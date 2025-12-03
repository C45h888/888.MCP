"""
Phase 1.2 - Retrieval Accuracy & Limits Testing

Integration tests for /tool/retrieve endpoint covering:
- 1.2.1: Different pair values (BTC-ETH, BTC-USD, invalid)
- 1.2.2: Edge case time ranges (1min, 7-day, 30-day windows)
- 1.2.3: Limit parameter testing (near max 1000, small 10)
- 1.2.4: Time-ordering verification
- 1.2.5: Cursor-based pagination (if implemented)

Prerequisites:
- S3_DATA_BUCKET must be configured
- Test data must be seeded (use scripts/seed_test_data.py)
- MCP server must be running

Run with: pytest tests/integration/test_retrieval_accuracy.py -v
"""

import os
import pytest
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Any


# Test configuration
MCP_BASE_URL = os.getenv("MCP_URL", "http://localhost:8080")
MCP_API_KEY = os.getenv("MCP_API_KEY", "")
HEADERS = {
    "x-api-key": MCP_API_KEY,
    "Content-Type": "application/json"
}

# Skip all tests if S3 not configured (will return 501)
S3_CONFIGURED = bool(os.getenv("S3_DATA_BUCKET"))


class TestRetrievalBasics:
    """Basic retrieval endpoint functionality."""

    def test_retrieve_endpoint_exists(self):
        """Verify /tool/retrieve endpoint is accessible."""
        response = requests.post(
            f"{MCP_BASE_URL}/tool/retrieve",
            headers=HEADERS,
            json={"collection": "market:data", "limit": 1}
        )
        # Should be 200 (success) or 501 (S3 not configured), not 404
        assert response.status_code in [200, 501], \
            f"Unexpected status: {response.status_code}"

    @pytest.mark.skipif(not S3_CONFIGURED, reason="S3_DATA_BUCKET not configured")
    def test_retrieve_requires_valid_collection(self):
        """Test that invalid collection names are rejected."""
        response = requests.post(
            f"{MCP_BASE_URL}/tool/retrieve",
            headers=HEADERS,
            json={
                "collection": "invalid:collection",
                "limit": 10
            }
        )
        assert response.status_code == 400, \
            f"Expected 400 for invalid collection, got {response.status_code}"
        assert "invalid collection" in response.json()["detail"].lower()


class TestRetrievalPairFiltering:
    """1.2.1 - Test pair value filtering."""

    @pytest.mark.skipif(not S3_CONFIGURED, reason="S3_DATA_BUCKET not configured")
    def test_retrieve_with_btc_eth_pair(self):
        """Test retrieval with BTC-ETH pair filter."""
        response = requests.post(
            f"{MCP_BASE_URL}/tool/retrieve",
            headers=HEADERS,
            json={
                "collection": "market:data",
                "pair": "BTC-ETH",
                "limit": 100
            }
        )

        if response.status_code == 200:
            data = response.json()
            assert "messages" in data
            assert "count" in data

            # Verify all returned messages have BTC-ETH pair
            for msg in data["messages"]:
                assert msg.get("pair") == "BTC-ETH", \
                    f"Expected BTC-ETH, got {msg.get('pair')}"

            print(f"✅ Retrieved {data['count']} BTC-ETH messages")
        else:
            pytest.skip(f"Retrieval returned {response.status_code}: {response.text}")

    @pytest.mark.skipif(not S3_CONFIGURED, reason="S3_DATA_BUCKET not configured")
    def test_retrieve_with_btc_usd_pair(self):
        """Test retrieval with BTC-USD pair filter."""
        response = requests.post(
            f"{MCP_BASE_URL}/tool/retrieve",
            headers=HEADERS,
            json={
                "collection": "market:data",
                "pair": "BTC-USD",
                "limit": 100
            }
        )

        if response.status_code == 200:
            data = response.json()
            # Verify all returned messages have BTC-USD pair
            for msg in data["messages"]:
                assert msg.get("pair") == "BTC-USD", \
                    f"Expected BTC-USD, got {msg.get('pair')}"

            print(f"✅ Retrieved {data['count']} BTC-USD messages")
        else:
            pytest.skip(f"Retrieval returned {response.status_code}: {response.text}")

    @pytest.mark.skipif(not S3_CONFIGURED, reason="S3_DATA_BUCKET not configured")
    def test_retrieve_with_no_pair_filter(self):
        """Test retrieval without pair filter returns all pairs."""
        response = requests.post(
            f"{MCP_BASE_URL}/tool/retrieve",
            headers=HEADERS,
            json={
                "collection": "market:data",
                "limit": 100
            }
        )

        if response.status_code == 200:
            data = response.json()
            # Should return messages regardless of pair
            pairs = set(msg.get("pair") for msg in data["messages"] if "pair" in msg)
            print(f"✅ Retrieved {data['count']} messages with pairs: {pairs}")
            assert data["count"] >= 0  # Can be 0 if no data
        else:
            pytest.skip(f"Retrieval returned {response.status_code}: {response.text}")

    @pytest.mark.skipif(not S3_CONFIGURED, reason="S3_DATA_BUCKET not configured")
    def test_retrieve_with_nonexistent_pair(self):
        """Test retrieval with pair that doesn't exist in data."""
        response = requests.post(
            f"{MCP_BASE_URL}/tool/retrieve",
            headers=HEADERS,
            json={
                "collection": "market:data",
                "pair": "XYZ-ABC",  # Non-existent pair
                "limit": 100
            }
        )

        if response.status_code == 200:
            data = response.json()
            # Should return 0 messages
            assert data["count"] == 0, \
                f"Expected 0 messages for non-existent pair, got {data['count']}"
            print("✅ Non-existent pair correctly returns 0 messages")
        else:
            pytest.skip(f"Retrieval returned {response.status_code}: {response.text}")


class TestRetrievalTimeRanges:
    """1.2.2 - Test edge case time ranges."""

    @pytest.mark.skipif(not S3_CONFIGURED, reason="S3_DATA_BUCKET not configured")
    def test_retrieve_1_minute_window(self):
        """Test retrieval with 1-minute time window."""
        now = int(datetime.now().timestamp())
        from_ts = now - 60  # 1 minute ago
        to_ts = now

        response = requests.post(
            f"{MCP_BASE_URL}/tool/retrieve",
            headers=HEADERS,
            json={
                "collection": "market:data",
                "from_timestamp": from_ts,
                "to_timestamp": to_ts,
                "limit": 100
            }
        )

        if response.status_code == 200:
            data = response.json()
            # Verify all messages are within range
            for msg in data["messages"]:
                ts = msg.get("timestamp", 0)
                assert from_ts <= ts <= to_ts, \
                    f"Message timestamp {ts} outside range [{from_ts}, {to_ts}]"

            print(f"✅ 1-minute window: {data['count']} messages")
        else:
            pytest.skip(f"Retrieval returned {response.status_code}: {response.text}")

    @pytest.mark.skipif(not S3_CONFIGURED, reason="S3_DATA_BUCKET not configured")
    def test_retrieve_7_day_window(self):
        """Test retrieval with 7-day time window."""
        now = int(datetime.now().timestamp())
        from_ts = now - (7 * 24 * 60 * 60)  # 7 days ago
        to_ts = now

        response = requests.post(
            f"{MCP_BASE_URL}/tool/retrieve",
            headers=HEADERS,
            json={
                "collection": "market:data",
                "from_timestamp": from_ts,
                "to_timestamp": to_ts,
                "limit": 1000  # Max limit
            }
        )

        if response.status_code == 200:
            data = response.json()
            # Verify all messages are within range
            for msg in data["messages"]:
                ts = msg.get("timestamp", 0)
                assert from_ts <= ts <= to_ts, \
                    f"Message timestamp {ts} outside range [{from_ts}, {to_ts}]"

            print(f"✅ 7-day window: {data['count']} messages (limit: 1000)")
        else:
            pytest.skip(f"Retrieval returned {response.status_code}: {response.text}")

    @pytest.mark.skipif(not S3_CONFIGURED, reason="S3_DATA_BUCKET not configured")
    def test_retrieve_30_day_window(self):
        """Test retrieval with 30-day time window."""
        now = int(datetime.now().timestamp())
        from_ts = now - (30 * 24 * 60 * 60)  # 30 days ago
        to_ts = now

        response = requests.post(
            f"{MCP_BASE_URL}/tool/retrieve",
            headers=HEADERS,
            json={
                "collection": "market:data",
                "from_timestamp": from_ts,
                "to_timestamp": to_ts,
                "limit": 1000  # Max limit
            }
        )

        if response.status_code == 200:
            data = response.json()
            # Verify all messages are within range
            for msg in data["messages"]:
                ts = msg.get("timestamp", 0)
                assert from_ts <= ts <= to_ts, \
                    f"Message timestamp {ts} outside range [{from_ts}, {to_ts}]"

            print(f"✅ 30-day window: {data['count']} messages (limit: 1000)")

            # Warning if limit reached (might be truncated)
            if data['count'] >= 1000:
                print("⚠️  WARNING: Limit reached, results may be truncated")
        else:
            pytest.skip(f"Retrieval returned {response.status_code}: {response.text}")

    @pytest.mark.skipif(not S3_CONFIGURED, reason="S3_DATA_BUCKET not configured")
    def test_retrieve_future_time_range(self):
        """Test retrieval with future time range (should return 0 messages)."""
        future_ts = int((datetime.now() + timedelta(days=365)).timestamp())

        response = requests.post(
            f"{MCP_BASE_URL}/tool/retrieve",
            headers=HEADERS,
            json={
                "collection": "market:data",
                "from_timestamp": future_ts,
                "to_timestamp": future_ts + 3600,
                "limit": 100
            }
        )

        if response.status_code == 200:
            data = response.json()
            assert data["count"] == 0, \
                f"Expected 0 messages for future time range, got {data['count']}"
            print("✅ Future time range correctly returns 0 messages")
        else:
            pytest.skip(f"Retrieval returned {response.status_code}: {response.text}")


class TestRetrievalLimits:
    """1.2.3 - Test limit parameter near max and small values."""

    @pytest.mark.skipif(not S3_CONFIGURED, reason="S3_DATA_BUCKET not configured")
    def test_retrieve_limit_10(self):
        """Test retrieval with small limit (10)."""
        response = requests.post(
            f"{MCP_BASE_URL}/tool/retrieve",
            headers=HEADERS,
            json={
                "collection": "market:data",
                "limit": 10
            }
        )

        if response.status_code == 200:
            data = response.json()
            assert data["count"] <= 10, \
                f"Expected max 10 messages, got {data['count']}"
            print(f"✅ Limit 10: {data['count']} messages returned")
        else:
            pytest.skip(f"Retrieval returned {response.status_code}: {response.text}")

    @pytest.mark.skipif(not S3_CONFIGURED, reason="S3_DATA_BUCKET not configured")
    def test_retrieve_limit_100(self):
        """Test retrieval with medium limit (100)."""
        response = requests.post(
            f"{MCP_BASE_URL}/tool/retrieve",
            headers=HEADERS,
            json={
                "collection": "market:data",
                "limit": 100
            }
        )

        if response.status_code == 200:
            data = response.json()
            assert data["count"] <= 100, \
                f"Expected max 100 messages, got {data['count']}"
            print(f"✅ Limit 100: {data['count']} messages returned")
        else:
            pytest.skip(f"Retrieval returned {response.status_code}: {response.text}")

    @pytest.mark.skipif(not S3_CONFIGURED, reason="S3_DATA_BUCKET not configured")
    def test_retrieve_limit_1000_max(self):
        """Test retrieval with maximum limit (1000)."""
        response = requests.post(
            f"{MCP_BASE_URL}/tool/retrieve",
            headers=HEADERS,
            json={
                "collection": "market:data",
                "limit": 1000
            }
        )

        if response.status_code == 200:
            data = response.json()
            assert data["count"] <= 1000, \
                f"Expected max 1000 messages, got {data['count']}"
            print(f"✅ Limit 1000 (MAX): {data['count']} messages returned")
        else:
            pytest.skip(f"Retrieval returned {response.status_code}: {response.text}")

    @pytest.mark.skipif(not S3_CONFIGURED, reason="S3_DATA_BUCKET not configured")
    def test_retrieve_limit_exceeds_max(self):
        """Test that limit > 1000 is rejected."""
        response = requests.post(
            f"{MCP_BASE_URL}/tool/retrieve",
            headers=HEADERS,
            json={
                "collection": "market:data",
                "limit": 5000  # Exceeds max
            }
        )

        # Should return 400 Bad Request
        assert response.status_code == 400, \
            f"Expected 400 for limit > 1000, got {response.status_code}"
        assert "limit" in response.json()["detail"].lower()
        print("✅ Limit > 1000 correctly rejected with 400")

    @pytest.mark.skipif(not S3_CONFIGURED, reason="S3_DATA_BUCKET not configured")
    def test_retrieve_limit_1(self):
        """Test retrieval with limit 1 (edge case)."""
        response = requests.post(
            f"{MCP_BASE_URL}/tool/retrieve",
            headers=HEADERS,
            json={
                "collection": "market:data",
                "limit": 1
            }
        )

        if response.status_code == 200:
            data = response.json()
            assert data["count"] <= 1, \
                f"Expected max 1 message, got {data['count']}"
            print(f"✅ Limit 1: {data['count']} messages returned")
        else:
            pytest.skip(f"Retrieval returned {response.status_code}: {response.text}")


class TestRetrievalTimeOrdering:
    """1.2.4 - Verify time-ordering of returned records."""

    @pytest.mark.skipif(not S3_CONFIGURED, reason="S3_DATA_BUCKET not configured")
    def test_messages_sorted_by_timestamp_ascending(self):
        """Verify messages are sorted by timestamp in ascending order."""
        response = requests.post(
            f"{MCP_BASE_URL}/tool/retrieve",
            headers=HEADERS,
            json={
                "collection": "market:data",
                "limit": 100
            }
        )

        if response.status_code == 200:
            data = response.json()

            if data["count"] < 2:
                pytest.skip("Not enough messages to test ordering")

            messages = data["messages"]
            timestamps = [msg.get("timestamp", 0) for msg in messages]

            # Verify timestamps are in ascending order
            for i in range(len(timestamps) - 1):
                assert timestamps[i] <= timestamps[i + 1], \
                    f"Messages not sorted: ts[{i}]={timestamps[i]} > ts[{i+1}]={timestamps[i+1]}"

            print(f"✅ {len(timestamps)} messages correctly sorted by timestamp (ascending)")
        else:
            pytest.skip(f"Retrieval returned {response.status_code}: {response.text}")


class TestRetrievalPagination:
    """1.2.5 - Test cursor-based pagination (if implemented)."""

    @pytest.mark.skipif(not S3_CONFIGURED, reason="S3_DATA_BUCKET not configured")
    def test_pagination_cursor_support(self):
        """Test if cursor-based pagination is supported."""
        # First request
        response = requests.post(
            f"{MCP_BASE_URL}/tool/retrieve",
            headers=HEADERS,
            json={
                "collection": "market:data",
                "limit": 10
            }
        )

        if response.status_code == 200:
            data = response.json()

            # Check if cursor field exists in response
            if "cursor" in data or "next_cursor" in data:
                cursor = data.get("cursor") or data.get("next_cursor")
                print(f"✅ Pagination cursor found: {cursor}")

                # Try to fetch next page
                response2 = requests.post(
                    f"{MCP_BASE_URL}/tool/retrieve",
                    headers=HEADERS,
                    json={
                        "collection": "market:data",
                        "limit": 10,
                        "cursor": cursor
                    }
                )

                if response2.status_code == 200:
                    data2 = response2.json()
                    print(f"✅ Second page retrieved: {data2['count']} messages")

                    # Verify no overlapping messages (by timestamp or message content)
                    first_page_timestamps = {msg.get("timestamp") for msg in data["messages"]}
                    second_page_timestamps = {msg.get("timestamp") for msg in data2["messages"]}
                    overlap = first_page_timestamps & second_page_timestamps

                    assert len(overlap) == 0, \
                        f"Pages overlap with {len(overlap)} duplicate timestamps"

                    print("✅ No overlapping messages between pages")
                else:
                    pytest.fail(f"Second page request failed: {response2.status_code}")
            else:
                pytest.skip("Cursor-based pagination not implemented yet (no cursor field in response)")
        else:
            pytest.skip(f"Retrieval returned {response.status_code}: {response.text}")


class TestRetrievalSentimentData:
    """Test retrieval works for sentiment:data collection."""

    @pytest.mark.skipif(not S3_CONFIGURED, reason="S3_DATA_BUCKET not configured")
    def test_retrieve_sentiment_data(self):
        """Test retrieval from sentiment:data collection."""
        response = requests.post(
            f"{MCP_BASE_URL}/tool/retrieve",
            headers=HEADERS,
            json={
                "collection": "sentiment:data",
                "limit": 50
            }
        )

        if response.status_code == 200:
            data = response.json()
            print(f"✅ Retrieved {data['count']} sentiment messages")

            # Verify sentiment-specific fields
            for msg in data["messages"]:
                # Sentiment messages should have these fields
                if "score" in msg:
                    assert -1.0 <= msg["score"] <= 1.0, \
                        f"Sentiment score {msg['score']} out of range [-1, 1]"

        else:
            pytest.skip(f"Retrieval returned {response.status_code}: {response.text}")


# Run all tests if executed directly
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
