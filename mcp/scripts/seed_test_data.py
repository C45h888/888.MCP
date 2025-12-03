#!/usr/bin/env python3
"""
Test Data Seeding Utility for Retrieval Testing

Seeds the MCP server with test data for Phase 1.2 retrieval accuracy testing.
Publishes messages across multiple pairs, time ranges, and collections.

Usage:
    # Seed production/staging server
    export MCP_URL="https://your-mcp-server.onrender.com"
    export MCP_API_KEY="your-api-key"
    python scripts/seed_test_data.py

    # Seed with custom parameters
    python scripts/seed_test_data.py --market-messages 200 --sentiment-messages 50

    # Dry run (show what would be published)
    python scripts/seed_test_data.py --dry-run

Prerequisites:
    - MCP_URL and MCP_API_KEY environment variables
    - MCP server must be running
    - Archiver should be enabled for data to persist to S3

Author: MCP Development Team
"""

import os
import sys
import time
import argparse
import requests
from datetime import datetime, timedelta
from typing import Dict, Any, List
import random


# Configuration
MCP_URL = os.getenv("MCP_URL", "http://localhost:8080")
MCP_API_KEY = os.getenv("MCP_API_KEY", "")

HEADERS = {
    "x-api-key": MCP_API_KEY,
    "Content-Type": "application/json"
}

# Trading pairs to seed
TRADING_PAIRS = ["BTC-ETH", "BTC-USD", "ETH-USD"]

# Sentiment sources
SENTIMENT_SOURCES = ["Twitter", "Reddit", "News", "TradingView"]


def publish_message(collection: str, message: Dict[str, Any], dry_run: bool = False) -> bool:
    """
    Publish a single message to MCP server.

    Args:
        collection: Channel name (market:data, sentiment:data, etc.)
        message: Message payload (must include schema_version)
        dry_run: If True, print message but don't publish

    Returns:
        True if successful, False otherwise
    """
    if dry_run:
        print(f"[DRY RUN] Would publish to {collection}: {message}")
        return True

    try:
        response = requests.post(
            f"{MCP_URL}/tool/publish",
            headers=HEADERS,
            json={
                "collection": collection,
                "message": message
            },
            timeout=10
        )

        if response.status_code == 200:
            return True
        else:
            print(f"❌ Publish failed: HTTP {response.status_code} - {response.text}")
            return False

    except Exception as e:
        print(f"❌ Publish error: {e}")
        return False


def generate_market_message(pair: str, timestamp: int) -> Dict[str, Any]:
    """
    Generate a market:data message with realistic random prices.

    Args:
        pair: Trading pair (e.g., "BTC-ETH")
        timestamp: Unix timestamp

    Returns:
        Message dictionary conforming to market:data schema
    """
    # Base prices (realistic as of 2024)
    base_prices = {
        "BTC": 30000 + random.uniform(-5000, 5000),
        "ETH": 2000 + random.uniform(-300, 300),
        "USD": 1.0
    }

    # Parse pair
    base, quote = pair.split("-")

    price_base = base_prices.get(base, 1000)
    price_quote = base_prices.get(quote, 1.0)

    return {
        "schema_version": "v1",
        "timestamp": timestamp,
        "pair": pair,
        f"price_{base.lower()}": round(price_base, 2),
        f"price_{quote.lower()}": round(price_quote, 2),
        f"volume_{base.lower()}": round(random.uniform(50, 500), 2)
    }


def generate_sentiment_message(timestamp: int) -> Dict[str, Any]:
    """
    Generate a sentiment:data message with random sentiment.

    Args:
        timestamp: Unix timestamp

    Returns:
        Message dictionary conforming to sentiment:data schema
    """
    score = round(random.uniform(-1.0, 1.0), 2)

    # Generate summary based on score
    if score > 0.5:
        summaries = [
            "Major institution announces Bitcoin ETF approval.",
            "Crypto market shows strong bullish momentum.",
            "Ethereum upgrade receives positive community feedback."
        ]
    elif score < -0.5:
        summaries = [
            "Regulatory concerns impact market sentiment.",
            "Exchange security breach raises safety concerns.",
            "Market volatility increases amid uncertainty."
        ]
    else:
        summaries = [
            "Market shows mixed signals across trading pairs.",
            "Traders await regulatory clarity.",
            "Consolidation period continues in major assets."
        ]

    return {
        "schema_version": "v1",
        "timestamp": timestamp,
        "source": random.choice(SENTIMENT_SOURCES),
        "score": score,
        "summary": random.choice(summaries)
    }


def seed_market_data(
    num_messages: int,
    time_spread_days: int = 7,
    dry_run: bool = False
) -> tuple[int, int]:
    """
    Seed market:data messages across multiple pairs and time ranges.

    Args:
        num_messages: Total number of market messages to publish
        time_spread_days: Spread messages across this many days
        dry_run: If True, don't actually publish

    Returns:
        Tuple of (published_count, failed_count)
    """
    print(f"\n📊 Seeding {num_messages} market:data messages...")
    print(f"   Time spread: {time_spread_days} days")
    print(f"   Trading pairs: {TRADING_PAIRS}")

    published = 0
    failed = 0

    now = int(datetime.now().timestamp())
    time_spread_seconds = time_spread_days * 24 * 60 * 60

    for i in range(num_messages):
        # Distribute across time range
        timestamp = now - random.randint(0, time_spread_seconds)

        # Distribute across pairs
        pair = TRADING_PAIRS[i % len(TRADING_PAIRS)]

        # Generate and publish message
        message = generate_market_message(pair, timestamp)

        if publish_message("market:data", message, dry_run):
            published += 1
            if not dry_run and (published % 10 == 0):
                print(f"  Published {published}/{num_messages}...", end="\r")
        else:
            failed += 1

        # Rate limiting (don't overwhelm server)
        if not dry_run:
            time.sleep(0.1)  # 10 msg/sec max

    if not dry_run:
        print(f"  Published {published}/{num_messages}... ✅")

    return published, failed


def seed_sentiment_data(
    num_messages: int,
    time_spread_days: int = 7,
    dry_run: bool = False
) -> tuple[int, int]:
    """
    Seed sentiment:data messages across time ranges.

    Args:
        num_messages: Total number of sentiment messages to publish
        time_spread_days: Spread messages across this many days
        dry_run: If True, don't actually publish

    Returns:
        Tuple of (published_count, failed_count)
    """
    print(f"\n💭 Seeding {num_messages} sentiment:data messages...")
    print(f"   Time spread: {time_spread_days} days")
    print(f"   Sources: {SENTIMENT_SOURCES}")

    published = 0
    failed = 0

    now = int(datetime.now().timestamp())
    time_spread_seconds = time_spread_days * 24 * 60 * 60

    for i in range(num_messages):
        # Distribute across time range
        timestamp = now - random.randint(0, time_spread_seconds)

        # Generate and publish message
        message = generate_sentiment_message(timestamp)

        if publish_message("sentiment:data", message, dry_run):
            published += 1
            if not dry_run and (published % 10 == 0):
                print(f"  Published {published}/{num_messages}...", end="\r")
        else:
            failed += 1

        # Rate limiting
        if not dry_run:
            time.sleep(0.1)  # 10 msg/sec max

    if not dry_run:
        print(f"  Published {published}/{num_messages}... ✅")

    return published, failed


def seed_edge_case_data(dry_run: bool = False) -> tuple[int, int]:
    """
    Seed edge case data for specific test scenarios.

    - Exact 1000 messages for limit testing
    - Messages at very recent timestamps (1 min ago)
    - Messages at older timestamps (30 days ago)

    Returns:
        Tuple of (published_count, failed_count)
    """
    print(f"\n🔧 Seeding edge case test data...")

    published = 0
    failed = 0

    now = int(datetime.now().timestamp())

    # 1. Seed 10 messages from last minute (for 1-min window test)
    print("  Creating recent messages (1 min ago)...")
    for i in range(10):
        timestamp = now - random.randint(0, 60)
        message = generate_market_message("BTC-ETH", timestamp)

        if publish_message("market:data", message, dry_run):
            published += 1
        else:
            failed += 1

        if not dry_run:
            time.sleep(0.1)

    # 2. Seed 50 messages from 30 days ago (for 30-day window test)
    print("  Creating older messages (30 days ago)...")
    thirty_days_ago = now - (30 * 24 * 60 * 60)

    for i in range(50):
        timestamp = thirty_days_ago + random.randint(0, 86400)  # Spread across that day
        message = generate_market_message("BTC-USD", timestamp)

        if publish_message("market:data", message, dry_run):
            published += 1
        else:
            failed += 1

        if not dry_run:
            time.sleep(0.1)

    print(f"  Published {published} edge case messages ✅")

    return published, failed


def verify_server_connection() -> bool:
    """
    Verify we can connect to MCP server.

    Returns:
        True if server is reachable, False otherwise
    """
    try:
        response = requests.get(f"{MCP_URL}/health", timeout=5)
        if response.status_code == 200:
            print(f"✅ Server connection verified: {MCP_URL}")
            return True
        else:
            print(f"❌ Server returned HTTP {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Cannot connect to server: {e}")
        return False


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Seed MCP server with test data for retrieval testing"
    )

    parser.add_argument(
        "--market-messages",
        type=int,
        default=100,
        help="Number of market:data messages to seed (default: 100)"
    )

    parser.add_argument(
        "--sentiment-messages",
        type=int,
        default=30,
        help="Number of sentiment:data messages to seed (default: 30)"
    )

    parser.add_argument(
        "--time-spread-days",
        type=int,
        default=7,
        help="Spread messages across this many days (default: 7)"
    )

    parser.add_argument(
        "--edge-cases",
        action="store_true",
        help="Also seed edge case data for specific test scenarios"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be published without actually publishing"
    )

    args = parser.parse_args()

    # Header
    print("=" * 70)
    print("MCP Test Data Seeding Utility - Phase 1.2 Retrieval Testing")
    print("=" * 70)
    print(f"\nTarget server: {MCP_URL}")

    if args.dry_run:
        print("🔍 DRY RUN MODE - No data will be published\n")

    # Check environment
    if not MCP_API_KEY and not args.dry_run:
        print("❌ ERROR: MCP_API_KEY not set")
        print("   Usage: export MCP_API_KEY='your-api-key'")
        return 1

    # Verify server connection
    if not args.dry_run:
        if not verify_server_connection():
            print("\n❌ Cannot proceed - server not reachable")
            return 1

    print()

    # Seed data
    total_published = 0
    total_failed = 0

    # Market data
    published, failed = seed_market_data(
        args.market_messages,
        args.time_spread_days,
        args.dry_run
    )
    total_published += published
    total_failed += failed

    # Sentiment data
    published, failed = seed_sentiment_data(
        args.sentiment_messages,
        args.time_spread_days,
        args.dry_run
    )
    total_published += published
    total_failed += failed

    # Edge cases (optional)
    if args.edge_cases:
        published, failed = seed_edge_case_data(args.dry_run)
        total_published += published
        total_failed += failed

    # Summary
    print("\n" + "=" * 70)
    print("SEEDING SUMMARY")
    print("=" * 70)
    print(f"Total published: {total_published}")
    print(f"Total failed:    {total_failed}")

    if args.dry_run:
        print("\n🔍 DRY RUN - No data was actually published")
        print("   Remove --dry-run flag to publish for real")
    elif total_failed == 0:
        print("\n✅ ALL MESSAGES PUBLISHED SUCCESSFULLY")
        print("\n💡 Next steps:")
        print("   1. Wait 60-90 seconds for archiver to flush to S3")
        print("   2. Run retrieval tests:")
        print("      pytest tests/integration/test_retrieval_accuracy.py -v")
        print("      ./scripts/test_retrieval_phase_1_2.sh")
    else:
        print(f"\n⚠️  WARNING: {total_failed} messages failed to publish")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
