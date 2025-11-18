#!/usr/bin/env python3
"""
Archiver Runner - Standalone worker process for MCP message archiving

Runs the Archiver as a foreground service with graceful shutdown on SIGTERM/SIGINT.
Intended to run as a Render.com worker service or similar long-running background job.

Usage:
    python -u -m mcp.uploader.archiver_runner

Environment variables:
    - ARCHIVE_ENABLED: Enable/disable archiving (default: true)
    - ARCHIVE_DIR: Local archive directory (default: /tmp/mcp_archive)
    - ARCHIVE_FLUSH_INTERVAL: Flush interval in seconds (default: 60)
    - ARCHIVE_BATCH_SIZE: Max batch size before flush (default: 1000)
    - ARCHIVE_FORMAT: Storage format - jsonl or parquet (default: jsonl)
    - S3_DATA_BUCKET: S3 bucket for uploads (optional)
"""

import logging
import signal
import sys
import time
from pathlib import Path

# Add parent directory to path so we can import from mcp package
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from mcp.uploader.archiver import Archiver

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

# Global archiver instance
archiver = None
shutdown_requested = False


def signal_handler(signum, frame):
    """Handle SIGTERM/SIGINT for graceful shutdown."""
    global shutdown_requested
    sig_name = signal.Signals(signum).name
    logger.info(f"Received signal {sig_name} - initiating graceful shutdown")
    shutdown_requested = True

    if archiver:
        archiver.stop()


def main():
    """Main entry point for archiver worker."""
    global archiver

    logger.info("=" * 60)
    logger.info("MCP Archiver Worker starting...")
    logger.info("=" * 60)

    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    try:
        # Initialize and start archiver
        archiver = Archiver()
        archiver.start()

        if not archiver.enabled:
            logger.warning("Archiver is DISABLED via ARCHIVE_ENABLED=false")
            logger.warning("Worker will exit immediately")
            return 0

        logger.info("Archiver worker running. Press Ctrl+C to stop.")

        # Keep process alive until shutdown signal
        while not shutdown_requested:
            time.sleep(1)

            # Periodically log stats
            stats = archiver.get_stats()
            if stats["messages_archived"] % 1000 == 0 and stats["messages_archived"] > 0:
                logger.info(f"Stats: {stats}")

    except Exception as e:
        logger.error(f"Fatal error in archiver worker: {e}", exc_info=True)
        return 1

    finally:
        if archiver:
            archiver.stop()

        logger.info("Archiver worker stopped cleanly")

    return 0


if __name__ == "__main__":
    sys.exit(main())
