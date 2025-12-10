"""
Rate Limiting System for MCP Server.

Implements multi-tier rate limiting using Redis token bucket algorithm:
1. Per-IP global rate limit (prevent DoS)
2. Per-API-key rate limit (fair usage enforcement)
3. Per-endpoint rate limits (protect specific endpoints)

Design:
- Token bucket algorithm for smooth rate limiting
- Redis-backed for distributed rate limiting
- Configurable limits via environment variables
- Rate limit headers in responses (X-RateLimit-*)
- Metrics for monitoring rate limit violations
"""

import time
import logging
from typing import Tuple, Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class RateLimitExceeded(Exception):
    """
    Exception raised when rate limit is exceeded.

    Attributes:
        limit: Rate limit that was exceeded (e.g., "60/minute")
        retry_after: Seconds until rate limit resets
        headers: Rate limit headers to include in response
    """

    def __init__(self, limit: str, retry_after: int, headers: Dict[str, str]):
        self.limit = limit
        self.retry_after = retry_after
        self.headers = headers
        super().__init__(f"Rate limit exceeded: {limit}")


class RateLimiter:
    """
    Multi-tier rate limiter using Redis token bucket algorithm.

    Token Bucket Algorithm:
    - Each client has a bucket with a max capacity of tokens
    - Tokens are added at a fixed rate
    - Each request consumes one token
    - Request is allowed if bucket has >= 1 token
    - Request is denied if bucket is empty

    Redis Storage:
    - Key: "mcp:ratelimit:<type>:<identifier>"
    - Value: JSON with {tokens: float, last_refill: timestamp}
    - TTL: Window duration (auto-cleanup)

    Rate Limit Formats:
    - "60/minute" = 60 requests per minute
    - "100/minute" = 100 requests per minute
    - "10/second" = 10 requests per second
    """

    RATELIMIT_PREFIX = "mcp:ratelimit:"

    def __init__(self, redis_client):
        """
        Initialize rate limiter.

        Args:
            redis_client: RedisClient instance for storage
        """
        self.redis = redis_client
        logger.info("RateLimiter initialized")

    @staticmethod
    def parse_limit(limit: str) -> Tuple[int, int]:
        """
        Parse rate limit string into (max_requests, window_seconds).

        Args:
            limit: Rate limit string (e.g., "60/minute", "100/minute")

        Returns:
            Tuple of (max_requests, window_seconds)

        Raises:
            ValueError: If limit format is invalid

        Examples:
            >>> parse_limit("60/minute")
            (60, 60)
            >>> parse_limit("100/minute")
            (100, 60)
            >>> parse_limit("10/second")
            (10, 1)
        """
        try:
            parts = limit.split("/")
            if len(parts) != 2:
                raise ValueError(f"Invalid limit format: {limit}")

            max_requests = int(parts[0])
            unit = parts[1].lower()

            # Convert unit to seconds
            unit_seconds = {
                "second": 1,
                "minute": 60,
                "hour": 3600,
                "day": 86400,
            }

            if unit not in unit_seconds:
                raise ValueError(f"Invalid time unit: {unit}")

            window_seconds = unit_seconds[unit]

            return max_requests, window_seconds

        except Exception as e:
            raise ValueError(f"Failed to parse limit '{limit}': {e}")

    def check_rate_limit(
        self,
        identifier: str,
        limit: str,
        cost: int = 1
    ) -> Tuple[bool, Dict[str, str]]:
        """
        Check if request is within rate limit using token bucket algorithm.

        Args:
            identifier: Unique identifier (e.g., "ip:1.2.3.4", "key:abc123")
            limit: Rate limit string (e.g., "60/minute")
            cost: Number of tokens to consume (default: 1)

        Returns:
            Tuple of (allowed: bool, headers: dict)
            - allowed: True if request is allowed, False if rate limited
            - headers: Dict of rate limit headers to include in response
                {
                    "X-RateLimit-Limit": "60",
                    "X-RateLimit-Remaining": "45",
                    "X-RateLimit-Reset": "1678886460"
                }

        Raises:
            ValueError: If limit format is invalid
        """
        max_requests, window_seconds = self.parse_limit(limit)

        # Redis key for this rate limit bucket
        redis_key = f"{self.RATELIMIT_PREFIX}{identifier}"

        now = time.time()

        try:
            # Get current bucket state
            bucket_data = self.redis.client.get(redis_key)

            if bucket_data:
                # Parse existing bucket
                parts = bucket_data.decode().split(":")
                tokens = float(parts[0])
                last_refill = float(parts[1])
            else:
                # Initialize new bucket (full)
                tokens = float(max_requests)
                last_refill = now

            # Calculate token refill
            time_elapsed = now - last_refill
            refill_rate = max_requests / window_seconds  # Tokens per second

            # Add tokens based on elapsed time
            tokens = min(max_requests, tokens + (time_elapsed * refill_rate))

            # Check if enough tokens available
            allowed = tokens >= cost

            if allowed:
                # Consume tokens
                tokens -= cost
                remaining = int(tokens)
            else:
                # Not allowed, don't consume
                remaining = 0

            # Calculate reset time (when bucket will be full again)
            tokens_to_refill = max_requests - tokens
            seconds_to_refill = tokens_to_refill / refill_rate
            reset_time = int(now + seconds_to_refill)

            # Update bucket in Redis
            bucket_value = f"{tokens}:{now}"
            self.redis.client.setex(
                redis_key,
                window_seconds * 2,  # TTL: 2x window for safety
                bucket_value
            )

            # Build rate limit headers
            headers = {
                "X-RateLimit-Limit": str(max_requests),
                "X-RateLimit-Remaining": str(remaining),
                "X-RateLimit-Reset": str(reset_time),
            }

            if not allowed:
                # Calculate retry-after in seconds
                retry_after = int(1 / refill_rate) if refill_rate > 0 else window_seconds
                headers["Retry-After"] = str(retry_after)

                logger.warning(
                    "Rate limit exceeded",
                    extra={
                        "identifier": identifier,
                        "limit": limit,
                        "retry_after": retry_after
                    }
                )

            return allowed, headers

        except Exception as e:
            logger.error(f"Rate limit check failed: {e}", exc_info=True)
            # On error, allow request (fail open)
            return True, {
                "X-RateLimit-Limit": str(max_requests),
                "X-RateLimit-Remaining": "unknown",
                "X-RateLimit-Reset": str(int(now + window_seconds)),
            }

    def get_rate_limit_info(self, identifier: str, limit: str) -> Dict[str, any]:
        """
        Get current rate limit status for an identifier.

        Args:
            identifier: Unique identifier
            limit: Rate limit string

        Returns:
            Dict with current rate limit status:
            {
                "limit": 60,
                "remaining": 45,
                "reset": 1678886460,
                "reset_human": "2025-03-15 10:21:00"
            }
        """
        max_requests, window_seconds = self.parse_limit(limit)
        redis_key = f"{self.RATELIMIT_PREFIX}{identifier}"

        now = time.time()

        try:
            bucket_data = self.redis.client.get(redis_key)

            if bucket_data:
                parts = bucket_data.decode().split(":")
                tokens = float(parts[0])
                last_refill = float(parts[1])

                # Calculate current tokens
                time_elapsed = now - last_refill
                refill_rate = max_requests / window_seconds
                tokens = min(max_requests, tokens + (time_elapsed * refill_rate))

                remaining = int(tokens)
            else:
                remaining = max_requests

            # Calculate reset time
            tokens_to_refill = max_requests - remaining
            refill_rate = max_requests / window_seconds
            seconds_to_refill = tokens_to_refill / refill_rate if refill_rate > 0 else 0
            reset_time = int(now + seconds_to_refill)

            return {
                "limit": max_requests,
                "remaining": remaining,
                "reset": reset_time,
                "reset_human": datetime.fromtimestamp(reset_time).strftime("%Y-%m-%d %H:%M:%S"),
            }

        except Exception as e:
            logger.error(f"Failed to get rate limit info: {e}", exc_info=True)
            return {
                "limit": max_requests,
                "remaining": "unknown",
                "reset": int(now + window_seconds),
                "reset_human": "unknown",
            }

    def reset_rate_limit(self, identifier: str) -> bool:
        """
        Reset rate limit for an identifier (admin operation).

        Args:
            identifier: Unique identifier to reset

        Returns:
            True if reset successful, False otherwise
        """
        redis_key = f"{self.RATELIMIT_PREFIX}{identifier}"

        try:
            deleted = self.redis.client.delete(redis_key)

            if deleted:
                logger.info(f"Rate limit reset for: {identifier}")
                return True
            else:
                logger.warning(f"No rate limit found for: {identifier}")
                return False

        except Exception as e:
            logger.error(f"Failed to reset rate limit: {e}", exc_info=True)
            return False


class RateLimitConfig:
    """
    Centralized rate limit configuration for all endpoints.

    Environment variables:
    - RATE_LIMIT_GLOBAL_IP: Global per-IP limit (default: "100/minute")
    - RATE_LIMIT_GLOBAL_KEY: Global per-key limit (default: "200/minute")
    - RATE_LIMIT_PUBLISH: Publish endpoint limit (default: "60/minute")
    - RATE_LIMIT_RETRIEVE: Retrieve endpoint limit (default: "30/minute")
    - RATE_LIMIT_STATUS: Status endpoint limit (default: "120/minute")
    - RATE_LIMIT_METRICS: Metrics endpoint limit (default: "120/minute")
    - RATE_LIMIT_ADMIN: Admin endpoints limit (default: "30/minute")
    """

    def __init__(self):
        """Initialize rate limit configuration from environment variables."""
        import os

        self.global_ip = os.getenv("RATE_LIMIT_GLOBAL_IP", "100/minute")
        self.global_key = os.getenv("RATE_LIMIT_GLOBAL_KEY", "200/minute")
        self.publish = os.getenv("RATE_LIMIT_PUBLISH", "60/minute")
        self.retrieve = os.getenv("RATE_LIMIT_RETRIEVE", "30/minute")
        self.status = os.getenv("RATE_LIMIT_STATUS", "120/minute")
        self.metrics = os.getenv("RATE_LIMIT_METRICS", "120/minute")
        self.admin = os.getenv("RATE_LIMIT_ADMIN", "30/minute")
        self.health = os.getenv("RATE_LIMIT_HEALTH", "300/minute")

        logger.info(
            "Rate limit configuration loaded",
            extra={
                "global_ip": self.global_ip,
                "global_key": self.global_key,
                "publish": self.publish,
                "retrieve": self.retrieve,
            }
        )

    def get_limit_for_endpoint(self, endpoint: str) -> str:
        """
        Get rate limit for a specific endpoint.

        Args:
            endpoint: Endpoint path (e.g., "/tool/publish")

        Returns:
            Rate limit string
        """
        endpoint_limits = {
            "/tool/publish": self.publish,
            "/tool/retrieve": self.retrieve,
            "/tool/get_status": self.status,
            "/tool/kill_history": self.status,
            "/tool/list_collections": self.status,
            "/metrics": self.metrics,
            "/health": self.health,
            "/admin/keys/create": self.admin,
            "/admin/keys/list": self.admin,
            "/admin/keys/revoke": self.admin,
            "/admin/keys/rotate": self.admin,
        }

        return endpoint_limits.get(endpoint, self.status)
