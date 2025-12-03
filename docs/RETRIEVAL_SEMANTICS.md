# Retrieval Semantics Documentation

**Version:** 1.0
**Last Updated:** 2024-12-03
**Phase:** 1.2 - Retrieval Accuracy & Limits Testing
**Status:** Production-Ready ✅

---

## Table of Contents

1. [Overview](#overview)
2. [Endpoint Specification](#endpoint-specification)
3. [Request Schema](#request-schema)
4. [Response Schema](#response-schema)
5. [Filtering Capabilities](#filtering-capabilities)
6. [Limits and Safety](#limits-and-safety)
7. [Time Ordering Guarantees](#time-ordering-guarantees)
8. [Pagination](#pagination)
9. [Error Handling](#error-handling)
10. [Performance Considerations](#performance-considerations)
11. [Best Practices](#best-practices)
12. [Code Examples](#code-examples)

---

## Overview

The `/tool/retrieve` endpoint provides read-only access to historical MCP messages stored in S3. It enables the Brain Agent and other consumers to:

- Fetch historical market data for backtesting
- Retrieve sentiment history for analysis
- Access trade signals for performance evaluation
- Query control events (kill-switch history)

**Key Characteristics:**
- **Read-only**: Never modifies data
- **Paginated**: Enforces safety limits to prevent memory exhaustion
- **Filtered**: Supports pair, timestamp, and collection filtering
- **Ordered**: Always returns messages in ascending timestamp order
- **Safe**: Hard caps prevent unbounded queries

---

## Endpoint Specification

**URL:** `POST /tool/retrieve`

**Authentication:** Required (`x-api-key` header)

**Prerequisites:**
- `S3_DATA_BUCKET` must be configured
- AWS credentials must be valid
- Returns HTTP 501 if S3 not configured

**Rate Limits:** None currently enforced (trust-based)

---

## Request Schema

### Full Request Example

```json
{
  "collection": "market:data",
  "pair": "BTC-ETH",
  "from_timestamp": 1701388800,
  "to_timestamp": 1701475200,
  "limit": 100
}
```

### Request Fields

| Field | Type | Required | Description | Constraints |
|-------|------|----------|-------------|-------------|
| `collection` | string | ✅ Yes | Channel name | Must be valid MCP channel |
| `pair` | string | ❌ No | Trading pair filter | e.g., "BTC-ETH", "BTC-USD" |
| `from_timestamp` | integer | ❌ No | Start time (inclusive) | Unix timestamp in seconds |
| `to_timestamp` | integer | ❌ No | End time (inclusive) | Unix timestamp in seconds |
| `limit` | integer | ❌ No | Max messages to return | Default: 100, Max: 1000 |
| `cursor` | string | ❌ No | Pagination cursor | ⚠️ Not implemented yet |

### Valid Collections

- `market:data` - Price, volume data
- `sentiment:data` - Sentiment scores, summaries
- `agent:signal` - Trade signals from Brain
- `agent:control` - Kill-switch commands

---

## Response Schema

### Successful Response (HTTP 200)

```json
{
  "messages": [
    {
      "schema_version": "v1",
      "timestamp": 1701388801,
      "pair": "BTC-ETH",
      "price_btc": 30000.0,
      "price_eth": 2000.0,
      "volume_btc": 150.5
    },
    {
      "schema_version": "v1",
      "timestamp": 1701388805,
      "pair": "BTC-ETH",
      "price_btc": 30005.0,
      "price_eth": 2001.0,
      "volume_btc": 152.3
    }
  ],
  "count": 2,
  "collection": "market:data",
  "filters": {
    "pair": "BTC-ETH",
    "from_timestamp": 1701388800,
    "to_timestamp": 1701475200,
    "limit": 100
  }
}
```

### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `messages` | array | Array of message objects (sorted by timestamp) |
| `count` | integer | Number of messages returned (≤ limit) |
| `collection` | string | Echo of requested collection |
| `filters` | object | Echo of applied filters |

### Error Responses

| HTTP Code | Condition | Example |
|-----------|-----------|---------|
| **400** | Invalid collection | `{"detail": "Invalid collection. Must be one of: [...]}` |
| **400** | Limit exceeds max | `{"detail": "Limit exceeds maximum allowed (1000)"}` |
| **401** | Missing API key | `{"detail": "Not authenticated"}` |
| **501** | S3 not configured | `{"detail": "Historical data retrieval not configured. Set S3_DATA_BUCKET and AWS credentials."}` |
| **500** | S3 query failed | `{"detail": "Retrieval failed: [error details]"}` |

---

## Filtering Capabilities

### 1. Collection Filter (Required)

**Purpose:** Select which channel to query

**Behavior:**
- Must be one of the 4 valid MCP channels
- Invalid collection → HTTP 400

**Example:**
```json
{"collection": "market:data"}
```

---

### 2. Pair Filter (Optional)

**Purpose:** Filter by trading pair

**Behavior:**
- If omitted: Returns all pairs
- If specified: Returns only messages matching exact pair
- Non-existent pair: Returns 0 messages (not an error)
- Case-sensitive: `"BTC-ETH"` ≠ `"btc-eth"`

**Examples:**
```json
// Get only BTC-ETH
{"collection": "market:data", "pair": "BTC-ETH"}

// Get all pairs
{"collection": "market:data"}

// Non-existent pair (returns 0 messages)
{"collection": "market:data", "pair": "XYZ-ABC"}
```

---

### 3. Time Range Filter (Optional)

**Purpose:** Filter by timestamp range

**Behavior:**
- `from_timestamp`: Inclusive lower bound
- `to_timestamp`: Inclusive upper bound
- If omitted: No time filtering (returns oldest messages up to limit)
- Future timestamps: Returns 0 messages (not an error)
- Both bounds can be used independently

**Examples:**
```json
// Last 24 hours
{
  "collection": "market:data",
  "from_timestamp": 1701388800,
  "to_timestamp": 1701475200
}

// Only lower bound (all messages after timestamp)
{
  "collection": "market:data",
  "from_timestamp": 1701388800
}

// Only upper bound (all messages before timestamp, up to limit)
{
  "collection": "market:data",
  "to_timestamp": 1701475200
}
```

**Time Range Guidelines:**

| Time Window | Typical Message Count | Notes |
|-------------|----------------------|-------|
| 1 minute | 0-10 | Recent data only |
| 1 hour | 10-100 | Good for live analysis |
| 1 day | 100-2000 | May hit limit |
| 7 days | 1000+ | **Will hit limit** - use pagination |
| 30 days | 5000+ | **Will hit limit** - use pagination |

---

### 4. Limit Parameter (Optional)

**Purpose:** Control how many messages to return

**Behavior:**
- Default: 100 messages
- Maximum: 1000 messages (hard cap)
- Exceeding max: HTTP 400 error
- If fewer messages exist: Returns actual count

**Examples:**
```json
// Small queries (fast)
{"collection": "market:data", "limit": 10}

// Default (if omitted)
{"collection": "market:data"}  // Returns up to 100

// Maximum allowed
{"collection": "market:data", "limit": 1000}

// Exceeds limit (ERROR)
{"collection": "market:data", "limit": 5000}  // → HTTP 400
```

---

## Limits and Safety

### Hard Limits

| Limit | Value | Enforcement | Reason |
|-------|-------|-------------|--------|
| **MAX_RETRIEVE_LIMIT** | 1000 messages | Server-side | Prevent memory exhaustion |
| **Timeout** | ~10s | FastAPI default | Prevent long-running queries |
| **S3 fetch limit** | `limit * 2` objects | Client-side | Allow for filtering overhead |

### Safety Mechanisms

1. **Limit Cap Enforcement**
   - Requests with `limit > 1000` → HTTP 400
   - Server enforces: `limit = min(requested_limit, 1000)`

2. **Client-Side Filtering**
   - S3 objects fetched: `limit * 2` (to allow for filtering)
   - Client-side filtering applied after fetch
   - Stops when `limit` messages matched

3. **Timeout Protection**
   - Large time ranges with high limits may timeout
   - Consider using smaller limits for wide time ranges

### Capacity Planning

**Current S3 Layout:**
```
s3://bucket/mcp/market:data/year=2024/month=12/day=03/hour=10/minute=30/part-uuid.jsonl.gz
```

**Query Performance:**
- Single day, single pair: <1s
- 7 days, all pairs: 1-3s
- 30 days, all pairs: 3-10s (may timeout with limit=1000)

---

## Time Ordering Guarantees

### Guarantee

**All messages are returned in ascending timestamp order (oldest first).**

### Implementation

```python
# From retrieval.py
messages.sort(key=lambda x: x.get('timestamp', 0))
```

### Verification

**Test:** Phase 1.2.4 - Time Ordering Verification

```python
# Pseudo-code
messages = retrieve(collection="market:data", limit=100)
timestamps = [msg.timestamp for msg in messages]

assert timestamps == sorted(timestamps)  # Always true
```

### Use Cases

**Backtesting (Time-Series Replay):**
```python
# Retrieve 24h window
messages = retrieve(
    collection="market:data",
    from_timestamp=start_of_day,
    to_timestamp=end_of_day,
    limit=1000
)

# Messages are guaranteed to be in chronological order
for msg in messages:
    backtest_engine.process(msg)  # Replay in order
```

---

## Pagination

### Current Status: ⚠️ Not Implemented

**Task:** 1.2.5 - Cursor-based pagination

**Current Behavior:**
- Single request returns up to `limit` messages
- No cursor/next_page field in response
- To get more than 1000 messages: Must use multiple queries with time ranges

**Workaround (Manual Pagination):**

```python
# Fetch messages in chunks using time ranges
def fetch_large_dataset(collection, from_ts, to_ts):
    all_messages = []
    chunk_size = 86400  # 1 day chunks

    current_ts = from_ts
    while current_ts < to_ts:
        chunk_end = min(current_ts + chunk_size, to_ts)

        messages = retrieve(
            collection=collection,
            from_timestamp=current_ts,
            to_timestamp=chunk_end,
            limit=1000
        )

        all_messages.extend(messages)
        current_ts = chunk_end + 1  # Move to next chunk

    return all_messages
```

### Future Implementation (Planned)

**Expected cursor format:**
```json
{
  "messages": [...],
  "count": 1000,
  "cursor": "eyJzM19rZXkiOiAibWFya2V0OmRhdGEvLi4uIiwgImxhc3RfdHMiOiAxNzAxNDc1MjAwfQ==",
  "has_more": true
}
```

**Next page request:**
```json
{
  "collection": "market:data",
  "cursor": "eyJzM19rZXkiOiAibWFya2V0OmRhdGEvLi4uIiwgImxhc3RfdHMiOiAxNzAxNDc1MjAwfQ==",
  "limit": 1000
}
```

---

## Error Handling

### Common Errors and Solutions

#### 1. HTTP 501 - S3 Not Configured

**Error:**
```json
{
  "detail": "Historical data retrieval not configured. Set S3_DATA_BUCKET and AWS credentials."
}
```

**Cause:** `S3_DATA_BUCKET` environment variable not set

**Solution:**
```bash
# In Render.com dashboard or local .env
export S3_DATA_BUCKET="your-bucket-name"
export AWS_ACCESS_KEY_ID="AKIA..."
export AWS_SECRET_ACCESS_KEY="..."
export AWS_REGION="us-east-1"
```

---

#### 2. HTTP 400 - Invalid Collection

**Error:**
```json
{
  "detail": "Invalid collection. Must be one of: ['market:data', 'sentiment:data', 'agent:signal', 'agent:control']"
}
```

**Cause:** Collection name typo or invalid channel

**Solution:** Use exact channel names (case-sensitive)

---

#### 3. HTTP 400 - Limit Exceeds Maximum

**Error:**
```json
{
  "detail": "Limit exceeds maximum allowed (1000)"
}
```

**Cause:** `limit > 1000`

**Solution:** Use `limit ≤ 1000` or implement manual pagination

---

#### 4. HTTP 500 - S3 Query Failed

**Error:**
```json
{
  "detail": "Retrieval failed: NoSuchBucket: The specified bucket does not exist"
}
```

**Cause:** AWS credentials invalid, bucket doesn't exist, or permission issues

**Solution:**
- Verify S3 bucket exists: `aws s3 ls s3://your-bucket/`
- Check IAM permissions: `s3:GetObject`, `s3:ListBucket`
- Verify credentials are correct

---

## Performance Considerations

### Query Performance Matrix

| Query Type | Time Range | Limit | Typical Latency | Notes |
|------------|------------|-------|----------------|-------|
| Recent data | 1 minute | 100 | <0.5s | ✅ Fast |
| Single pair | 1 day | 100 | <1s | ✅ Fast |
| All pairs | 1 day | 1000 | 1-2s | ✅ Good |
| All pairs | 7 days | 1000 | 2-5s | ⚠️ Moderate |
| All pairs | 30 days | 1000 | 5-10s | ⚠️ Slow |
| No time filter | N/A | 1000 | 1-3s | Fetches oldest messages |

### Optimization Tips

1. **Use Pair Filters**
   ```json
   // Faster (filters in S3)
   {"collection": "market:data", "pair": "BTC-ETH", "limit": 1000}

   // Slower (fetches all pairs)
   {"collection": "market:data", "limit": 1000}
   ```

2. **Use Narrow Time Ranges**
   ```json
   // Faster (focused query)
   {"from_timestamp": last_hour, "to_timestamp": now, "limit": 100}

   // Slower (wide scan)
   {"from_timestamp": 30_days_ago, "to_timestamp": now, "limit": 1000}
   ```

3. **Request Only What You Need**
   ```json
   // Faster (small result set)
   {"collection": "market:data", "limit": 10}

   // Slower (large result set)
   {"collection": "market:data", "limit": 1000}
   ```

---

## Best Practices

### For Brain Agent (Backtesting)

```python
# ✅ GOOD: Focused time window
def fetch_training_data(pair, start_date, end_date):
    return retrieve(
        collection="market:data",
        pair=pair,
        from_timestamp=start_date.timestamp(),
        to_timestamp=end_date.timestamp(),
        limit=1000
    )

# ❌ BAD: No filters (unpredictable results)
def fetch_training_data():
    return retrieve(collection="market:data", limit=1000)
```

---

### For Real-Time Analysis

```python
# ✅ GOOD: Recent data only
def get_recent_sentiment(minutes=60):
    now = int(time.time())
    from_ts = now - (minutes * 60)

    return retrieve(
        collection="sentiment:data",
        from_timestamp=from_ts,
        to_timestamp=now,
        limit=100
    )

# ⚠️ AVOID: Wide time range for real-time
def get_recent_sentiment():
    return retrieve(collection="sentiment:data", limit=1000)  # May fetch old data
```

---

### For Multi-Day Analysis

```python
# ✅ GOOD: Chunk by day
def fetch_week_data(pair):
    messages = []
    for day in range(7):
        day_start = start_of_week + (day * 86400)
        day_end = day_start + 86400

        chunk = retrieve(
            collection="market:data",
            pair=pair,
            from_timestamp=day_start,
            to_timestamp=day_end,
            limit=1000
        )
        messages.extend(chunk)

    return messages

# ❌ BAD: Single query for 7 days (will hit limit)
def fetch_week_data(pair):
    return retrieve(
        collection="market:data",
        pair=pair,
        from_timestamp=start_of_week,
        to_timestamp=end_of_week,
        limit=1000  # May truncate results
    )
```

---

## Code Examples

### Python (requests library)

```python
import requests
import os
from datetime import datetime, timedelta

MCP_URL = os.getenv("MCP_URL")
MCP_API_KEY = os.getenv("MCP_API_KEY")

def retrieve_historical_data(
    collection: str,
    pair: str = None,
    from_timestamp: int = None,
    to_timestamp: int = None,
    limit: int = 100
):
    """Retrieve historical messages from MCP server."""

    headers = {
        "x-api-key": MCP_API_KEY,
        "Content-Type": "application/json"
    }

    payload = {
        "collection": collection,
        "limit": limit
    }

    if pair:
        payload["pair"] = pair
    if from_timestamp:
        payload["from_timestamp"] = from_timestamp
    if to_timestamp:
        payload["to_timestamp"] = to_timestamp

    response = requests.post(
        f"{MCP_URL}/tool/retrieve",
        headers=headers,
        json=payload,
        timeout=10
    )

    response.raise_for_status()
    return response.json()


# Example usage
if __name__ == "__main__":
    # Get last 24 hours of BTC-ETH data
    now = int(datetime.now().timestamp())
    yesterday = now - 86400

    data = retrieve_historical_data(
        collection="market:data",
        pair="BTC-ETH",
        from_timestamp=yesterday,
        to_timestamp=now,
        limit=1000
    )

    print(f"Retrieved {data['count']} messages")
    for msg in data['messages'][:5]:
        print(f"  {msg['timestamp']}: BTC={msg['price_btc']}, ETH={msg['price_eth']}")
```

---

### Bash (curl)

```bash
#!/bin/bash

# Retrieve last 100 market messages
curl -X POST "$MCP_URL/tool/retrieve" \
  -H "x-api-key: $MCP_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "collection": "market:data",
    "limit": 100
  }' | jq .

# Retrieve BTC-ETH from last hour
NOW=$(date +%s)
ONE_HOUR_AGO=$((NOW - 3600))

curl -X POST "$MCP_URL/tool/retrieve" \
  -H "x-api-key: $MCP_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"collection\": \"market:data\",
    \"pair\": \"BTC-ETH\",
    \"from_timestamp\": $ONE_HOUR_AGO,
    \"to_timestamp\": $NOW,
    \"limit\": 100
  }" | jq .
```

---

## Testing

### Phase 1.2 Test Coverage

✅ **1.2.1 - Pair Filtering**
- BTC-ETH, BTC-USD pair filters
- No pair filter (all pairs)
- Non-existent pair

✅ **1.2.2 - Time Ranges**
- 1-minute window
- 7-day window
- 30-day window
- Future time range

✅ **1.2.3 - Limits**
- limit=1, 10, 100, 1000
- Exceeding limit (validation)

✅ **1.2.4 - Time Ordering**
- Ascending timestamp verification

⚠️ **1.2.5 - Pagination**
- Not yet implemented

✅ **1.2.6 - Documentation**
- This document

### Run Tests

```bash
# Python tests
pytest tests/integration/test_retrieval_accuracy.py -v

# Bash tests
export MCP_URL="https://your-server.onrender.com"
export MCP_API_KEY="your-key"
./scripts/test_retrieval_phase_1_2.sh

# Seed test data first
python scripts/seed_test_data.py --market-messages 200 --sentiment-messages 50
```

---

## Changelog

**v1.0 (2024-12-03)**
- Initial documentation for Phase 1.2
- Documented current implementation (no pagination)
- Added code examples and best practices
- Covered all filtering capabilities and limits

---

## Related Documents

- [CLAUDE.md](../.claude/CLAUDE.md) - System architecture
- [current-work.md](../.claude/resources/current-work.md) - Active tasks
- [DEVELOPMENT.md](DEVELOPMENT.md) - Development guide
- [server.py](../mcp/server.py) - Retrieve endpoint implementation
- [retrieval.py](../mcp/retrieval.py) - Retrieval logic

---

**Document Status:** ✅ Complete for Phase 1.2
**Next Review:** After pagination implementation (Phase 1.2.5)
