"""
Historical data retrieval module.

Provides safe access to historical MCP messages from S3 storage.
Falls back to 501 Not Implemented when S3 is not configured.
"""

import json
import logging
import os
from typing import List, Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

# S3 configuration (reuse from kill_persistence)
S3_KILL_BUCKET = os.getenv("S3_KILL_BUCKET", "")
S3_DATA_BUCKET = os.getenv("S3_DATA_BUCKET", "")  # Separate bucket for historical data
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID", "")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")

# Safety limits
MAX_RETRIEVE_LIMIT = 1000

# S3 client (lazy initialization)
_s3_client = None


def _get_s3_client():
    """Get or create S3 client (lazy initialization)."""
    global _s3_client

    if _s3_client is None and S3_DATA_BUCKET and AWS_ACCESS_KEY_ID:
        try:
            import boto3
            _s3_client = boto3.client(
                's3',
                aws_access_key_id=AWS_ACCESS_KEY_ID,
                aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
                region_name=AWS_REGION
            )
            logger.info(f"S3 retrieval client initialized for bucket: {S3_DATA_BUCKET}")
        except Exception as e:
            logger.warning(f"Failed to initialize S3 retrieval client: {e}")
            _s3_client = False  # Mark as failed to avoid retries

    return _s3_client if _s3_client and _s3_client is not False else None


def is_retrieval_enabled() -> bool:
    """Check if S3 retrieval is configured and available."""
    return _get_s3_client() is not None


def retrieve_historical_data(
    collection: str,
    pair: Optional[str] = None,
    from_timestamp: Optional[int] = None,
    to_timestamp: Optional[int] = None,
    limit: int = 100
) -> List[Dict[str, Any]]:
    """
    Retrieve historical messages from S3 storage.

    Args:
        collection: Channel name (market:data, sentiment:data, etc.)
        pair: Optional trading pair filter (e.g., "BTC-ETH")
        from_timestamp: Optional start timestamp (inclusive)
        to_timestamp: Optional end timestamp (inclusive)
        limit: Maximum number of records to return (capped at MAX_RETRIEVE_LIMIT)

    Returns:
        List of message dictionaries sorted by timestamp ascending

    Raises:
        ValueError: If S3 retrieval is not configured
        Exception: If S3 query fails
    """
    s3 = _get_s3_client()
    if not s3:
        raise ValueError("S3 retrieval not configured. Set S3_DATA_BUCKET and AWS credentials.")

    # Enforce safety limit
    limit = min(limit, MAX_RETRIEVE_LIMIT)

    try:
        # S3 key structure: <collection>/<year>/<month>/<day>/<timestamp>_<pair>.json
        # For simplicity, we'll list objects with prefix and filter client-side
        # Production implementation would use partitioned queries

        prefix = f"{collection}/"

        response = s3.list_objects_v2(
            Bucket=S3_DATA_BUCKET,
            Prefix=prefix,
            MaxKeys=limit * 2  # Fetch more to allow for filtering
        )

        messages = []

        if 'Contents' in response:
            for obj in response['Contents']:
                try:
                    # Fetch object content
                    obj_response = s3.get_object(
                        Bucket=S3_DATA_BUCKET,
                        Key=obj['Key']
                    )

                    message = json.loads(obj_response['Body'].read().decode('utf-8'))

                    # Apply filters
                    msg_timestamp = message.get('timestamp', 0)

                    # Timestamp filter
                    if from_timestamp and msg_timestamp < from_timestamp:
                        continue
                    if to_timestamp and msg_timestamp > to_timestamp:
                        continue

                    # Pair filter
                    if pair and message.get('pair') != pair:
                        continue

                    messages.append(message)

                    # Stop if we've reached limit
                    if len(messages) >= limit:
                        break

                except Exception as e:
                    logger.warning(f"Failed to parse S3 object {obj['Key']}: {e}")
                    continue

        # Sort by timestamp ascending
        messages.sort(key=lambda x: x.get('timestamp', 0))

        logger.info(
            f"Retrieved {len(messages)} messages from {collection}",
            extra={
                'collection': collection,
                'pair': pair,
                'count': len(messages)
            }
        )

        return messages

    except Exception as e:
        logger.error(f"Failed to retrieve from S3: {e}")
        raise
