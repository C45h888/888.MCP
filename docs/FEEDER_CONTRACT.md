# FEEDER AGENT CONTRACT (v1.0)

**Status:** 🟢 IMMUTABLE — Production Integration Contract
**Effective Date:** 2025-12-12
**Schema Version:** v1
**Target Audience:** n8n Feeder Agent Developers

---

## 📋 Table of Contents

1. [Overview](#overview)
2. [Authentication](#authentication)
3. [Channel Specifications](#channel-specifications)
4. [Publishing Protocol](#publishing-protocol)
5. [Error Handling](#error-handling)
6. [Rate Limits](#rate-limits)
7. [Examples](#examples)
8. [Testing](#testing)
9. [Troubleshooting](#troubleshooting)

---

## Overview

The **Feeder Agent** is responsible for ingesting external market data and sentiment signals, then publishing structured messages to the MCP Server's Redis pub/sub channels.

### Responsibilities

✅ **DO:**
- Ingest price, volume, and market data from exchanges
- Perform sentiment analysis via RAG pipeline
- Publish clean, validated messages to MCP channels
- Handle rate limits with exponential backoff
- Monitor MCP server health

❌ **DO NOT:**
- Publish to channels not listed in this contract
- Modify or add fields to message schemas
- Retry invalid messages (422 errors)
- Exceed rate limits (60 req/min per API key)

### Architecture Position

```
┌─────────────────┐
│ Feeder Agent    │ ◄─── External Data (Exchanges, News, Social)
│ (n8n)           │
└────────┬────────┘
         │ POST /tool/publish
         │ (market:data, sentiment:data)
         ▼
┌─────────────────┐
│ MCP Server      │ ◄─── Redis Pub/Sub Bus
│ (FastAPI+Redis) │
└─────────────────┘
         │
         │ Subscribe to channels
         ▼
┌─────────────────┐
│ Brain Agent     │
│ (Python/ML)     │
└─────────────────┘
```

---

## Authentication

All `/tool/*` endpoints require authentication via API key.

### Header Format

```http
x-api-key: YOUR_MCP_API_KEY
```

### Security Rules

- **NEVER** commit API keys to version control
- Store keys in n8n environment variables or credentials vault
- Use separate keys for development and production
- Rotate keys quarterly (see [Key Rotation Procedure](#key-rotation))

### Testing Authentication

```bash
# ❌ FAIL - No API key (should return 401/403)
curl -i https://mcp-server.onrender.com/tool/get_status

# ✅ SUCCESS - With API key (should return 200)
curl -i -H "x-api-key: YOUR_KEY" https://mcp-server.onrender.com/tool/get_status
```

---

## Channel Specifications

The Feeder Agent MUST publish to exactly **2 channels**:

1. `market:data` - Price and volume data
2. `sentiment:data` - Sentiment analysis results

### 1. market:data Channel

**Purpose:** Real-time price and volume updates for trading pairs.

**Schema:** [mcp/schemas/v1/market.schema.json](../mcp/schemas/v1/market.schema.json)

**Required Fields:**

| Field | Type | Constraints | Example |
|-------|------|-------------|---------|
| `schema_version` | string | Must be `"v1"` | `"v1"` |
| `timestamp` | integer | Unix timestamp (seconds) | `1678886400` |
| `pair` | string | Format: `^[A-Z]+-[A-Z]+$` | `"BTC-ETH"` |
| `price_btc` | number | Minimum: 0 | `30000.0` |
| `price_eth` | number | Minimum: 0 | `2000.0` |
| `volume_btc` | number | Minimum: 0 | `150.5` |

**Additional Properties:** ❌ NOT ALLOWED (schema validation will reject)

**Example Message:**

```json
{
  "schema_version": "v1",
  "timestamp": 1678886400,
  "pair": "BTC-ETH",
  "price_btc": 30000.0,
  "price_eth": 2000.0,
  "volume_btc": 150.5
}
```

### 2. sentiment:data Channel

**Purpose:** Sentiment analysis results from RAG pipeline.

**Schema:** [mcp/schemas/v1/sentiment.schema.json](../mcp/schemas/v1/sentiment.schema.json)

**Required Fields:**

| Field | Type | Constraints | Example |
|-------|------|-------------|---------|
| `schema_version` | string | Must be `"v1"` | `"v1"` |
| `timestamp` | integer | Unix timestamp (seconds) | `1678886405` |
| `source` | string | Data source identifier | `"Twitter"` |
| `score` | number | Range: -1.0 to 1.0 | `0.85` |
| `summary` | string | One-sentence summary | `"Major institution announces Bitcoin ETF."` |

**Score Interpretation:**
- `-1.0` = Maximum negative sentiment
- `0.0` = Neutral sentiment
- `+1.0` = Maximum positive sentiment

**Example Message:**

```json
{
  "schema_version": "v1",
  "timestamp": 1678886405,
  "source": "Twitter",
  "score": 0.85,
  "summary": "Major institution announces Bitcoin ETF."
}
```

---

## Publishing Protocol

### Endpoint

```
POST https://mcp-server.onrender.com/tool/publish
```

### Request Format

```http
POST /tool/publish HTTP/1.1
Host: mcp-server.onrender.com
Content-Type: application/json
x-api-key: YOUR_MCP_API_KEY

{
  "collection": "market:data",
  "message": {
    "schema_version": "v1",
    "timestamp": 1678886400,
    "pair": "BTC-ETH",
    "price_btc": 30000.0,
    "price_eth": 2000.0,
    "volume_btc": 150.5
  }
}
```

### Response Format

**Success (HTTP 200):**

```json
{
  "success": true,
  "collection": "market:data",
  "subscriber_count": 1,
  "timestamp": 1678886401
}
```

**Failure (HTTP 4xx/5xx):** See [Error Handling](#error-handling)

---

## Error Handling

### HTTP Status Codes

| Code | Meaning | Action Required |
|------|---------|-----------------|
| **200** | Success | Continue normal operation |
| **400** | Bad Request | Fix request format, do NOT retry |
| **401** | Unauthorized | Check API key configuration |
| **403** | Forbidden | Verify API key permissions |
| **422** | Schema Validation Failed | **DO NOT RETRY** - Fix message schema |
| **429** | Rate Limit Exceeded | Exponential backoff (see below) |
| **500** | Internal Server Error | Retry up to 3 times with backoff |
| **502/503/504** | Service Unavailable | Retry up to 3 times with backoff |

### Retry Logic

**❌ NEVER RETRY:**
- `422` - Schema validation errors (invalid message structure)
- `400` - Malformed requests
- `401/403` - Authentication failures (fix configuration first)

**✅ RETRY WITH EXPONENTIAL BACKOFF:**
- `429` - Rate limit exceeded
- `500/502/503/504` - Temporary server errors

**Exponential Backoff Algorithm:**

```javascript
// n8n JavaScript pseudocode
async function publishWithRetry(message, maxRetries = 3) {
  for (let attempt = 1; attempt <= maxRetries; attempt++) {
    try {
      const response = await publishMessage(message);

      if (response.status === 200) {
        return response; // Success
      }

      if (response.status === 422 || response.status === 400) {
        // Schema validation failed - LOG ERROR AND DROP MESSAGE
        console.error(`Invalid message schema: ${JSON.stringify(message)}`);
        throw new Error('Schema validation failed - message dropped');
      }

      if (response.status === 429 || response.status >= 500) {
        // Exponential backoff: 1s, 2s, 4s
        const backoffSeconds = Math.pow(2, attempt - 1);
        console.warn(`Retry attempt ${attempt}/${maxRetries} after ${backoffSeconds}s`);
        await sleep(backoffSeconds * 1000);
        continue;
      }

      throw new Error(`Unexpected status: ${response.status}`);

    } catch (error) {
      if (attempt === maxRetries) {
        throw error; // Give up after max retries
      }
    }
  }
}
```

### Error Response Format

```json
{
  "error": "Schema validation failed",
  "detail": "Field 'schema_version' is required",
  "collection": "market:data"
}
```

---

## Rate Limits

### Current Limits (Production)

Based on [render.yaml](../render.yaml):

| Endpoint | Limit | Scope |
|----------|-------|-------|
| `/tool/publish` | **60 requests/minute** | Per API key |
| `/tool/get_status` | 120 requests/minute | Per API key |
| `/health` | 300 requests/minute | Per IP |

### Compliance Strategies

**1. Batch Publishing (Recommended)**

Instead of publishing individual messages immediately, batch them:

```
Every 1 second: Publish 1 market:data message
= 60 messages/minute (at limit)
```

**2. Request Smoothing**

Use n8n's "Wait" node to enforce minimum intervals:

```
Interval = 60 seconds / 60 messages = 1 second per message
```

**3. Rate Limit Detection**

Monitor for `429` responses and implement circuit breaker:

```javascript
let rateLimitHits = 0;

if (response.status === 429) {
  rateLimitHits++;

  if (rateLimitHits > 3) {
    // Circuit breaker - pause for 60 seconds
    await sleep(60000);
    rateLimitHits = 0;
  }
}
```

---

## Examples

### Example 1: Publish Market Data (curl)

```bash
#!/bin/bash
export MCP_URL="https://mcp-server.onrender.com"
export MCP_API_KEY="your-api-key-here"

curl -X POST "$MCP_URL/tool/publish" \
  -H "x-api-key: $MCP_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "collection": "market:data",
    "message": {
      "schema_version": "v1",
      "timestamp": '$(date +%s)',
      "pair": "BTC-ETH",
      "price_btc": 30000.0,
      "price_eth": 2000.0,
      "volume_btc": 150.5
    }
  }'
```

**Expected Output:**

```json
{"success": true, "collection": "market:data", "subscriber_count": 1}
```

### Example 2: Publish Sentiment Data (curl)

```bash
curl -X POST "$MCP_URL/tool/publish" \
  -H "x-api-key: $MCP_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "collection": "sentiment:data",
    "message": {
      "schema_version": "v1",
      "timestamp": '$(date +%s)',
      "source": "Twitter",
      "score": 0.85,
      "summary": "Major institution announces Bitcoin ETF."
    }
  }'
```

### Example 3: n8n HTTP Request Node Configuration

**Node Type:** HTTP Request

**Configuration:**

```yaml
Method: POST
URL: https://mcp-server.onrender.com/tool/publish
Authentication: None (use Headers)
Headers:
  x-api-key: {{$env.MCP_API_KEY}}
  Content-Type: application/json
Body:
  {
    "collection": "market:data",
    "message": {
      "schema_version": "v1",
      "timestamp": {{$now.unix()}},
      "pair": "BTC-ETH",
      "price_btc": {{$json.btc_price}},
      "price_eth": {{$json.eth_price}},
      "volume_btc": {{$json.btc_volume}}
    }
  }
Response Format: JSON
```

### Example 4: Health Check Before Publishing

```bash
# Always check health before starting batch publish
curl -s "$MCP_URL/health" | jq -e '.status == "ok"'

if [ $? -eq 0 ]; then
  echo "✅ MCP Server healthy - proceeding with publish"
  # ... publish messages
else
  echo "❌ MCP Server unhealthy - aborting"
  exit 1
fi
```

---

## Testing

### Pre-Production Checklist

Before deploying your Feeder Agent to production:

**1. Schema Validation Test**

```bash
# ✅ Valid message (should return 200)
curl -X POST "$MCP_URL/tool/publish" \
  -H "x-api-key: $MCP_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"collection": "market:data", "message": {...valid...}}'

# ❌ Invalid message - missing schema_version (should return 422)
curl -X POST "$MCP_URL/tool/publish" \
  -H "x-api-key: $MCP_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"collection": "market:data", "message": {"timestamp": 1678886400}}'
```

**Expected:** Valid returns 200, invalid returns 422.

**2. Authentication Test**

```bash
# ❌ No API key (should return 401/403)
curl -i -X POST "$MCP_URL/tool/publish" \
  -H "Content-Type: application/json" \
  -d '{...}'

# ✅ With API key (should return 200)
curl -i -X POST "$MCP_URL/tool/publish" \
  -H "x-api-key: $MCP_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{...}'
```

**3. Rate Limit Test**

```bash
# Send 61 requests in 60 seconds (should trigger 429 on last request)
for i in {1..61}; do
  curl -X POST "$MCP_URL/tool/publish" \
    -H "x-api-key: $MCP_API_KEY" \
    -H "Content-Type: application/json" \
    -d '{...}'

  if [ $i -lt 61 ]; then
    sleep 1
  fi
done
```

**Expected:** First 60 return 200, 61st returns 429.

**4. Retry Logic Test**

Manually simulate 500 error and verify exponential backoff:
- Attempt 1: Immediate
- Attempt 2: 1 second delay
- Attempt 3: 2 second delay
- Attempt 4: Give up

---

## Troubleshooting

### Problem: "401 Unauthorized"

**Symptoms:**
```json
{"error": "Unauthorized"}
```

**Solutions:**
1. Verify `x-api-key` header is present
2. Check API key value (no extra spaces, correct key)
3. Verify `MCP_DEV=false` in production (dev mode bypasses auth)
4. Check Render environment variables

### Problem: "422 Schema Validation Failed"

**Symptoms:**
```json
{"error": "Schema validation failed", "detail": "..."}
```

**Solutions:**
1. **DO NOT RETRY** - This is a permanent error
2. Check message structure against schema
3. Common mistakes:
   - Missing `schema_version: "v1"`
   - Wrong field types (string instead of number)
   - Extra fields not in schema
   - Negative values for `price_*` or `volume_*`
   - Invalid `pair` format (must be `SYMBOL-SYMBOL`)

### Problem: "429 Rate Limit Exceeded"

**Symptoms:**
```json
{"error": "Rate limit exceeded"}
```

**Solutions:**
1. Implement exponential backoff (see [Retry Logic](#retry-logic))
2. Reduce publish frequency (max 60/min = 1 per second)
3. Use batch publishing strategies
4. Monitor rate limit hits and adjust timing

### Problem: Messages Not Reaching Brain Agent

**Symptoms:**
- Publish returns 200
- But Brain Agent doesn't receive messages

**Debugging Steps:**

```bash
# 1. Verify Redis connection
curl -H "x-api-key: $MCP_API_KEY" "$MCP_URL/tool/get_status" | jq '.redis_connected'
# Should return: true

# 2. Check subscriber count
curl -X POST "$MCP_URL/tool/publish" \
  -H "x-api-key: $MCP_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{...}' | jq '.subscriber_count'
# Should return: 1 or more (Brain Agent subscribed)

# 3. Check MCP server logs on Render
# (Requires Render access)
```

**Solutions:**
- If `redis_connected: false` → Check Redis service on Render
- If `subscriber_count: 0` → Brain Agent not subscribed yet (expected before Brain deployment)
- If `subscriber_count: 1+` → Check Brain Agent logs

### Problem: "Connection Timeout"

**Symptoms:**
```
curl: (28) Connection timed out after 30000 milliseconds
```

**Solutions:**
1. Check MCP server status on Render dashboard
2. Verify `MCP_URL` is correct
3. Check network connectivity
4. Verify Render service is not sleeping (free tier auto-sleeps)

---

## Key Rotation

**Frequency:** Quarterly (every 90 days)

**Procedure:**

1. **Generate New Key:**
   ```bash
   # On secure workstation
   NEW_KEY=$(openssl rand -base64 32)
   echo $NEW_KEY
   ```

2. **Update Render Environment:**
   - Go to Render dashboard → mcp-server → Environment
   - Add new variable: `MCP_API_KEY_NEW=$NEW_KEY`
   - Keep old key active during transition

3. **Update Feeder Agent:**
   - Update n8n credentials with new key
   - Test with new key in staging
   - Deploy to production

4. **Verify Transition:**
   ```bash
   curl -H "x-api-key: $NEW_KEY" "$MCP_URL/tool/get_status"
   # Should return 200
   ```

5. **Deactivate Old Key:**
   - Remove `MCP_API_KEY` from Render
   - Rename `MCP_API_KEY_NEW` to `MCP_API_KEY`
   - Redeploy MCP server

---

## Contract Versioning

**Current Version:** v1.0
**Schema Version:** v1
**Last Updated:** 2025-12-12

### Breaking Changes Policy

This contract is **IMMUTABLE** for schema version `v1`. Any breaking changes require:

1. New schema version (e.g., `v2`)
2. New contract document (e.g., `FEEDER_CONTRACT_v2.md`)
3. Deprecation notice (minimum 90 days)
4. Migration guide

**Backwards Compatibility:** v1 messages will be supported indefinitely.

---

## Support & Escalation

**Documentation:**
- [MCP Server README](../mcp/README.md)
- [CLAUDE.md](../.claude/CLAUDE.md) - System architecture
- [Smoke Testing Guide](../mcp/SMOKE_TESTING.md)

**Monitoring:**
- Health endpoint: `GET /health`
- Status endpoint: `POST /tool/get_status` (requires API key)

**Incident Response:**
1. Check [TROUBLESHOOTING](#troubleshooting) section
2. Review MCP server logs on Render
3. Run smoke tests: [mcp/scripts/run_smoke_tests.sh](../mcp/scripts/run_smoke_tests.sh)
4. Escalate to system administrator if unresolved

---

## Appendix: n8n Workflow Template (Reference)

**Note:** This is a reference template. Customize for your data sources.

```json
{
  "name": "MCP Feeder - Market Data",
  "nodes": [
    {
      "name": "Schedule Trigger",
      "type": "n8n-nodes-base.cron",
      "parameters": {
        "triggerTimes": {
          "item": [
            {
              "mode": "everyMinute"
            }
          ]
        }
      }
    },
    {
      "name": "Fetch Price Data",
      "type": "n8n-nodes-base.httpRequest",
      "parameters": {
        "url": "https://api.exchange.com/ticker/BTC-ETH",
        "responseFormat": "json"
      }
    },
    {
      "name": "Transform to MCP Schema",
      "type": "n8n-nodes-base.function",
      "parameters": {
        "functionCode": "return {\n  collection: 'market:data',\n  message: {\n    schema_version: 'v1',\n    timestamp: Math.floor(Date.now() / 1000),\n    pair: 'BTC-ETH',\n    price_btc: items[0].json.btc_usd,\n    price_eth: items[0].json.eth_usd,\n    volume_btc: items[0].json.volume_24h\n  }\n};"
      }
    },
    {
      "name": "Publish to MCP",
      "type": "n8n-nodes-base.httpRequest",
      "parameters": {
        "url": "https://mcp-server.onrender.com/tool/publish",
        "method": "POST",
        "sendHeaders": true,
        "headerParameters": {
          "parameters": [
            {
              "name": "x-api-key",
              "value": "={{$env.MCP_API_KEY}}"
            }
          ]
        },
        "sendBody": true,
        "bodyParameters": {
          "parameters": []
        },
        "jsonParameters": true,
        "options": {
          "response": {
            "response": {
              "responseFormat": "json"
            }
          }
        }
      }
    }
  ],
  "connections": {
    "Schedule Trigger": {
      "main": [
        [
          {
            "node": "Fetch Price Data",
            "type": "main",
            "index": 0
          }
        ]
      ]
    },
    "Fetch Price Data": {
      "main": [
        [
          {
            "node": "Transform to MCP Schema",
            "type": "main",
            "index": 0
          }
        ]
      ]
    },
    "Transform to MCP Schema": {
      "main": [
        [
          {
            "node": "Publish to MCP",
            "type": "main",
            "index": 0
          }
        ]
      ]
    }
  }
}
```

---

**END OF FEEDER CONTRACT v1.0**
