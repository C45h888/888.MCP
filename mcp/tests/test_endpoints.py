"""
Test suite for MCP Server endpoints.

Tests cover:
- Schema validation
- Publishing to channels
- Kill-switch logic
- Health checks
- Error handling
"""

import pytest
import json
import os
from datetime import datetime
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch

# Import app components
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Set dev mode for tests (bypass auth by default)
os.environ["MCP_DEV"] = "true"

# Reload app to pick up env vars
import importlib
import server as server_module
importlib.reload(server_module)
app = server_module.app

from redis_client import RedisClient

# Test client
client = TestClient(app)


class TestMCPInfo:
    """Test /.well-known/mcp endpoint."""

    def test_mcp_info_returns_correct_structure(self):
        """Test that MCP info endpoint returns expected metadata."""
        response = client.get("/.well-known/mcp")
        assert response.status_code == 200

        data = response.json()
        assert data["name"] == "MCP Trading Server"
        assert data["version"] == "1.0.0"
        assert data["type"] == "custom-redis-pubsub"
        assert len(data["channels"]) == 4
        assert "market:data" in data["channels"]
        assert "sentiment:data" in data["channels"]
        assert "agent:control" in data["channels"]
        assert "agent:signal" in data["channels"]


class TestListCollections:
    """Test /tool/list_collections endpoint."""

    def test_list_collections_returns_all_channels(self):
        """Test that list_collections returns all 4 MCP channels."""
        response = client.get("/tool/list_collections")
        assert response.status_code == 200

        data = response.json()
        assert data["total"] == 4
        assert len(data["channels"]) == 4
        assert set(data["channels"]) == {
            "market:data",
            "sentiment:data",
            "agent:control",
            "agent:signal"
        }


class TestPublishMessage:
    """Test /tool/publish endpoint."""

    @patch('server.redis_client.publish')
    def test_publish_valid_market_data(self, mock_publish):
        """Test publishing valid market data message."""
        mock_publish.return_value = 2  # 2 subscribers

        message = {
            "schema_version": "v1",
            "timestamp": 1678886400,
            "pair": "BTC-ETH",
            "price_btc": 30000.0,
            "price_eth": 2000.0,
            "volume_btc": 150.5
        }

        response = client.post(
            "/tool/publish",
            json={"channel": "market:data", "message": message}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["channel"] == "market:data"
        assert data["subscriber_count"] == 2
        mock_publish.assert_called_once()

    @patch('server.redis_client.publish')
    def test_publish_valid_sentiment_data(self, mock_publish):
        """Test publishing valid sentiment data message."""
        mock_publish.return_value = 1

        message = {
            "schema_version": "v1",
            "timestamp": 1678886405,
            "source": "Twitter",
            "score": 0.85,
            "summary": "Major institution announces Bitcoin ETF."
        }

        response = client.post(
            "/tool/publish",
            json={"channel": "sentiment:data", "message": message}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["channel"] == "sentiment:data"

    @patch('server.redis_client.publish')
    def test_publish_valid_control_message(self, mock_publish):
        """Test publishing valid control message."""
        mock_publish.return_value = 1

        message = {
            "schema_version": "v1",
            "timestamp": 1678886410,
            "command": "EMERGENCY_HALT",
            "reason": "USDT_DEPEG_DETECTED"
        }

        response = client.post(
            "/tool/publish",
            json={"channel": "agent:control", "message": message}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    @patch('server.redis_client.publish')
    def test_publish_valid_signal_message(self, mock_publish):
        """Test publishing valid signal message."""
        mock_publish.return_value = 1

        message = {
            "schema_version": "v1",
            "timestamp": 1678886415,
            "pair": "BTC-ETH",
            "action": "SHORT_SPREAD",
            "confidence": 0.78,
            "stop_loss_z": 3.0,
            "reason": "Z-Score > 2, ML Confirmed"
        }

        response = client.post(
            "/tool/publish",
            json={"channel": "agent:signal", "message": message}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_publish_invalid_channel(self):
        """Test that invalid channel is rejected."""
        message = {"timestamp": 1678886400, "test": "data"}

        response = client.post(
            "/tool/publish",
            json={"channel": "invalid:channel", "message": message}
        )

        assert response.status_code == 400
        assert "Invalid channel" in response.json()["detail"]

    def test_publish_missing_required_field(self):
        """Test that message with missing required field is rejected."""
        message = {
            "schema_version": "v1",
            "timestamp": 1678886400,
            "pair": "BTC-ETH",
            # Missing price_btc, price_eth, volume_btc
        }

        response = client.post(
            "/tool/publish",
            json={"channel": "market:data", "message": message}
        )

        assert response.status_code == 422
        assert "validation failed" in response.json()["detail"].lower()

    def test_publish_invalid_field_type(self):
        """Test that message with invalid field type is rejected."""
        message = {
            "schema_version": "v1",
            "timestamp": "not-a-number",  # Should be integer
            "pair": "BTC-ETH",
            "price_btc": 30000.0,
            "price_eth": 2000.0,
            "volume_btc": 150.5
        }

        response = client.post(
            "/tool/publish",
            json={"channel": "market:data", "message": message}
        )

        assert response.status_code == 422

    def test_publish_additional_properties_rejected(self):
        """Test that additional properties are rejected (additionalProperties: false)."""
        message = {
            "schema_version": "v1",
            "timestamp": 1678886400,
            "pair": "BTC-ETH",
            "price_btc": 30000.0,
            "price_eth": 2000.0,
            "volume_btc": 150.5,
            "extra_field": "should_not_be_here"  # Not in schema
        }

        response = client.post(
            "/tool/publish",
            json={"channel": "market:data", "message": message}
        )

        assert response.status_code == 422

    def test_publish_sentiment_score_out_of_range(self):
        """Test that sentiment score outside [-1, 1] is rejected."""
        message = {
            "schema_version": "v1",
            "timestamp": 1678886405,
            "source": "Twitter",
            "score": 1.5,  # Out of range
            "summary": "Test"
        }

        response = client.post(
            "/tool/publish",
            json={"channel": "sentiment:data", "message": message}
        )

        assert response.status_code == 422

    def test_publish_invalid_control_command(self):
        """Test that invalid control command is rejected."""
        message = {
            "schema_version": "v1",
            "timestamp": 1678886410,
            "command": "INVALID_COMMAND",  # Not in enum
            "reason": "Test"
        }

        response = client.post(
            "/tool/publish",
            json={"channel": "agent:control", "message": message}
        )

        assert response.status_code == 422

    def test_publish_missing_schema_version(self):
        """Test that message without schema_version is rejected."""
        message = {
            # Missing schema_version
            "timestamp": 1678886400,
            "pair": "BTC-ETH",
            "price_btc": 30000.0,
            "price_eth": 2000.0,
            "volume_btc": 150.5
        }

        response = client.post(
            "/tool/publish",
            json={"channel": "market:data", "message": message}
        )

        assert response.status_code == 400
        assert "schema_version" in response.json()["detail"].lower()

    def test_publish_wrong_schema_version(self):
        """Test that message with wrong schema_version is rejected."""
        message = {
            "schema_version": "v2",  # Wrong version
            "timestamp": 1678886400,
            "pair": "BTC-ETH",
            "price_btc": 30000.0,
            "price_eth": 2000.0,
            "volume_btc": 150.5
        }

        response = client.post(
            "/tool/publish",
            json={"channel": "market:data", "message": message}
        )

        assert response.status_code == 400
        assert "schema_version" in response.json()["detail"].lower()


class TestAuthentication:
    """Test API key authentication."""

    def test_dev_mode_bypasses_auth(self):
        """Test that MCP_DEV=true allows requests without API key."""
        # Already set in module-level setup
        message = {
            "schema_version": "v1",
            "timestamp": 1678886400,
            "pair": "BTC-ETH",
            "price_btc": 30000.0,
            "price_eth": 2000.0,
            "volume_btc": 150.5
        }

        with patch('server.redis_client.publish', return_value=1):
            response = client.post(
                "/tool/publish",
                json={"channel": "market:data", "message": message}
            )

        # Should succeed even without x-api-key header
        assert response.status_code == 200


class TestGetStatus:
    """Test /tool/get_status endpoint."""

    @patch('server.redis_client.health_check')
    @patch('server.redis_client.get_kill_switch_status')
    @patch('server.redis_client.get_channel_info')
    def test_get_status_healthy(self, mock_channel_info, mock_kill_switch, mock_health):
        """Test status endpoint when system is healthy."""
        mock_health.return_value = True
        mock_kill_switch.return_value = {"active": False}
        mock_channel_info.return_value = {
            "market:data": 2,
            "sentiment:data": 1,
            "agent:control": 1,
            "agent:signal": 1
        }

        response = client.get("/tool/get_status")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "healthy"
        assert data["redis_connected"] is True
        assert data["kill_switch"]["active"] is False

    @patch('server.redis_client.health_check')
    @patch('server.redis_client.get_kill_switch_status')
    @patch('server.redis_client.get_channel_info')
    def test_get_status_emergency_halt(self, mock_channel_info, mock_kill_switch, mock_health):
        """Test status endpoint when kill switch is active."""
        mock_health.return_value = True
        mock_kill_switch.return_value = {
            "active": True,
            "timestamp": 1678886410,
            "reason": "USDT_DEPEG_DETECTED"
        }
        mock_channel_info.return_value = {}

        response = client.get("/tool/get_status")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "EMERGENCY_HALT"
        assert data["kill_switch"]["active"] is True
        assert data["kill_switch"]["reason"] == "USDT_DEPEG_DETECTED"


class TestHealth:
    """Test /health endpoint."""

    @patch('server.redis_client.health_check')
    def test_health_check_healthy(self, mock_health):
        """Test health endpoint when Redis is connected."""
        mock_health.return_value = True

        response = client.get("/health")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "healthy"
        assert data["redis"] is True

    @patch('server.redis_client.health_check')
    def test_health_check_unhealthy(self, mock_health):
        """Test health endpoint when Redis is disconnected."""
        mock_health.return_value = False

        response = client.get("/health")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "unhealthy"
        assert data["redis"] is False


class TestRetrievalEndpoint:
    """Test historical data retrieval endpoint."""

    def test_retrieve_returns_501_when_s3_not_configured(self):
        """Test that retrieve endpoint returns 501 when S3 not configured."""
        # Ensure S3 is not configured
        os.environ.pop("S3_DATA_BUCKET", None)

        retrieve_request = {
            "collection": "market:data",
            "limit": 10
        }

        response = client.post("/tool/retrieve", json=retrieve_request)

        assert response.status_code == 501
        assert "not configured" in response.json()["detail"].lower()

    def test_retrieve_validates_collection(self):
        """Test that retrieve endpoint validates collection name."""
        retrieve_request = {
            "collection": "invalid:collection",
            "limit": 10
        }

        response = client.post("/tool/retrieve", json=retrieve_request)
        assert response.status_code in [400, 501]  # 501 if S3 not configured, 400 if it is


class TestRAGEndpoint:
    """Test RAG search endpoint."""

    def test_search_rag_returns_501(self):
        """Test that RAG search returns 501 (not yet implemented)."""
        search_request = {"query": "Bitcoin price prediction", "k": 5}

        response = client.post("/tool/search_rag", json=search_request)

        assert response.status_code == 501
        assert "not yet implemented" in response.json()["detail"].lower()


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
