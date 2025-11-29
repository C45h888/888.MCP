"""
Archiver - Background message archiver for MCP

Batches and archives published messages to S3 with Hive-style partitioning.
Supports JSONL.gz format with boto3 S3 uploads.

Fully implemented per CLAUDE.md specifications.
"""

import os
import json
import gzip
import boto3
import logging
import threading
import time
from datetime import datetime
from queue import Queue, Empty
from typing import Dict, Any, List
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class Archiver:
    """
    Real implementation of the MCP Archiver.
    Batches messages and uploads them to S3 with Hive-style partitioning.

    Configuration via environment variables:
    - ARCHIVE_ENABLED: Enable/disable archiving (default: true)
    - S3_DATA_BUCKET: S3 bucket for uploads (required)
    - AWS_DEFAULT_REGION: AWS region (default: eu-north-1)
    - ARCHIVE_BATCH_SIZE: Max batch size before flush (default: 100)
    - ARCHIVE_FLUSH_INTERVAL: Flush interval in seconds (default: 60)
    """

    def __init__(self):
        # Configuration
        self.enabled = os.getenv("ARCHIVE_ENABLED", "true").lower() == "true"
        self.bucket_name = os.getenv("S3_DATA_BUCKET")
        self.region = os.getenv("AWS_DEFAULT_REGION", "eu-north-1")
        self.batch_size = int(os.getenv("ARCHIVE_BATCH_SIZE", "100"))
        self.flush_interval = int(os.getenv("ARCHIVE_FLUSH_INTERVAL", "60"))

        # State
        self.queue = Queue()
        self.running = False
        self.worker_thread = None
        self.messages_archived = 0
        self.uploads_total = 0
        self.uploads_failed = 0

        # S3 Client Initialization
        self.s3_client = None
        if self.enabled and self.bucket_name:
            try:
                self.s3_client = boto3.client('s3', region_name=self.region)
                logger.info(f"✅ S3 Archiver initialized for bucket: {self.bucket_name} ({self.region})")
            except Exception as e:
                logger.error(f"❌ Failed to initialize S3 client: {e}")
                self.enabled = False
        else:
            logger.warning("⚠️ S3 Archiver disabled: ARCHIVE_ENABLED=false or S3_DATA_BUCKET missing")
            self.enabled = False

    def start(self):
        """Start the background worker thread."""
        if not self.enabled:
            logger.info("Archiver disabled - skipping start")
            return

        if self.running:
            logger.warning("Archiver already running")
            return

        self.running = True
        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=False)
        self.worker_thread.start()
        logger.info("MCP Archiver worker started")

    def stop(self):
        """Stop the worker thread gracefully and flush remaining messages."""
        if not self.running:
            return

        logger.info("Stopping archiver...")
        self.running = False

        if self.worker_thread:
            self.worker_thread.join(timeout=10)

        logger.info(f"Archiver stopped. Total archived: {self.messages_archived}")

    def enqueue(self, collection: str, message: Dict[str, Any]):
        """
        Add a message to the archive queue.

        Args:
            collection: Channel/collection name (e.g., "market:data")
            message: Message payload to archive
        """
        if not self.enabled:
            return

        # Enrich with timestamp if missing
        if 'timestamp' not in message:
            message['timestamp'] = time.time()

        item = {
            'collection': collection,
            'message': message
        }
        self.queue.put(item)

    def get_stats(self) -> Dict[str, Any]:
        """Return archiver statistics."""
        return {
            "enabled": self.enabled,
            "running": self.running,
            "queue_depth": self.queue.qsize(),
            "messages_archived": self.messages_archived,
            "uploads_total": self.uploads_total,
            "uploads_failed": self.uploads_failed
        }

    def _worker_loop(self):
        """
        Main worker loop: Collect batch -> Flush to S3.
        Runs in background thread until stop() is called.
        """
        batch = []
        last_flush_time = time.time()

        logger.info("Archiver worker loop started")

        while self.running:
            try:
                # Wait for items with timeout (to respect flush interval)
                time_remaining = self.flush_interval - (time.time() - last_flush_time)
                timeout = max(0.1, time_remaining)

                try:
                    item = self.queue.get(timeout=timeout)
                    batch.append(item)
                except Empty:
                    pass  # Timeout reached, proceed to flush check

                # Flush conditions: Batch full OR Time expired
                time_since_flush = time.time() - last_flush_time
                is_full = len(batch) >= self.batch_size
                is_time = time_since_flush >= self.flush_interval

                if batch and (is_full or is_time):
                    self._flush_batch(batch)
                    batch = []
                    last_flush_time = time.time()

            except Exception as e:
                logger.error(f"Error in archiver loop: {e}", exc_info=True)
                time.sleep(1)

        # Final flush on exit
        if batch:
            logger.info(f"Final flush of {len(batch)} messages before shutdown")
            self._flush_batch(batch)

    def _flush_batch(self, batch: List[Dict[str, Any]]):
        """
        Upload a batch of messages to S3 with Hive-style partitioning.

        S3 Path Format:
        s3://{bucket}/mcp/{collection}/year=YYYY/month=MM/day=DD/hour=HH/minute=MM/part-{ts}-{count}.jsonl.gz

        Args:
            batch: List of message items to upload
        """
        if not self.s3_client:
            logger.error("Attempted flush without S3 client")
            return

        if not batch:
            return

        try:
            # Use the timestamp of the first item for partitioning
            first_item = batch[0]
            message = first_item.get('message', {})
            ts = message.get('timestamp', time.time())
            dt = datetime.fromtimestamp(ts)

            # Get collection name (sanitize for S3 path)
            collection = first_item.get('collection', 'unknown')
            collection_safe = collection.replace(':', '_')

            # Prepare content: NDJSON (newline-delimited JSON)
            jsonl_lines = []
            for item in batch:
                jsonl_lines.append(json.dumps(item))
            jsonl_data = "\n".join(jsonl_lines)

            # GZIP compression
            compressed_data = gzip.compress(jsonl_data.encode('utf-8'))

            # Hive-style partitioning path
            # Format: mcp/{collection}/year=YYYY/month=MM/day=DD/hour=HH/minute=MM/
            prefix = (
                f"mcp/{collection_safe}/"
                f"year={dt.year}/"
                f"month={dt.month:02d}/"
                f"day={dt.day:02d}/"
                f"hour={dt.hour:02d}/"
                f"minute={dt.minute:02d}"
            )

            # Filename: part-{timestamp}-{count}.jsonl.gz
            filename = f"part-{int(ts)}-{len(batch)}.jsonl.gz"
            s3_key = f"{prefix}/{filename}"

            # Upload to S3
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=s3_key,
                Body=compressed_data,
                ContentType='application/gzip',
                ContentEncoding='gzip'
            )

            # Update statistics
            self.messages_archived += len(batch)
            self.uploads_total += 1

            logger.info(f"✅ Archived {len(batch)} messages to s3://{self.bucket_name}/{s3_key}")

        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            logger.error(f"❌ S3 Upload Failed ({error_code}): {e}")
            self.uploads_failed += 1

        except Exception as e:
            logger.error(f"❌ Archive Upload Failed: {e}", exc_info=True)
            self.uploads_failed += 1
