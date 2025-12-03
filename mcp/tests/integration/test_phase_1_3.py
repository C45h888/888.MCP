"""
Phase 1.3 Integration Tests - Kill-Switch & Control Channel Reliability

Tests the complete kill-switch and control channel behavior as specified in
Task 1.3 of current-work.md:

1.3.1: Send multiple EMERGENCY_HALT commands (rapid sequence of 5)
1.3.2: Verify kill_history returns correct and ordered control events
1.3.3: Test kill-switch persistence (requires manual restart verification)
1.3.4: Documentation validation

These tests use real Redis (not mocks) to verify actual persistence behavior.
Requires Redis running on REDIS_URL (default: redis://localhost:6379).

Usage:
    # Run all Phase 1.3 tests
    pytest tests/integration/test_phase_1_3.py -v

    # Run with docker-compose
    docker-compose up -d redis
    pytest tests/integration/test_phase_1_3.py -v
    docker-compose down
"""

import pytest
import json
import os
import time
from datetime import datetime
from fastapi.testclient import TestClient
import redis

# Set dev mode for tests (bypass auth)
os.environ["MCP_DEV"] = "true"

# Import app components
import importlib
from mcp import server as server_module
importlib.reload(server_module)
app = server_module.app
from mcp.redis_client import RedisClient

# Test client
client = TestClient(app)

# Redis client for direct verification
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
redis_direct = redis.from_url(REDIS_URL, decode_responses=True)


@pytest.fixture(autouse=True)
def clear_kill_switch_state():
    """Clear kill switch state before and after each test."""
    # Clear before test
    redis_direct.delete(RedisClient.KILL_SWITCH_KEY)
    redis_direct.delete(RedisClient.KILL_HISTORY_KEY)

    yield

    # Clear after test
    redis_direct.delete(RedisClient.KILL_SWITCH_KEY)
    redis_direct.delete(RedisClient.KILL_HISTORY_KEY)


class TestTask1_3_1_RapidEmergencyHalt:
    """
    Task 1.3.1: Send multiple EMERGENCY_HALT commands (rapid sequence of 5)

    Verify system handles rapid control messages correctly:
    - All messages are accepted
    - History tracks all events
    - Kill switch remains active
    - No race conditions or crashes
    """

    def test_rapid_emergency_halt_sequence(self):
        """Send 5 rapid EMERGENCY_HALT commands."""
        base_timestamp = int(datetime.now().timestamp())

        # Send 5 rapid EMERGENCY_HALT commands
        responses = []
        for i in range(5):
            message = {
                "schema_version": "v1",
                "timestamp": base_timestamp + i,
                "command": "EMERGENCY_HALT",
                "reason": f"RAPID_TEST_{i+1}"
            }

            response = client.post(
                "/tool/publish",
                json={"channel": "agent:control", "message": message}
            )
            responses.append(response)

            # No delay - truly rapid

        # Verify all requests succeeded
        for i, response in enumerate(responses):
            assert response.status_code == 200, f"Request {i+1} failed: {response.json()}"
            data = response.json()
            assert data["success"] is True
            assert data["channel"] == "agent:control"

        # Give Redis a moment to process
        time.sleep(0.1)

        # Verify kill switch is active (latest state)
        status_response = client.get("/tool/get_status")
        assert status_response.status_code == 200
        status_data = status_response.json()
        assert status_data["kill_switch"]["active"] is True

        # Verify all 5 events are in history
        history_response = client.get("/tool/kill_history")
        assert history_response.status_code == 200
        history_data = history_response.json()

        assert history_data["count"] == 5, f"Expected 5 events, got {history_data['count']}"

        # Verify all events are EMERGENCY_HALT
        for event in history_data["events"]:
            assert event["command"] == "EMERGENCY_HALT"

        # Verify ordering (most recent first)
        for i in range(4):
            assert history_data["events"][i]["timestamp"] >= history_data["events"][i+1]["timestamp"]

    def test_mixed_control_sequence(self):
        """Test HALT → RESUME → HALT sequence."""
        base_timestamp = int(datetime.now().timestamp())

        commands = [
            ("EMERGENCY_HALT", "FIRST_HALT"),
            ("RESUME", "CLEAR_FIRST"),
            ("EMERGENCY_HALT", "SECOND_HALT"),
            ("EMERGENCY_HALT", "THIRD_HALT"),
            ("RESUME", "FINAL_CLEAR")
        ]

        for i, (command, reason) in enumerate(commands):
            message = {
                "schema_version": "v1",
                "timestamp": base_timestamp + i,
                "command": command,
                "reason": reason
            }

            response = client.post(
                "/tool/publish",
                json={"channel": "agent:control", "message": message}
            )
            assert response.status_code == 200

        time.sleep(0.1)

        # Final state should be inactive (last command was RESUME)
        status_response = client.get("/tool/get_status")
        status_data = status_response.json()
        assert status_data["kill_switch"]["active"] is False

        # History should contain all 5 events
        history_response = client.get("/tool/kill_history")
        history_data = history_response.json()
        assert history_data["count"] == 5

        # Verify correct ordering (most recent first)
        assert history_data["events"][0]["command"] == "RESUME"
        assert history_data["events"][0]["reason"] == "FINAL_CLEAR"


class TestTask1_3_2_KillHistoryOrdering:
    """
    Task 1.3.2: Verify kill_history returns correct and ordered control events

    Test that:
    - History returns events in correct order (most recent first)
    - All control events are tracked
    - Limit parameter works correctly
    - History includes all required fields
    """

    def test_kill_history_ordering(self):
        """Verify kill history returns events in correct order."""
        base_timestamp = int(datetime.now().timestamp())

        # Create sequence of events with known timestamps
        events = [
            (base_timestamp + 0, "EMERGENCY_HALT", "EVENT_1"),
            (base_timestamp + 1, "RESUME", "EVENT_2"),
            (base_timestamp + 2, "EMERGENCY_HALT", "EVENT_3"),
            (base_timestamp + 3, "RESUME", "EVENT_4"),
        ]

        for timestamp, command, reason in events:
            message = {
                "schema_version": "v1",
                "timestamp": timestamp,
                "command": command,
                "reason": reason
            }
            response = client.post(
                "/tool/publish",
                json={"channel": "agent:control", "message": message}
            )
            assert response.status_code == 200

        time.sleep(0.1)

        # Get history
        history_response = client.get("/tool/kill_history")
        assert history_response.status_code == 200
        history_data = history_response.json()

        assert history_data["count"] == 4

        # Verify reverse chronological order (most recent first)
        assert history_data["events"][0]["reason"] == "EVENT_4"
        assert history_data["events"][1]["reason"] == "EVENT_3"
        assert history_data["events"][2]["reason"] == "EVENT_2"
        assert history_data["events"][3]["reason"] == "EVENT_1"

        # Verify timestamps are descending
        for i in range(3):
            assert history_data["events"][i]["timestamp"] >= history_data["events"][i+1]["timestamp"]

    def test_kill_history_includes_all_fields(self):
        """Verify each history entry has all required fields."""
        message = {
            "schema_version": "v1",
            "timestamp": int(datetime.now().timestamp()),
            "command": "EMERGENCY_HALT",
            "reason": "FIELD_TEST"
        }

        response = client.post(
            "/tool/publish",
            json={"channel": "agent:control", "message": message}
        )
        assert response.status_code == 200

        time.sleep(0.1)

        history_response = client.get("/tool/kill_history")
        history_data = history_response.json()

        assert history_data["count"] == 1
        event = history_data["events"][0]

        # Verify required fields
        assert "command" in event
        assert "timestamp" in event
        assert "reason" in event
        assert "recorded_at" in event

        assert event["command"] == "EMERGENCY_HALT"
        assert event["reason"] == "FIELD_TEST"

    def test_kill_history_limit_parameter(self):
        """Test that limit parameter works correctly."""
        base_timestamp = int(datetime.now().timestamp())

        # Create 10 events
        for i in range(10):
            message = {
                "schema_version": "v1",
                "timestamp": base_timestamp + i,
                "command": "EMERGENCY_HALT",
                "reason": f"EVENT_{i+1}"
            }
            response = client.post(
                "/tool/publish",
                json={"channel": "agent:control", "message": message}
            )
            assert response.status_code == 200

        time.sleep(0.1)

        # Request only 5 most recent
        history_response = client.get("/tool/kill_history?limit=5")
        assert history_response.status_code == 200
        history_data = history_response.json()

        assert history_data["count"] == 5

        # Verify we got the 5 most recent (EVENT_10 to EVENT_6)
        assert history_data["events"][0]["reason"] == "EVENT_10"
        assert history_data["events"][4]["reason"] == "EVENT_6"

    def test_kill_history_includes_current_status(self):
        """Verify kill_history response includes current kill switch status."""
        # Activate kill switch
        message = {
            "schema_version": "v1",
            "timestamp": int(datetime.now().timestamp()),
            "command": "EMERGENCY_HALT",
            "reason": "STATUS_TEST"
        }

        response = client.post(
            "/tool/publish",
            json={"channel": "agent:control", "message": message}
        )
        assert response.status_code == 200

        time.sleep(0.1)

        # Get history
        history_response = client.get("/tool/kill_history")
        history_data = history_response.json()

        # Verify current_status field exists and is correct
        assert "current_status" in history_data
        assert history_data["current_status"]["active"] is True
        assert history_data["current_status"]["reason"] == "STATUS_TEST"


class TestTask1_3_3_Persistence:
    """
    Task 1.3.3: Test kill-switch persistence

    Verify that kill switch state persists in Redis and can survive
    application restarts.

    Note: Full restart testing requires manual verification (see documentation).
    These tests verify Redis persistence at the data layer.
    """

    def test_kill_switch_persists_in_redis(self):
        """Verify kill switch state is written to Redis."""
        # Activate kill switch
        message = {
            "schema_version": "v1",
            "timestamp": int(datetime.now().timestamp()),
            "command": "EMERGENCY_HALT",
            "reason": "PERSISTENCE_TEST"
        }

        response = client.post(
            "/tool/publish",
            json={"channel": "agent:control", "message": message}
        )
        assert response.status_code == 200

        time.sleep(0.1)

        # Verify Redis key exists
        kill_switch_data = redis_direct.get(RedisClient.KILL_SWITCH_KEY)
        assert kill_switch_data is not None

        # Parse and verify
        kill_switch = json.loads(kill_switch_data)
        assert kill_switch["active"] is True
        assert kill_switch["reason"] == "PERSISTENCE_TEST"

    def test_kill_history_persists_in_redis(self):
        """Verify kill history is written to Redis list."""
        # Create some events
        for i in range(3):
            message = {
                "schema_version": "v1",
                "timestamp": int(datetime.now().timestamp()),
                "command": "EMERGENCY_HALT",
                "reason": f"HISTORY_TEST_{i+1}"
            }
            response = client.post(
                "/tool/publish",
                json={"channel": "agent:control", "message": message}
            )
            assert response.status_code == 200

        time.sleep(0.1)

        # Verify Redis list exists
        history_length = redis_direct.llen(RedisClient.KILL_HISTORY_KEY)
        assert history_length == 3

        # Verify we can read events directly from Redis
        history_json = redis_direct.lrange(RedisClient.KILL_HISTORY_KEY, 0, -1)
        assert len(history_json) == 3

        # Parse first event (most recent)
        first_event = json.loads(history_json[0])
        assert first_event["command"] == "EMERGENCY_HALT"
        assert "HISTORY_TEST" in first_event["reason"]

    def test_resume_clears_kill_switch_but_keeps_history(self):
        """Verify RESUME clears kill switch but history remains."""
        base_timestamp = int(datetime.now().timestamp())

        # Activate
        halt_message = {
            "schema_version": "v1",
            "timestamp": base_timestamp,
            "command": "EMERGENCY_HALT",
            "reason": "TEST_HALT"
        }
        client.post("/tool/publish", json={"channel": "agent:control", "message": halt_message})

        time.sleep(0.1)

        # Verify active
        kill_switch_data = redis_direct.get(RedisClient.KILL_SWITCH_KEY)
        assert kill_switch_data is not None

        # Resume
        resume_message = {
            "schema_version": "v1",
            "timestamp": base_timestamp + 1,
            "command": "RESUME",
            "reason": "TEST_CLEAR"
        }
        client.post("/tool/publish", json={"channel": "agent:control", "message": resume_message})

        time.sleep(0.1)

        # Verify kill switch cleared
        kill_switch_data = redis_direct.get(RedisClient.KILL_SWITCH_KEY)
        assert kill_switch_data is None

        # Verify history still exists with both events
        history_length = redis_direct.llen(RedisClient.KILL_HISTORY_KEY)
        assert history_length == 2


class TestTask1_3_RestartVerification:
    """
    Task 1.3.3 (continued): Restart verification instructions

    These are not automated tests, but instructions for manual verification
    of kill switch persistence across server restarts.

    See: docs/test-results/phase-1.3-restart-verification.md
    """

    def test_restart_verification_instructions(self):
        """Print instructions for manual restart verification."""
        instructions = """
        MANUAL RESTART VERIFICATION STEPS:

        1. Activate kill switch:
           curl -X POST "$MCP_URL/tool/publish" \\
             -H "x-api-key: $MCP_API_KEY" \\
             -H "Content-Type: application/json" \\
             -d '{
               "channel": "agent:control",
               "message": {
                 "schema_version": "v1",
                 "timestamp": TIMESTAMP,
                 "command": "EMERGENCY_HALT",
                 "reason": "RESTART_TEST"
               }
             }'

        2. Verify kill switch active:
           curl -H "x-api-key: $MCP_API_KEY" "$MCP_URL/tool/get_status" | jq .kill_switch

        3. Restart MCP server service:
           - On Render: Dashboard → mcp-server → Manual Deploy → Restart
           - Local: docker-compose restart mcp-server

        4. Wait for server to come back online (30-60 seconds)

        5. Verify kill switch STILL active:
           curl -H "x-api-key: $MCP_API_KEY" "$MCP_URL/tool/get_status" | jq .kill_switch

           Expected: {"active": true, "reason": "RESTART_TEST", ...}

        6. Verify kill history STILL contains event:
           curl -H "x-api-key: $MCP_API_KEY" "$MCP_URL/tool/kill_history" | jq '.events[] | select(.reason == "RESTART_TEST")'

           Expected: Event found with command "EMERGENCY_HALT"

        7. Clean up - Resume normal operations:
           curl -X POST "$MCP_URL/tool/publish" \\
             -H "x-api-key: $MCP_API_KEY" \\
             -H "Content-Type: application/json" \\
             -d '{
               "channel": "agent:control",
               "message": {
                 "schema_version": "v1",
                 "timestamp": TIMESTAMP,
                 "command": "RESUME",
                 "reason": "RESTART_TEST_COMPLETE"
               }
             }'

        SUCCESS CRITERIA:
        ✓ Kill switch remains active after restart
        ✓ Kill history remains intact after restart
        ✓ Redis persistence working correctly
        """

        # This test always passes - it's just documentation
        print(instructions)
        assert True


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
