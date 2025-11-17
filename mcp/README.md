# MCP Server - Message & Compute Protocol

**High-speed Redis-based pub/sub message bus for the Agentic Trading System**

> ⚠️ **Note**: This is NOT Anthropic's Model Context Protocol. This is a custom Message & Compute Protocol built on Redis Pub/Sub, FastAPI, and JSON Schema validation.

---

## 📋 Overview

The MCP Server acts as the "Central Nervous System" for a three-agent trading system:

1. **Feeder Agent** (n8n) → Ingests external data and publishes to MCP
2. **MCP Server** (this component) → Validates and routes messages via Redis
3. **Brain Agent** (Python) → Subscribes to data and executes trading logic

### Architecture

```
┌─────────────────┐        ┌─────────────────┐        ┌─────────────────┐
│  Feeder Agent   │───────▶│   MCP Server    │◀───────│   Brain Agent   │
│     (n8n)       │        │  (Redis Pub/Sub)│        │    (Python)     │
└─────────────────┘        └─────────────────┘        └─────────────────┘
                                    │
                           ┌────────┴────────┐
                           │  4 MCP Channels │
                           ├─────────────────┤
                           │ market:data     │
                           │ sentiment:data  │
                           │ agent:control   │
                           │ agent:signal    │
                           └─────────────────┘
```

---

## 🚀 Quick Start

### Using Docker Compose (Recommended)

```bash
# Start all services (Redis, Redis Commander, MCP Server)
docker-compose up -d

# Check logs
docker-compose logs -f mcp-server

# Stop services
docker-compose down
```

**Services will be available at:**
- MCP Server: `http://localhost:8080`
- Redis Commander: `http://localhost:8081`
- Redis: `localhost:6379`

### Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Start Redis (required)
docker run -d -p 6379:6379 redis:7-alpine

# Run server
python server.py

# Or with uvicorn
uvicorn server:app --host 0.0.0.0 --port 8080 --reload
```

---

## 🔌 API Endpoints

### 1. Server Information
```bash
GET /.well-known/mcp
```
Returns server metadata, available channels, and architecture info.

**Response:**
```json
{
  "name": "MCP Trading Server",
  "version": "1.0.0",
  "channels": ["market:data", "sentiment:data", "agent:control", "agent:signal"]
}
```

### 2. Publish Message
```bash
POST /tool/publish
```
Publish a validated message to an MCP channel.

**Request:**
```json
{
  "channel": "market:data",
  "message": {
    "timestamp": 1678886400,
    "pair": "BTC-ETH",
    "price_btc": 30000.0,
    "price_eth": 2000.0,
    "volume_btc": 150.5
  }
}
```

**Response:**
```json
{
  "success": true,
  "channel": "market:data",
  "subscriber_count": 2,
  "timestamp": 1678886450
}
```

### 3. List Channels
```bash
GET /tool/list_collections
```
Returns all available MCP channels.

### 4. Get Status
```bash
GET /tool/get_status
```
Returns server health, Redis status, kill-switch state, and channel subscriber counts.

**Response:**
```json
{
  "status": "healthy",
  "redis_connected": true,
  "kill_switch": {
    "active": false
  },
  "channels": {
    "market:data": 2,
    "sentiment:data": 1,
    "agent:control": 1,
    "agent:signal": 1
  }
}
```

### 5. Health Check
```bash
GET /health
```
Simple health check for monitoring.

---

## 📡 MCP Channels & Schemas

### 1. `market:data`
**Publisher:** Feeder Agent
**Subscriber:** Brain Agent

```json
{
  "timestamp": 1678886400,
  "pair": "BTC-ETH",
  "price_btc": 30000.0,
  "price_eth": 2000.0,
  "volume_btc": 150.5
}
```

### 2. `sentiment:data`
**Publisher:** Feeder Agent (RAG pipeline)
**Subscriber:** Brain Agent

```json
{
  "timestamp": 1678886405,
  "source": "Twitter",
  "score": 0.85,
  "summary": "Major institution announces Bitcoin ETF."
}
```

### 3. `agent:control`
**Publisher:** External kill-switch/monitoring
**Subscriber:** Brain Agent

```json
{
  "timestamp": 1678886410,
  "command": "EMERGENCY_HALT",
  "reason": "USDT_DEPEG_DETECTED"
}
```

**Commands:** `EMERGENCY_HALT`, `RESUME`, `PAUSE`

**Kill-Switch Logic:**
- When `EMERGENCY_HALT` is published, it is persisted to Redis key `mcp:kill_switch`
- Brain Agent must immediately publish a `FLAT` signal
- Status endpoint will show `"status": "EMERGENCY_HALT"`

### 4. `agent:signal`
**Publisher:** Brain Agent ONLY
**Subscriber:** Execution systems

```json
{
  "timestamp": 1678886415,
  "pair": "BTC-ETH",
  "action": "SHORT_SPREAD",
  "confidence": 0.78,
  "stop_loss_z": 3.0,
  "reason": "Z-Score > 2, ML Confirmed"
}
```

**Actions:** `LONG_SPREAD`, `SHORT_SPREAD`, `FLAT`, `HOLD`

---

## 🧪 Testing

Run the test suite:

```bash
# Install test dependencies
pip install -r requirements.txt

# Run all tests
pytest tests/ -v

# Run specific test
pytest tests/test_endpoints.py::TestPublishMessage -v

# Run with coverage
pytest tests/ --cov=. --cov-report=html
```

**Test Coverage:**
- ✅ Schema validation (all 4 channels)
- ✅ Publishing valid messages
- ✅ Rejecting invalid messages
- ✅ Kill-switch persistence
- ✅ Health checks
- ✅ Error handling

---

## 🔒 Safety Features

### 1. Strict Schema Validation
- All messages MUST pass JSON Schema validation before publishing
- `additionalProperties: false` prevents schema drift
- Type checking and range validation enforced

### 2. Kill-Switch Priority
- `EMERGENCY_HALT` commands are immediately persisted to Redis
- Kill-switch state is available via `/tool/get_status`
- Brain Agent can check status before every decision

### 3. Channel Isolation
- Only 4 predefined channels are allowed
- No dynamic channel creation
- Prevents unauthorized message routing

---

## 🛠️ Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `REDIS_URL` | `redis://localhost:6379` | Redis connection URL |

### Docker Compose Configuration

Edit `docker-compose.yml` to customize:
- Port mappings
- Redis persistence settings
- Resource limits
- Network configuration

---

## 📊 Monitoring

### Redis Commander
Access Redis Commander at `http://localhost:8081` to:
- View pub/sub channels
- Inspect kill-switch state (`mcp:kill_switch` key)
- Monitor message flow
- Debug connection issues

### Server Logs
```bash
# Docker Compose
docker-compose logs -f mcp-server

# Local development
# Logs appear in terminal where uvicorn is running
```

---

## 🚨 Troubleshooting

### Server won't start
```bash
# Check if Redis is running
redis-cli ping

# Check port 8080 is available
lsof -i :8080
```

### Schema validation failing
```bash
# Validate JSON against schema manually
python -c "
import json
import jsonschema

with open('schemas/market.schema.json') as f:
    schema = json.load(f)

message = {...}  # Your message
jsonschema.validate(instance=message, schema=schema)
"
```

### Kill-switch stuck
```bash
# Check kill-switch state
redis-cli GET mcp:kill_switch

# Manually clear kill-switch
redis-cli DEL mcp:kill_switch
```

---

## 📁 Project Structure

```
mcp/
├── server.py                    # FastAPI application
├── redis_client.py              # Redis pub/sub wrapper
├── schemas/
│   ├── market.schema.json       # market:data schema
│   ├── sentiment.schema.json    # sentiment:data schema
│   ├── control.schema.json      # agent:control schema
│   └── signal.schema.json       # agent:signal schema
├── tests/
│   └── test_endpoints.py        # Pytest test suite
├── Dockerfile                   # Container definition
├── docker-compose.yml           # Multi-service orchestration
├── requirements.txt             # Python dependencies
└── README.md                    # This file
```

---

## 🔗 Related Components

- **Brain Agent** (Python) - Statistical/ML trading logic → `../brain/`
- **Offline Trainer** (Python) - Model training pipeline → `../offline_trainer/`
- **Feeder Agent** (n8n) - Data ingestion workflows → *External system*

---

## 📜 License

Part of the 888.MCP Agentic Trading System.
See project root for license information.

---

## ⚠️ Important Notes

1. **DO NOT modify JSON schemas** without updating all agents
2. **DO NOT publish to undefined channels**
3. **DO NOT introduce new message fields** without architecture review
4. **ALWAYS validate messages** before publishing
5. **RESPECT the kill-switch** - it's a safety mechanism

**Failure to follow these rules may cause incorrect signals, financial risk, or broken communication between agents.**
