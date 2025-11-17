"""
Integration tests for MCP Server.

These tests require docker-compose services to be running:
  - redis
  - mcp-server

Run with: pytest tests/integration/ -v
"""

import pytest
import requests
import redis
import json
import time
from typing import Dict, Any

# Base URL for MCP server (running in docker-compose)
MCP_BASE_URL = "http://localhost:8080"
REDIS_URL = "redis://localhost:6379"

# Test API key (for production mode tests)
TEST_API_KEY = "test-api-key-12345"


@pytest.fixture(scope="module")
def wait_for_services():
    """Wait for MCP server and Redis to be ready."""
    max_retries = 30
    retry_delay = 1

    # Wait for MCP server
    for i in range(max_retries):
        try:
            response = requests.get(f"{MCP_BASE_URL}/health", timeout=2)
            if response.status_code == 200:
                break
        except requests.RequestException:
            pass
        time.sleep(retry_delay)
    else:
        pytest.fail("MCP server did not become ready in time")

    # Wait for Redis
    for i in range(max_retries):
        try:
            r = redis.from_url(REDIS_URL)
            r.ping()
            break
        except redis.RedisError:
            pass
        time.sleep(retry_delay)
    else:
        pytest.fail("Redis did not become ready in time")

    yield

    # Cleanup: clear kill switch if set
    try:
        r = redis.from_url(REDIS_URL)
        r.delete("mcp:kill_switch")
    except:
        pass


class TestDiscovery:
    """Test MCP server discovery endpoints."""

    def test_well_known_mcp(self, wait_for_services):
        """Test /.well-known/mcp endpoint returns correct metadata."""
        response = requests.get(f"{MCP_BASE_URL}/.well-known/mcp")
        assert response.status_code == 200

        data = response.json()
        assert data["name"] == "MCP Trading Server"
        assert data["type"] == "custom-redis-pubsub"
        assert len(data["channels"]) == 4
        assert "market:data" in data["channels"]
        assert "sentiment:data" in data["channels"]
        assert "agent:control" in data["channels"]
        assert "agent:signal" in data["channels"]

    def test_list_collections(self, wait_for_services):
        """Test /tool/list_collections endpoint."""
        response = requests.get(f"{MCP_BASE_URL}/tool/list_collections")
        assert response.status_code == 200

        data = response.json()
        assert data["total"] == 4
        assert set(data["channels"]) == {
            "market:data",
            "sentiment:data",
            "agent:control",
            "agent:signal"
        }

    def test_health_endpoint(self, wait_for_services):
        """Test /health endpoint."""
        response = requests.get(f"{MCP_BASE_URL}/health")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "healthy"
        assert data["redis"] is True


class TestPublish:
    """Test message publishing with schema validation."""

    def test_publish_valid_market_data(self, wait_for_services):
        """Test publishing valid market data with schema_version."""
        message = {
            "schema_version": "v1",
            "timestamp": 1678886400,
            "pair": "BTC-ETH",
            "price_btc": 30000.0,
            "price_eth": 2000.0,
            "volume_btc": 150.5
        }

        response = requests.post(
            f"{MCP_BASE_URL}/tool/publish",
            json={"channel": "market:data", "message": message}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["channel"] == "market:data"

    def test_publish_missing_schema_version(self, wait_for_services):
        """Test that message without schema_version is rejected."""
        message = {
            # Missing schema_version
            "timestamp": 1678886400,
            "pair": "BTC-ETH",
            "price_btc": 30000.0,
            "price_eth": 2000.0,
            "volume_btc": 150.5
        }

        response = requests.post(
            f"{MCP_BASE_URL}/tool/publish",
            json={"channel": "market:data", "message": message}
        )

        assert response.status_code == 400
        assert "schema_version" in response.json()["detail"].lower()

    def test_publish_invalid_channel(self, wait_for_services):
        """Test that invalid channel is rejected."""
        message = {
            "schema_version": "v1",
            "timestamp": 1678886400
        }

        response = requests.post(
            f"{MCP_BASE_URL}/tool/publish",
            json={"channel": "invalid:channel", "message": message}
        )

        assert response.status_code == 400
        assert "Invalid channel" in response.json()["detail"]


class TestEmergencyHalt:
    """Test EMERGENCY_HALT kill-switch persistence."""

    def test_emergency_halt_persists_to_redis(self, wait_for_services):
        """Test that EMERGENCY_HALT command persists to mcp:kill_switch key."""
        message = {
            "schema_version": "v1",
            "timestamp": 1678886410,
            "command": "EMERGENCY_HALT",
            "reason": "Integration test - USDT depeg simulation"
        }

        response = requests.post(
            f"{MCP_BASE_URL}/tool/publish",
            json={"channel": "agent:control", "message": message}
        )

        assert response.status_code == 200

        # Check Redis for kill switch
        r = redis.from_url(REDIS_URL, decode_responses=True)
        kill_switch_data = r.get("mcp:kill_switch")
        assert kill_switch_data is not None

        kill_switch = json.loads(kill_switch_data)
        assert kill_switch["active"] is True
        assert "USDT depeg" in kill_switch["reason"]
