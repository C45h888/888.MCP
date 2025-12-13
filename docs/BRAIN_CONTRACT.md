# BRAIN AGENT CONTRACT (v1.0)

**Status:** 🟢 IMMUTABLE — Production Integration Contract
**Effective Date:** 2025-12-12
**Schema Version:** v1
**Target Audience:** Python Brain Agent Developers

---

## 📋 Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Startup Protocol](#startup-protocol)
4. [Input Contract](#input-contract)
5. [Output Contract](#output-contract)
6. [Safety Contract](#safety-contract)
7. [Historical Data Retrieval](#historical-data-retrieval)
8. [Code Examples](#code-examples)
9. [Testing](#testing)
10. [Troubleshooting](#troubleshooting)

---

## Overview

The **Brain Agent** is responsible for consuming market and sentiment data from the MCP Server, performing statistical analysis and ML predictions, and publishing trading signals.

### Responsibilities

✅ **DO:**
- Subscribe to `market:data` and `sentiment:data` channels via Redis
- Maintain internal DataFrame memory (`df_market`, `df_sentiment`)
- Perform cointegration analysis and z-score calculations
- Run ML model (`brain_model.h5`) for predictions
- Publish trading signals to `agent:signal` channel
- Monitor kill-switch status and halt immediately on `EMERGENCY_HALT`
- Fetch historical data on startup for warm-up

❌ **DO NOT:**
- Subscribe to channels not listed in this contract
- Publish signals without ML confirmation
- Modify message schemas
- Ignore kill-switch commands
- Skip startup health checks

### Four-Layer Architecture

The Brain Agent **MUST** maintain this exact architecture:

```
┌─────────────────────────────────────────────────┐
│ 1. LISTENER LAYER                               │
│    - Redis subscriber (market:data, sentiment)  │
│    - Message validation                         │
│    - DataFrame updates                          │
└─────────────────┬───────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────┐
│ 2. STATISTICAL LAYER                            │
│    - Cointegration test                         │
│    - Spread calculation                         │
│    - Z-score computation                        │
└─────────────────┬───────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────┐
│ 3. PREDICTIVE LAYER                             │
│    - brain_model.h5 inference                   │
│    - Feature vector construction                │
│    - Sentiment augmentation                     │
└─────────────────┬───────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────┐
│ 4. POLICY LAYER                                 │
│    - Signal logic (z-score + ML confidence)     │
│    - Stop-loss calculation                      │
│    - Emergency halt enforcement                 │
└─────────────────┬───────────────────────────────┘
                  │
                  ▼ Publish to agent:signal
```

---

## Architecture

### System Position

```
┌─────────────────┐
│ Feeder Agent    │ ──► Publish market:data, sentiment:data
│ (n8n)           │
└─────────────────┘
         │
         ▼
┌─────────────────┐
│ MCP Server      │ ──► Redis Pub/Sub Bus
│ (FastAPI+Redis) │
└─────────────────┘
         │
         │ Subscribe to channels
         ▼
┌─────────────────┐
│ BRAIN AGENT     │ ──► Publish agent:signal
│ (Python/ML)     │
└─────────────────┘
```

### Internal Memory Model

The Brain Agent maintains two in-memory DataFrames:

**1. df_market (Last 1000 rows)**

| Column | Type | Source |
|--------|------|--------|
| `timestamp` | int64 | market:data |
| `pair` | string | market:data |
| `price_btc` | float64 | market:data |
| `price_eth` | float64 | market:data |
| `volume_btc` | float64 | market:data |
| `spread` | float64 | **Calculated** (price_btc / price_eth) |
| `z_score` | float64 | **Calculated** (rolling z-score) |

**2. df_sentiment (Last 50 rows)**

| Column | Type | Source |
|--------|------|--------|
| `timestamp` | int64 | sentiment:data |
| `source` | string | sentiment:data |
| `score` | float64 | sentiment:data |
| `summary` | string | sentiment:data |

---

## Startup Protocol

**CRITICAL:** The Brain Agent **MUST** follow this exact startup sequence.

### Step 1: Health Check

```python
import requests
import os

MCP_URL = os.getenv("MCP_URL", "https://mcp-server.onrender.com")
MCP_API_KEY = os.getenv("MCP_API_KEY")

def check_mcp_health():
    """Verify MCP server is operational before starting Brain Agent."""
    try:
        # 1. Check health endpoint
        response = requests.get(f"{MCP_URL}/health", timeout=5)
        assert response.status_code == 200, f"Health check failed: {response.status_code}"
        assert response.json()["status"] == "ok", "MCP status not OK"

        # 2. Check Redis connectivity
        headers = {"x-api-key": MCP_API_KEY}
        response = requests.post(
            f"{MCP_URL}/tool/get_status",
            headers=headers,
            timeout=5
        )
        assert response.status_code == 200, f"Status check failed: {response.status_code}"

        status = response.json()
        assert status["redis_connected"] is True, "Redis not connected"

        # 3. Check kill-switch status
        kill_switch = status.get("kill_switch", {})
        if kill_switch.get("active"):
            print(f"⚠️  WARNING: Kill-switch is ACTIVE: {kill_switch.get('reason')}")
            print("⚠️  Brain Agent will NOT publish signals until kill-switch cleared.")

        print("✅ MCP Server health check passed")
        return status

    except Exception as e:
        print(f"❌ MCP Server health check FAILED: {e}")
        raise SystemExit(1)

# Run on startup
mcp_status = check_mcp_health()
```

### Step 2: Fetch Historical Data (Warm-Up)

```python
def fetch_historical_data(collection, hours=24, pair="BTC-ETH"):
    """
    Fetch historical data from MCP Server for warm-up.

    Args:
        collection: "market:data" or "sentiment:data"
        hours: Number of hours of historical data (default: 24)
        pair: Trading pair filter (default: "BTC-ETH")

    Returns:
        List of messages (max 1000)
    """
    import time

    headers = {"x-api-key": MCP_API_KEY}

    # Calculate timestamp range
    now = int(time.time())
    from_timestamp = now - (hours * 3600)

    payload = {
        "collection": collection,
        "filters": {
            "pair": pair,
            "from_timestamp": from_timestamp,
            "to_timestamp": now
        },
        "limit": 1000  # Hard cap enforced by MCP server
    }

    response = requests.post(
        f"{MCP_URL}/tool/retrieve",
        headers=headers,
        json=payload,
        timeout=30
    )

    if response.status_code == 501:
        # S3 not configured - expected in some deployments
        print(f"⚠️  Historical data not available (S3 not configured)")
        return []

    assert response.status_code == 200, f"Retrieve failed: {response.status_code}"

    data = response.json()
    messages = data.get("messages", [])

    print(f"✅ Fetched {len(messages)} historical {collection} messages")
    return messages

# Warm-up on startup
import pandas as pd

# Fetch market data
market_history = fetch_historical_data("market:data", hours=24)
df_market = pd.DataFrame(market_history)

# Fetch sentiment data
sentiment_history = fetch_historical_data("sentiment:data", hours=24)
df_sentiment = pd.DataFrame(sentiment_history)

print(f"📊 Warm-up complete: {len(df_market)} market rows, {len(df_sentiment)} sentiment rows")
```

### Step 3: Subscribe to Redis Channels

```python
import redis
import json

# Connect to Redis
redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
redis_client = redis.from_url(redis_url)
pubsub = redis_client.pubsub()

# Subscribe to channels
pubsub.subscribe("market:data", "sentiment:data", "agent:control")
print("✅ Subscribed to Redis channels: market:data, sentiment:data, agent:control")

# Main event loop
for message in pubsub.listen():
    if message["type"] == "message":
        channel = message["channel"].decode("utf-8")
        data = json.loads(message["data"])

        if channel == "market:data":
            handle_market_data(data)
        elif channel == "sentiment:data":
            handle_sentiment_data(data)
        elif channel == "agent:control":
            handle_control_command(data)
```

---

## Input Contract

The Brain Agent **MUST** subscribe to these Redis channels:

### 1. market:data Channel

**Schema:** [mcp/schemas/v1/market.schema.json](../mcp/schemas/v1/market.schema.json)

**Message Format:**

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

**Handler Implementation:**

```python
import pandas as pd

# Global DataFrame (last 1000 rows)
df_market = pd.DataFrame()

def handle_market_data(message):
    """Process incoming market:data message."""
    global df_market

    # Validate schema version
    assert message["schema_version"] == "v1", "Unsupported schema version"

    # Append to DataFrame
    df_market = pd.concat([
        df_market,
        pd.DataFrame([message])
    ]).tail(1000)  # Keep only last 1000 rows

    # Calculate spread and z-score
    df_market["spread"] = df_market["price_btc"] / df_market["price_eth"]
    df_market["z_score"] = calculate_zscore(df_market["spread"])

    # Trigger signal generation
    generate_signal()
```

### 2. sentiment:data Channel

**Schema:** [mcp/schemas/v1/sentiment.schema.json](../mcp/schemas/v1/sentiment.schema.json)

**Message Format:**

```json
{
  "schema_version": "v1",
  "timestamp": 1678886405,
  "source": "Twitter",
  "score": 0.85,
  "summary": "Major institution announces Bitcoin ETF."
}
```

**Handler Implementation:**

```python
# Global DataFrame (last 50 rows)
df_sentiment = pd.DataFrame()

def handle_sentiment_data(message):
    """Process incoming sentiment:data message."""
    global df_sentiment

    # Validate schema version
    assert message["schema_version"] == "v1", "Unsupported schema version"

    # Append to DataFrame
    df_sentiment = pd.concat([
        df_sentiment,
        pd.DataFrame([message])
    ]).tail(50)  # Keep only last 50 rows

    print(f"📰 Sentiment update: {message['source']} score={message['score']:.2f}")
```

### 3. agent:control Channel

**Schema:** [mcp/schemas/v1/control.schema.json](../mcp/schemas/v1/control.schema.json)

**Message Format:**

```json
{
  "schema_version": "v1",
  "timestamp": 1678886410,
  "command": "EMERGENCY_HALT",
  "reason": "USDT_DEPEG_DETECTED"
}
```

**Handler Implementation:** See [Safety Contract](#safety-contract)

---

## Output Contract

The Brain Agent **MUST** publish signals to this channel:

### agent:signal Channel

**Schema:** [mcp/schemas/v1/signal.schema.json](../mcp/schemas/v1/signal.schema.json)

**Message Format:**

```json
{
  "schema_version": "v1",
  "timestamp": 1678886415,
  "pair": "BTC-ETH",
  "action": "SHORT_SPREAD",
  "confidence": 0.78,
  "stop_loss_z": 3.0,
  "reason": "Z-Score > 2, ML Confirmed"
}
```

**Required Fields:**

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `schema_version` | string | Must be `"v1"` | Schema version |
| `timestamp` | integer | Unix seconds | Signal generation time |
| `pair` | string | `^[A-Z]+-[A-Z]+$` | Trading pair |
| `action` | string | `["LONG_SPREAD", "SHORT_SPREAD", "FLAT", "HOLD"]` | Trading action |
| `confidence` | number | 0.0 to 1.0 | ML model confidence |
| `stop_loss_z` | number | >= 0 | Stop-loss threshold (z-score units) |
| `reason` | string | Non-empty | Human-readable explanation |

**Action Definitions:**

- `LONG_SPREAD` - Buy BTC, sell ETH (spread expected to widen)
- `SHORT_SPREAD` - Sell BTC, buy ETH (spread expected to narrow)
- `FLAT` - Close all positions (neutral)
- `HOLD` - Maintain current position

**Publishing Implementation:**

```python
import time

def publish_signal(action, confidence, stop_loss_z, reason):
    """
    Publish trading signal to MCP Server.

    IMPORTANT: This function MUST check kill-switch before publishing.
    """
    global EMERGENCY_HALT

    # SAFETY CHECK: Enforce kill-switch
    if EMERGENCY_HALT:
        print("⛔ KILL-SWITCH ACTIVE - Signal suppressed")
        action = "FLAT"
        reason = f"EMERGENCY_HALT: {HALT_REASON}"

    signal = {
        "schema_version": "v1",
        "timestamp": int(time.time()),
        "pair": "BTC-ETH",
        "action": action,
        "confidence": confidence,
        "stop_loss_z": stop_loss_z,
        "reason": reason
    }

    headers = {"x-api-key": MCP_API_KEY}
    payload = {
        "collection": "agent:signal",
        "message": signal
    }

    response = requests.post(
        f"{MCP_URL}/tool/publish",
        headers=headers,
        json=payload,
        timeout=5
    )

    assert response.status_code == 200, f"Publish failed: {response.status_code}"
    print(f"📡 Signal published: {action} (confidence={confidence:.2f})")
```

---

## Safety Contract

**CRITICAL:** The Brain Agent **MUST** implement emergency halt logic.

### Kill-Switch Behavior

**1. On Startup:**

```python
# Check kill-switch status during health check
status = check_mcp_health()
kill_switch = status.get("kill_switch", {})

# Global state
EMERGENCY_HALT = kill_switch.get("active", False)
HALT_REASON = kill_switch.get("reason", "Unknown")

if EMERGENCY_HALT:
    print(f"⛔ KILL-SWITCH ACTIVE: {HALT_REASON}")
    print("⛔ Brain Agent will publish FLAT signals only.")
```

**2. During Runtime:**

```python
def handle_control_command(message):
    """
    Handle agent:control messages.

    CRITICAL: This function controls emergency halt state.
    """
    global EMERGENCY_HALT, HALT_REASON

    command = message["command"]
    reason = message["reason"]

    if command == "EMERGENCY_HALT":
        print(f"🚨 EMERGENCY HALT RECEIVED: {reason}")
        EMERGENCY_HALT = True
        HALT_REASON = reason

        # Immediately publish FLAT signal
        publish_signal(
            action="FLAT",
            confidence=1.0,
            stop_loss_z=0.0,
            reason=f"EMERGENCY_HALT: {reason}"
        )

    elif command == "RESUME":
        print(f"✅ RESUME RECEIVED: {reason}")
        EMERGENCY_HALT = False
        HALT_REASON = ""

    elif command == "PAUSE":
        print(f"⏸️  PAUSE RECEIVED: {reason}")
        EMERGENCY_HALT = True
        HALT_REASON = f"PAUSED: {reason}"
```

**3. Signal Generation:**

```python
def generate_signal():
    """
    Generate trading signal based on statistical + ML analysis.

    CRITICAL: MUST respect kill-switch state.
    """
    global EMERGENCY_HALT

    # LAYER 1: Check kill-switch FIRST
    if EMERGENCY_HALT:
        publish_signal("FLAT", 1.0, 0.0, f"EMERGENCY_HALT: {HALT_REASON}")
        return

    # LAYER 2: Statistical analysis
    z_score = df_market["z_score"].iloc[-1]

    # LAYER 3: ML prediction
    features = build_feature_vector(df_market, df_sentiment)
    ml_confidence = model.predict(features)[0]

    # LAYER 4: Policy logic
    if z_score > 2.0 and ml_confidence > 0.7:
        action = "SHORT_SPREAD"
        stop_loss = 3.0
        reason = f"Z-Score={z_score:.2f} > 2, ML Confidence={ml_confidence:.2f}"
    elif z_score < -2.0 and ml_confidence > 0.7:
        action = "LONG_SPREAD"
        stop_loss = 3.0
        reason = f"Z-Score={z_score:.2f} < -2, ML Confidence={ml_confidence:.2f}"
    else:
        action = "HOLD"
        stop_loss = 0.0
        reason = f"No signal: Z-Score={z_score:.2f}, ML={ml_confidence:.2f}"

    publish_signal(action, ml_confidence, stop_loss, reason)
```

---

## Historical Data Retrieval

The Brain Agent uses `/tool/retrieve` for historical data.

### Endpoint

```
POST https://mcp-server.onrender.com/tool/retrieve
```

### Request Format

```json
{
  "collection": "market:data",
  "filters": {
    "pair": "BTC-ETH",
    "from_timestamp": 1678800000,
    "to_timestamp": 1678886400
  },
  "limit": 1000,
  "cursor": null
}
```

### Response Format

```json
{
  "messages": [
    {
      "schema_version": "v1",
      "timestamp": 1678800100,
      "pair": "BTC-ETH",
      "price_btc": 29500.0,
      "price_eth": 1950.0,
      "volume_btc": 145.2
    }
  ],
  "count": 1000,
  "cursor": "eyJrZXkiOiAibWNwL21hcmtldDpkYXRhL3llYXI9MjAyMy8uLi4ifQ=="
}
```

### Pagination

For queries returning >1000 results, use cursor-based pagination:

```python
def fetch_all_historical_data(collection, from_timestamp, to_timestamp):
    """
    Fetch all historical data using cursor pagination.

    Handles automatic pagination when results exceed 1000 messages.
    """
    all_messages = []
    cursor = None

    while True:
        payload = {
            "collection": collection,
            "filters": {
                "from_timestamp": from_timestamp,
                "to_timestamp": to_timestamp
            },
            "limit": 1000,
            "cursor": cursor
        }

        response = requests.post(
            f"{MCP_URL}/tool/retrieve",
            headers={"x-api-key": MCP_API_KEY},
            json=payload,
            timeout=30
        )

        assert response.status_code == 200, f"Retrieve failed: {response.status_code}"

        data = response.json()
        messages = data.get("messages", [])
        all_messages.extend(messages)

        # Check for next page
        cursor = data.get("cursor")
        if not cursor:
            break  # No more pages

        print(f"📄 Fetched page: {len(messages)} messages (total: {len(all_messages)})")

    return all_messages
```

### Time Range Constraints

**Maximum Window:** No hard limit (S3-backed)
**Maximum Results Per Request:** 1000 (hard cap)
**Recommended Window:** 7 days for initial warm-up

**Example: 7-Day Warm-Up**

```python
import time

# Calculate timestamp range
now = int(time.time())
seven_days_ago = now - (7 * 24 * 3600)

# Fetch with pagination
messages = fetch_all_historical_data(
    collection="market:data",
    from_timestamp=seven_days_ago,
    to_timestamp=now
)

print(f"✅ Fetched {len(messages)} messages from past 7 days")
```

---

## Code Examples

### Example 1: Complete Brain Agent Skeleton

```python
#!/usr/bin/env python3
"""
Brain Agent - Minimal Implementation
Demonstrates all required contract behaviors.
"""

import os
import time
import json
import requests
import redis
import pandas as pd
import numpy as np
from tensorflow import keras

# Configuration
MCP_URL = os.getenv("MCP_URL", "https://mcp-server.onrender.com")
MCP_API_KEY = os.getenv("MCP_API_KEY")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

# Global state
df_market = pd.DataFrame()
df_sentiment = pd.DataFrame()
EMERGENCY_HALT = False
HALT_REASON = ""

# Load ML model
model = keras.models.load_model("brain_model.h5")

def startup_protocol():
    """Execute startup protocol (health check + warm-up)."""
    # Step 1: Health check
    status = check_mcp_health()

    # Step 2: Check kill-switch
    global EMERGENCY_HALT, HALT_REASON
    kill_switch = status.get("kill_switch", {})
    EMERGENCY_HALT = kill_switch.get("active", False)
    HALT_REASON = kill_switch.get("reason", "")

    # Step 3: Warm-up
    global df_market, df_sentiment
    market_history = fetch_historical_data("market:data", hours=24)
    df_market = pd.DataFrame(market_history).tail(1000)

    sentiment_history = fetch_historical_data("sentiment:data", hours=24)
    df_sentiment = pd.DataFrame(sentiment_history).tail(50)

    print("✅ Startup protocol complete")

def main_loop():
    """Main event loop (subscribe to Redis channels)."""
    redis_client = redis.from_url(REDIS_URL)
    pubsub = redis_client.pubsub()
    pubsub.subscribe("market:data", "sentiment:data", "agent:control")

    print("🧠 Brain Agent running...")

    for message in pubsub.listen():
        if message["type"] == "message":
            channel = message["channel"].decode("utf-8")
            data = json.loads(message["data"])

            if channel == "market:data":
                handle_market_data(data)
            elif channel == "sentiment:data":
                handle_sentiment_data(data)
            elif channel == "agent:control":
                handle_control_command(data)

def handle_market_data(message):
    """Process market:data message and generate signal."""
    global df_market

    # Update DataFrame
    df_market = pd.concat([df_market, pd.DataFrame([message])]).tail(1000)

    # Calculate features
    df_market["spread"] = df_market["price_btc"] / df_market["price_eth"]
    df_market["z_score"] = calculate_zscore(df_market["spread"])

    # Generate signal
    generate_signal()

def handle_sentiment_data(message):
    """Process sentiment:data message."""
    global df_sentiment
    df_sentiment = pd.concat([df_sentiment, pd.DataFrame([message])]).tail(50)

def handle_control_command(message):
    """Process agent:control message (kill-switch)."""
    global EMERGENCY_HALT, HALT_REASON

    command = message["command"]
    reason = message["reason"]

    if command == "EMERGENCY_HALT":
        EMERGENCY_HALT = True
        HALT_REASON = reason
        publish_signal("FLAT", 1.0, 0.0, f"EMERGENCY_HALT: {reason}")
    elif command == "RESUME":
        EMERGENCY_HALT = False
        HALT_REASON = ""

def generate_signal():
    """Generate trading signal (4-layer architecture)."""
    if EMERGENCY_HALT:
        publish_signal("FLAT", 1.0, 0.0, f"EMERGENCY_HALT: {HALT_REASON}")
        return

    # Statistical layer
    z_score = df_market["z_score"].iloc[-1]

    # Predictive layer
    features = build_feature_vector(df_market, df_sentiment)
    ml_confidence = model.predict(features)[0][0]

    # Policy layer
    if z_score > 2.0 and ml_confidence > 0.7:
        action = "SHORT_SPREAD"
        stop_loss = 3.0
        reason = f"Z={z_score:.2f}>2, ML={ml_confidence:.2f}"
    elif z_score < -2.0 and ml_confidence > 0.7:
        action = "LONG_SPREAD"
        stop_loss = 3.0
        reason = f"Z={z_score:.2f}<-2, ML={ml_confidence:.2f}"
    else:
        action = "HOLD"
        stop_loss = 0.0
        reason = f"No signal: Z={z_score:.2f}, ML={ml_confidence:.2f}"

    publish_signal(action, ml_confidence, stop_loss, reason)

def publish_signal(action, confidence, stop_loss_z, reason):
    """Publish signal to MCP Server."""
    signal = {
        "schema_version": "v1",
        "timestamp": int(time.time()),
        "pair": "BTC-ETH",
        "action": action,
        "confidence": confidence,
        "stop_loss_z": stop_loss_z,
        "reason": reason
    }

    response = requests.post(
        f"{MCP_URL}/tool/publish",
        headers={"x-api-key": MCP_API_KEY},
        json={"collection": "agent:signal", "message": signal},
        timeout=5
    )

    assert response.status_code == 200
    print(f"📡 {action} (conf={confidence:.2f})")

def calculate_zscore(series, window=100):
    """Calculate rolling z-score."""
    mean = series.rolling(window).mean()
    std = series.rolling(window).std()
    return (series - mean) / std

def build_feature_vector(df_market, df_sentiment):
    """Build feature vector for ML model."""
    # Extract latest features
    z_score = df_market["z_score"].iloc[-1]
    volume = df_market["volume_btc"].iloc[-1]
    sentiment_score = df_sentiment["score"].mean() if len(df_sentiment) > 0 else 0.0

    # Combine into feature vector
    features = np.array([[z_score, volume, sentiment_score]])
    return features

def check_mcp_health():
    """Check MCP Server health."""
    response = requests.get(f"{MCP_URL}/health", timeout=5)
    assert response.status_code == 200

    response = requests.post(
        f"{MCP_URL}/tool/get_status",
        headers={"x-api-key": MCP_API_KEY},
        timeout=5
    )
    assert response.status_code == 200
    return response.json()

def fetch_historical_data(collection, hours=24):
    """Fetch historical data from MCP Server."""
    now = int(time.time())
    from_timestamp = now - (hours * 3600)

    response = requests.post(
        f"{MCP_URL}/tool/retrieve",
        headers={"x-api-key": MCP_API_KEY},
        json={
            "collection": collection,
            "filters": {"from_timestamp": from_timestamp, "to_timestamp": now},
            "limit": 1000
        },
        timeout=30
    )

    if response.status_code == 501:
        return []  # S3 not configured

    assert response.status_code == 200
    return response.json().get("messages", [])

if __name__ == "__main__":
    startup_protocol()
    main_loop()
```

### Example 2: Backtesting Support

```python
def backtest_historical_replay(from_timestamp, to_timestamp):
    """
    Replay historical data for backtesting.

    Simulates real-time message processing in historical order.
    """
    # Fetch all historical data
    market_messages = fetch_all_historical_data(
        "market:data",
        from_timestamp,
        to_timestamp
    )

    sentiment_messages = fetch_all_historical_data(
        "sentiment:data",
        from_timestamp,
        to_timestamp
    )

    # Merge and sort by timestamp
    all_messages = [
        {"type": "market", "data": m} for m in market_messages
    ] + [
        {"type": "sentiment", "data": m} for m in sentiment_messages
    ]

    all_messages.sort(key=lambda x: x["data"]["timestamp"])

    # Replay in order
    signals = []

    for msg in all_messages:
        if msg["type"] == "market":
            handle_market_data(msg["data"])

            # Capture signal
            signal = get_latest_signal()
            if signal:
                signals.append(signal)

        elif msg["type"] == "sentiment":
            handle_sentiment_data(msg["data"])

    # Evaluate performance
    performance = evaluate_signals(signals)
    return performance

def evaluate_signals(signals):
    """Evaluate backtest performance (Sortino Ratio, etc.)."""
    # Calculate returns from signals
    returns = []

    for signal in signals:
        if signal["action"] == "SHORT_SPREAD":
            # Simulate spread narrowing profit
            returns.append(0.02)  # 2% profit (example)
        elif signal["action"] == "LONG_SPREAD":
            # Simulate spread widening profit
            returns.append(0.015)  # 1.5% profit (example)

    # Calculate Sortino Ratio
    mean_return = np.mean(returns)
    downside_std = np.std([r for r in returns if r < 0])
    sortino = mean_return / downside_std if downside_std > 0 else 0

    return {
        "total_signals": len(signals),
        "mean_return": mean_return,
        "sortino_ratio": sortino
    }
```

---

## Testing

### Pre-Production Checklist

**1. Startup Protocol Test**

```bash
# Verify health check works
python brain_agent.py
# Should print: "✅ Startup protocol complete"
```

**2. Kill-Switch Test**

```bash
# Activate kill-switch
curl -X POST "$MCP_URL/tool/publish" \
  -H "x-api-key: $MCP_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "collection": "agent:control",
    "message": {
      "schema_version": "v1",
      "timestamp": '$(date +%s)',
      "command": "EMERGENCY_HALT",
      "reason": "TEST"
    }
  }'

# Verify Brain Agent publishes FLAT signal
# Check logs for: "⛔ KILL-SWITCH ACTIVE: TEST"
```

**3. Historical Data Test**

```python
# Test retrieval
messages = fetch_historical_data("market:data", hours=1)
assert len(messages) > 0, "No historical data available"
assert messages[0]["schema_version"] == "v1"
```

**4. Signal Publishing Test**

```python
# Test signal publishing
publish_signal("HOLD", 0.5, 0.0, "Test signal")
# Should print: "📡 HOLD (conf=0.50)"
```

---

## Troubleshooting

### Problem: "No historical data available"

**Symptoms:**
- `fetch_historical_data()` returns empty list
- HTTP 501 response from `/tool/retrieve`

**Solutions:**
1. Check if `S3_DATA_BUCKET` is configured on MCP Server
2. If not configured: This is expected - Brain Agent will warm up from real-time messages
3. If configured: Verify archiver is running and has flushed data to S3

### Problem: Kill-switch not working

**Symptoms:**
- `EMERGENCY_HALT` command received but signals still published

**Debugging:**

```python
# Add debug logging to handle_control_command()
print(f"DEBUG: EMERGENCY_HALT={EMERGENCY_HALT}")
print(f"DEBUG: HALT_REASON={HALT_REASON}")

# Verify generate_signal() checks EMERGENCY_HALT first
def generate_signal():
    print(f"DEBUG: Entering generate_signal(), EMERGENCY_HALT={EMERGENCY_HALT}")
    if EMERGENCY_HALT:
        print("DEBUG: Kill-switch active, publishing FLAT")
        # ...
```

### Problem: Redis connection timeout

**Symptoms:**
```
redis.exceptions.ConnectionError: Error connecting to Redis
```

**Solutions:**
1. Verify `REDIS_URL` environment variable
2. Check Redis service status on Render
3. Test connection:
   ```bash
   redis-cli -u "$REDIS_URL" PING
   # Should return: PONG
   ```

---

## Contract Versioning

**Current Version:** v1.0
**Schema Version:** v1
**Last Updated:** 2025-12-12

### Breaking Changes Policy

This contract is **IMMUTABLE** for schema version `v1`. Any breaking changes require:

1. New schema version (e.g., `v2`)
2. New contract document (e.g., `BRAIN_CONTRACT_v2.md`)
3. Deprecation notice (minimum 90 days)
4. Migration guide

**Backwards Compatibility:** v1 messages will be supported indefinitely.

---

## Support & Escalation

**Documentation:**
- [MCP Server README](../mcp/README.md)
- [CLAUDE.md](../.claude/CLAUDE.md) - System architecture
- [FEEDER_CONTRACT.md](FEEDER_CONTRACT.md) - Feeder agent contract

**Monitoring:**
- Health endpoint: `GET /health`
- Status endpoint: `POST /tool/get_status` (requires API key)
- Kill history: `POST /tool/kill_history` (requires API key)

---

**END OF BRAIN CONTRACT v1.0**
