# Kill-Switch & Control Channel Behavior

**Document Version:** 1.0
**Last Updated:** 2025-12-03
**Audience:** Brain Agent Developers
**Phase:** 1.3 Documentation (Task 1.3.4)

---

## Table of Contents

1. [Overview](#overview)
2. [Control Channel Contract](#control-channel-contract)
3. [Kill Switch States](#kill-switch-states)
4. [Brain Agent Integration](#brain-agent-integration)
5. [API Reference](#api-reference)
6. [Error Handling](#error-handling)
7. [Examples](#examples)

---

## Overview

The **kill-switch** is a critical safety mechanism that allows external systems (monitoring, risk management, or human operators) to immediately halt all Brain agent trading activity.

### Key Concepts

- **Control Channel:** `agent:control` - Dedicated Redis pub/sub channel for control messages
- **Kill Switch:** Persistent flag stored in Redis that survives server restarts
- **Kill History:** Ordered log of all control events (EMERGENCY_HALT, RESUME, etc.)
- **Idempotent:** Multiple EMERGENCY_HALT commands are safe and result in same state

### Architecture

```
┌─────────────────┐
│ Monitoring/Ops  │
└────────┬────────┘
         │ (1) Publish EMERGENCY_HALT
         ▼
┌─────────────────┐
│   MCP Server    │ ◄── (2) Persist to Redis (mcp:kill_switch)
└────────┬────────┘
         │ (3) Pub/Sub broadcast
         ▼
┌─────────────────┐
│  Brain Agent    │ ◄── (4) Receive, check status, HALT operations
└─────────────────┘
```

---

## Control Channel Contract

### Channel Name

```
agent:control
```

### Message Schema

All control messages MUST follow this schema:

```json
{
  "schema_version": "v1",
  "timestamp": 1678886410,
  "command": "EMERGENCY_HALT",
  "reason": "USDT_DEPEG_DETECTED"
}
```

**Required Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `schema_version` | string | MUST be `"v1"` |
| `timestamp` | integer | Unix timestamp (seconds since epoch) |
| `command` | string | Control command: `"EMERGENCY_HALT"` or `"RESUME"` |
| `reason` | string | Human-readable reason for the command |

### Valid Commands

#### EMERGENCY_HALT

Immediately activates the kill switch. All Brain agent trading operations MUST cease.

**When to use:**
- Market anomaly detected (flash crash, extreme volatility)
- Stablecoin depeg detected (USDT, USDC)
- Exchange API failure or degradation
- Risk management breach (loss threshold exceeded)
- Manual intervention by operator

**Effect:**
- Kill switch set to `active: true` in Redis
- Event recorded in kill history
- Brain agent MUST stop all trading operations

#### RESUME

Clears the kill switch and resumes normal operations.

**When to use:**
- Market conditions normalized
- System health restored
- Manual approval to resume trading

**Effect:**
- Kill switch set to `active: false` in Redis
- Event recorded in kill history
- Brain agent MAY resume trading operations (after validation)

---

## Kill Switch States

### State Diagram

```
┌─────────────┐
│   INACTIVE  │ ◄────┐
│ (active:    │      │
│  false)     │      │
└──────┬──────┘      │
       │             │
       │ EMERGENCY_  │ RESUME
       │ HALT        │
       │             │
       ▼             │
┌─────────────┐      │
│   ACTIVE    │ ─────┘
│ (active:    │
│  true)      │
└─────────────┘
```

### State Properties

#### INACTIVE
- **Condition:** `kill_switch.active == false`
- **Brain Behavior:** Normal trading operations permitted
- **How to enter:** System startup OR RESUME command received

#### ACTIVE
- **Condition:** `kill_switch.active == true`
- **Brain Behavior:** ALL trading operations MUST halt immediately
- **How to enter:** EMERGENCY_HALT command received

---

## Brain Agent Integration

### Required Behavior

The Brain agent MUST implement the following behavior:

#### 1. Startup Check

On startup, ALWAYS check kill switch status before beginning trading operations:

```python
import requests

def check_kill_switch_on_startup(mcp_url: str, api_key: str) -> bool:
    """
    Check kill switch status on startup.

    Returns:
        True if safe to start (kill switch inactive)
        False if halted (kill switch active)
    """
    response = requests.get(
        f"{mcp_url}/tool/get_status",
        headers={"x-api-key": api_key}
    )

    data = response.json()

    if data["kill_switch"]["active"]:
        reason = data["kill_switch"].get("reason", "Unknown")
        print(f"⚠️  KILL SWITCH ACTIVE: {reason}")
        print("Brain agent will NOT start trading operations")
        return False

    print("✓ Kill switch inactive - safe to start")
    return True
```

#### 2. Real-Time Monitoring

Subscribe to `agent:control` channel for real-time kill switch events:

```python
import redis
import json

def monitor_control_channel(redis_url: str):
    """
    Subscribe to agent:control channel and react to kill switch events.
    """
    client = redis.from_url(redis_url, decode_responses=True)
    pubsub = client.pubsub()
    pubsub.subscribe("agent:control")

    for message in pubsub.listen():
        if message["type"] == "message":
            event = json.loads(message["data"])

            command = event.get("command")
            reason = event.get("reason", "")

            if command == "EMERGENCY_HALT":
                print(f"🚨 EMERGENCY HALT: {reason}")
                halt_all_trading()  # YOUR IMPLEMENTATION

            elif command == "RESUME":
                print(f"✓ RESUME: {reason}")
                resume_trading()  # YOUR IMPLEMENTATION
```

#### 3. Periodic Status Polling (Fallback)

In case pub/sub connection is lost, poll `/tool/get_status` every 10-30 seconds:

```python
import time

def poll_kill_switch(mcp_url: str, api_key: str, interval: int = 10):
    """
    Poll kill switch status periodically as fallback.

    Args:
        mcp_url: MCP server URL
        api_key: API key for authentication
        interval: Polling interval in seconds (default 10)
    """
    while True:
        try:
            response = requests.get(
                f"{mcp_url}/tool/get_status",
                headers={"x-api-key": api_key},
                timeout=5
            )

            data = response.json()

            if data["kill_switch"]["active"]:
                halt_all_trading()
            else:
                # Check if trading should resume
                if is_halted():
                    resume_trading()

        except Exception as e:
            print(f"Error polling kill switch: {e}")

        time.sleep(interval)
```

#### 4. Mandatory Trading Halt Behavior

When kill switch is activated, Brain agent MUST:

- ✅ **Immediately cease all new trade signal generation**
- ✅ **Stop publishing to `agent:signal` channel**
- ✅ **Preserve current state** (do NOT exit or crash)
- ✅ **Continue monitoring** control channel for RESUME
- ✅ **Log the halt event** with reason and timestamp

When kill switch is ACTIVE, Brain agent MUST NOT:

- ❌ Generate new trade signals
- ❌ Publish to `agent:signal` channel
- ❌ Execute any trading logic
- ❌ Make external API calls (exchanges, data providers)

---

## API Reference

### GET /tool/get_status

Get current kill switch status.

**Authentication:** Required (`x-api-key` header)

**Response:**

```json
{
  "status": "healthy",
  "redis_connected": true,
  "kill_switch": {
    "active": false
  },
  "channels": {
    "market:data": 0,
    "sentiment:data": 0,
    "agent:control": 1,
    "agent:signal": 0
  },
  "timestamp": 1678886400
}
```

**Status Values:**

| Status | Description |
|--------|-------------|
| `"healthy"` | System operational, kill switch inactive |
| `"EMERGENCY_HALT"` | Kill switch active, trading halted |
| `"degraded"` | Redis disconnected or other issues |

### GET /tool/kill_history

Get ordered history of control events.

**Authentication:** Required (`x-api-key` header)

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | integer | 100 | Max events to return (1-100) |

**Response:**

```json
{
  "events": [
    {
      "command": "RESUME",
      "timestamp": 1678886420,
      "reason": "TEST_COMPLETE",
      "recorded_at": 1678886420
    },
    {
      "command": "EMERGENCY_HALT",
      "timestamp": 1678886410,
      "reason": "USDT_DEPEG_DETECTED",
      "recorded_at": 1678886410
    }
  ],
  "count": 2,
  "current_status": {
    "active": false
  }
}
```

**Event Ordering:** Most recent first (reverse chronological)

**Use Cases:**

- Audit trail of control events
- Understanding recent system behavior
- Debugging unexpected halts
- Compliance and reporting

---

## Error Handling

### Connection Loss

If Brain agent loses connection to MCP server:

1. **Assume HALT state** (fail-safe)
2. **Stop all trading operations**
3. **Attempt reconnection** with exponential backoff
4. **Check kill switch status** immediately upon reconnection
5. **Resume only if** kill switch confirms inactive

### Invalid Control Messages

If Brain agent receives malformed control message:

1. **Log the error** with full message content
2. **Continue monitoring** (do NOT crash)
3. **Do NOT change current state** (invalid message ignored)

### Redis Pub/Sub Failures

If Redis pub/sub connection fails:

1. **Fall back to polling** `/tool/get_status` every 10 seconds
2. **Log the failure** for monitoring
3. **Maintain current trading state** until status confirmed
4. **Attempt pub/sub reconnection** in background

---

## Examples

### Example 1: Startup Check

```python
import requests
import sys

MCP_URL = "https://mcp-server.example.com"
API_KEY = "your-api-key"

def main():
    # Check kill switch before starting
    response = requests.get(
        f"{MCP_URL}/tool/get_status",
        headers={"x-api-key": API_KEY}
    )

    data = response.json()

    if data["kill_switch"]["active"]:
        print(f"❌ Cannot start: Kill switch active")
        print(f"   Reason: {data['kill_switch']['reason']}")
        sys.exit(1)

    print("✓ Kill switch inactive - starting Brain agent")
    start_trading()

if __name__ == "__main__":
    main()
```

### Example 2: Subscribe to Control Channel

```python
import redis
import json

REDIS_URL = "redis://localhost:6379"

def handle_control_message(message: dict):
    command = message.get("command")
    reason = message.get("reason", "")
    timestamp = message.get("timestamp")

    if command == "EMERGENCY_HALT":
        print(f"🚨 [{timestamp}] EMERGENCY HALT: {reason}")
        halt_all_trading()

    elif command == "RESUME":
        print(f"✓ [{timestamp}] RESUME: {reason}")
        resume_trading()

def subscribe_control_channel():
    client = redis.from_url(REDIS_URL, decode_responses=True)
    pubsub = client.pubsub()
    pubsub.subscribe("agent:control")

    print("✓ Subscribed to agent:control channel")

    for message in pubsub.listen():
        if message["type"] == "message":
            try:
                event = json.loads(message["data"])
                handle_control_message(event)
            except json.JSONDecodeError as e:
                print(f"⚠️  Invalid control message: {e}")

if __name__ == "__main__":
    subscribe_control_channel()
```

### Example 3: Check Kill History

```python
import requests

MCP_URL = "https://mcp-server.example.com"
API_KEY = "your-api-key"

def check_recent_halts(limit: int = 10):
    """
    Check recent kill switch events to understand system state.
    """
    response = requests.get(
        f"{MCP_URL}/tool/kill_history?limit={limit}",
        headers={"x-api-key": API_KEY}
    )

    data = response.json()

    print(f"Recent control events (last {data['count']}):")
    for event in data["events"]:
        cmd = event["command"]
        reason = event["reason"]
        ts = event["timestamp"]
        print(f"  [{ts}] {cmd}: {reason}")

    print(f"\nCurrent status: {'HALTED' if data['current_status']['active'] else 'ACTIVE'}")

if __name__ == "__main__":
    check_recent_halts()
```

### Example 4: Complete Integration

```python
import requests
import redis
import json
import threading
import time

class BrainAgent:
    def __init__(self, mcp_url: str, api_key: str, redis_url: str):
        self.mcp_url = mcp_url
        self.api_key = api_key
        self.redis_url = redis_url
        self.trading_active = False
        self.kill_switch_active = False

    def start(self):
        # Check kill switch on startup
        if not self._check_kill_switch():
            print("❌ Cannot start: Kill switch active")
            return False

        # Start control channel subscriber
        subscriber_thread = threading.Thread(
            target=self._subscribe_control_channel,
            daemon=True
        )
        subscriber_thread.start()

        # Start polling fallback
        poller_thread = threading.Thread(
            target=self._poll_kill_switch,
            daemon=True
        )
        poller_thread.start()

        # Start trading
        self.trading_active = True
        self._trading_loop()

    def _check_kill_switch(self) -> bool:
        """Check current kill switch status."""
        response = requests.get(
            f"{self.mcp_url}/tool/get_status",
            headers={"x-api-key": self.api_key}
        )
        data = response.json()
        self.kill_switch_active = data["kill_switch"]["active"]
        return not self.kill_switch_active

    def _subscribe_control_channel(self):
        """Subscribe to agent:control for real-time updates."""
        client = redis.from_url(self.redis_url, decode_responses=True)
        pubsub = client.pubsub()
        pubsub.subscribe("agent:control")

        for message in pubsub.listen():
            if message["type"] == "message":
                event = json.loads(message["data"])
                self._handle_control_event(event)

    def _handle_control_event(self, event: dict):
        """Handle control channel events."""
        command = event.get("command")
        reason = event.get("reason", "")

        if command == "EMERGENCY_HALT":
            print(f"🚨 EMERGENCY HALT: {reason}")
            self.kill_switch_active = True
            self.trading_active = False

        elif command == "RESUME":
            print(f"✓ RESUME: {reason}")
            self.kill_switch_active = False
            self.trading_active = True

    def _poll_kill_switch(self):
        """Poll kill switch status as fallback."""
        while True:
            try:
                self._check_kill_switch()
            except Exception as e:
                print(f"⚠️  Error polling kill switch: {e}")
            time.sleep(10)

    def _trading_loop(self):
        """Main trading loop."""
        while True:
            if self.trading_active and not self.kill_switch_active:
                # Generate and publish trade signals
                self._generate_signals()
            else:
                print("⏸️  Trading halted (kill switch active)")

            time.sleep(5)

    def _generate_signals(self):
        """Generate trade signals (placeholder)."""
        print("📊 Generating trade signals...")

if __name__ == "__main__":
    agent = BrainAgent(
        mcp_url="https://mcp-server.example.com",
        api_key="your-api-key",
        redis_url="redis://localhost:6379"
    )
    agent.start()
```

---

## Testing

See comprehensive test suite:
- Unit tests: `mcp/tests/test_endpoints.py::TestKillHistory`
- Integration tests: `mcp/tests/integration/test_phase_1_3.py`
- Smoke tests: `mcp/scripts/test_kill_switch.sh`

---

## Related Documentation

- [CLAUDE.md](../.claude/CLAUDE.md) - System architecture and rules
- [requirement.md](../.claude/resources/requirement.md) - Project requirements
- [current-work.md](../.claude/resources/current-work.md) - Task 1.3 details

---

## Change Log

**Version 1.0 (2025-12-03)**
- Initial documentation for Phase 1.3
- Added API reference for kill_history endpoint
- Included Python integration examples
- Documented required Brain agent behavior

---

**Document Maintained By:** MCP Development Team
**Review Frequency:** After each major feature change
**Next Review:** Phase 2 (Brain Agent Implementation)
