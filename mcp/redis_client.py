"""
Redis Pub/Sub Client for MCP Server

This module provides a Redis client wrapper for publishing and subscribing
to MCP channels with built-in kill-switch logic.
"""

import json
import logging
from typing import Dict, Any, Optional
import redis
from datetime import datetime

logger = logging.getLogger(__name__)


class RedisClient:
    """
    Redis client for MCP message bus operations.

    Handles:
    - Publishing to defined MCP channels
    - Kill-switch persistence
    - Connection health checks
    """

    # Valid MCP channels as defined in architecture
    VALID_CHANNELS = {
        "market:data",
        "sentiment:data",
        "agent:control",
        "agent:signal"
    }

    KILL_SWITCH_KEY = "mcp:kill_switch"

    def __init__(self, redis_url: str = "redis://localhost:6379"):
        """
        Initialize Redis client.

        Args:
            redis_url: Redis connection URL
        """
        self.redis_url = redis_url
        self.client: Optional[redis.Redis] = None
        self._connect()

    def _connect(self) -> None:
        """Establish connection to Redis."""
        try:
            self.client = redis.from_url(
                self.redis_url,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_keepalive=True
            )
            # Test connection
            self.client.ping()
            logger.info(f"Connected to Redis at {self.redis_url}")
        except redis.RedisError as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise

    def publish(self, channel: str, message: Dict[str, Any]) -> int:
        """
        Publish a message to an MCP channel.

        Args:
            channel: MCP channel name (must be in VALID_CHANNELS)
            message: Message payload (will be JSON-encoded)

        Returns:
            Number of subscribers that received the message

        Raises:
            ValueError: If channel is not valid
            redis.RedisError: If publish fails
        """
        if channel not in self.VALID_CHANNELS:
            raise ValueError(
                f"Invalid channel '{channel}'. "
                f"Must be one of: {self.VALID_CHANNELS}"
            )

        try:
            # Handle kill-switch persistence
            if channel == "agent:control":
                self._handle_control_message(message)

            # Publish message
            message_json = json.dumps(message)
            subscriber_count = self.client.publish(channel, message_json)

            logger.info(
                f"Published to {channel}: {message_json[:100]}... "
                f"({subscriber_count} subscribers)"
            )

            return subscriber_count

        except redis.RedisError as e:
            logger.error(f"Failed to publish to {channel}: {e}")
            raise

    def _handle_control_message(self, message: Dict[str, Any]) -> None:
        """
        Handle agent:control messages with kill-switch persistence.

        If command is EMERGENCY_HALT, persist to Redis key.

        Args:
            message: Control message payload
        """
        command = message.get("command")

        if command == "EMERGENCY_HALT":
            # Persist kill switch
            kill_switch_data = {
                "active": True,
                "timestamp": message.get("timestamp", int(datetime.now().timestamp())),
                "reason": message.get("reason", "Unknown")
            }
            self.client.set(
                self.KILL_SWITCH_KEY,
                json.dumps(kill_switch_data)
            )
            logger.warning(f"KILL SWITCH ACTIVATED: {kill_switch_data['reason']}")

        elif command == "RESUME":
            # Clear kill switch
            self.client.delete(self.KILL_SWITCH_KEY)
            logger.info("Kill switch deactivated - RESUME command received")

    def get_kill_switch_status(self) -> Dict[str, Any]:
        """
        Get current kill-switch status.

        Returns:
            Dict with 'active' boolean and optional 'reason', 'timestamp'
        """
        kill_switch_data = self.client.get(self.KILL_SWITCH_KEY)

        if kill_switch_data:
            return json.loads(kill_switch_data)

        return {"active": False}

    def health_check(self) -> bool:
        """
        Check Redis connection health.

        Returns:
            True if healthy, False otherwise
        """
        try:
            return self.client.ping()
        except redis.RedisError:
            return False

    def get_channel_info(self) -> Dict[str, int]:
        """
        Get subscriber counts for all MCP channels.

        Returns:
            Dict mapping channel names to subscriber counts
        """
        try:
            pubsub_channels = self.client.pubsub_channels()

            info = {}
            for channel in self.VALID_CHANNELS:
                # Count subscribers
                if channel.encode() in pubsub_channels or channel in pubsub_channels:
                    subscribers = self.client.pubsub_numsub(channel)[0][1]
                else:
                    subscribers = 0
                info[channel] = subscribers

            return info

        except redis.RedisError as e:
            logger.error(f"Failed to get channel info: {e}")
            return {channel: 0 for channel in self.VALID_CHANNELS}

    def close(self) -> None:
        """Close Redis connection."""
        if self.client:
            self.client.close()
            logger.info("Redis connection closed")
