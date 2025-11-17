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

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `REDIS_URL` | No | `redis://localhost:6379` | Redis connection URL |
| `MCP_DEV` | No | `false` | Set to `true` to disable authentication (dev mode) |
| `MCP_API_KEY` | Production only | - | API key for production authentication |
| `S3_DATA_BUCKET` | No | - | S3 bucket name for historical data storage (enables `/tool/retrieve`) |
| `AWS_ACCESS_KEY_ID` | No | - | AWS credentials for S3 access (standard boto3 env var) |
| `AWS_SECRET_ACCESS_KEY` | No | - | AWS credentials for S3 access (standard boto3 env var) |
| `AWS_REGION` | No | `us-east-1` | AWS region for S3 bucket |

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

**Production Mode:**
```bash
# Set API key
export MCP_API_KEY="your-secure-api-key-here"

# Start services
docker-compose up -d

# All requests must include x-api-key header
curl -H "x-api-key: your-secure-api-key-here" http://localhost:8080/tool/get_status
```

**Dev Mode:**
```bash
# Enable dev mode (no authentication required)
export MCP_DEV=true
docker-compose up -d
```

### Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Start Redis (required)
docker run -d -p 6379:6379 redis:7-alpine

# Run server
MCP_DEV=true python server.py

# Or with API key
MCP_API_KEY=your-key python server.py

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

### Authentication

All `/tool/*` endpoints require authentication in production mode:

**Dev Mode (MCP_DEV=true):**
```bash
# No authentication required
curl http://localhost:8080/tool/list_collections
```

**Production Mode:**
```bash
# Must include x-api-key header
curl -H "x-api-key: your-api-key" http://localhost:8080/tool/list_collections

# Without API key returns 401
curl http://localhost:8080/tool/list_collections
# Response: {"detail": "Invalid or missing API key"}
```

**Note:** Discovery endpoints (`/.well-known/mcp`, `/health`) do not require authentication.

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
    "schema_version": "v1",
    "timestamp": 1678886400,
    "pair": "BTC-ETH",
    "price_btc": 30000.0,
    "price_eth": 2000.0,
    "volume_btc": 150.5
  }
}
```

**Example with authentication:**
```bash
curl -X POST http://localhost:8080/tool/publish \
  -H "Content-Type: application/json" \
  -H "x-api-key: your-api-key" \
  -d '{"channel":"market:data","message":{"schema_version":"v1","timestamp":1678886400,"pair":"BTC-ETH","price_btc":30000.0,"price_eth":2000.0,"volume_btc":150.5}}'
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

### 6. Retrieve Historical Data
```bash
POST /tool/retrieve
```
Retrieve historical messages from S3 storage with timestamp and pair filtering.

**Note:** Requires `S3_DATA_BUCKET` and AWS credentials to be configured. Returns 501 if S3 not configured.

**Request:**
```json
{
  "collection": "market:data",
  "pair": "BTC-ETH",
  "from_timestamp": 1678886000,
  "to_timestamp": 1678886500,
  "limit": 100
}
```

**Parameters:**
- `collection` (required): Channel name (`market:data`, `sentiment:data`, etc.)
- `pair` (optional): Filter by trading pair (e.g., `BTC-ETH`)
- `from_timestamp` (optional): Unix timestamp - start of time range
- `to_timestamp` (optional): Unix timestamp - end of time range
- `limit` (optional): Maximum results to return (default: 100, max: 1000)

**Example:**
```bash
curl -X POST http://localhost:8080/tool/retrieve \
  -H "Content-Type: application/json" \
  -H "x-api-key: your-api-key" \
  -d '{
    "collection": "market:data",
    "pair": "BTC-ETH",
    "from_timestamp": 1678886000,
    "to_timestamp": 1678886500,
    "limit": 50
  }'
```

**Response (S3 configured):**
```json
{
  "messages": [
    {
      "schema_version": "v1",
      "timestamp": 1678886400,
      "pair": "BTC-ETH",
      "price_btc": 30000.0,
      "price_eth": 2000.0,
      "volume_btc": 150.5
    }
  ],
  "count": 1,
  "collection": "market:data",
  "filters": {
    "pair": "BTC-ETH",
    "from_timestamp": 1678886000,
    "to_timestamp": 1678886500,
    "limit": 50
  }
}
```

**Response (S3 not configured):**
```json
{
  "detail": "Historical data retrieval not configured. Set S3_DATA_BUCKET and AWS credentials."
}
```
Status: 501 Not Implemented

**Safety Limits:**
- Maximum `limit`: 1000 messages per request
- Enforces pagination to prevent memory issues
- Validates collection names against allowed channels

### 7. Search RAG Knowledge Base
```bash
POST /tool/search_rag
```
Search historical data using semantic similarity (placeholder for future vector DB integration).

**Note:** Currently returns 501 Not Implemented. Reserved for future integration with Pinecone, Weaviate, or similar vector databases.

**Request:**
```json
{
  "query": "What was BTC price when sentiment was bullish?",
  "k": 5
}
```

**Parameters:**
- `query` (required): Natural language search query
- `k` (optional): Number of results to return (default: 5)

**Response:**
```json
{
  "detail": "RAG search not yet implemented. Future integration planned for vector database (Pinecone/Weaviate)."
}
```
Status: 501 Not Implemented

---

## 📡 MCP Channels & Schemas

### 1. `market:data`
**Publisher:** Feeder Agent
**Subscriber:** Brain Agent

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

### 2. `sentiment:data`
**Publisher:** Feeder Agent (RAG pipeline)
**Subscriber:** Brain Agent

```json
{
  "schema_version": "v1",
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
  "schema_version": "v1",
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
  "schema_version": "v1",
  "timestamp": 1678886415,
  "pair": "BTC-ETH",
  "action": "SHORT_SPREAD",
  "confidence": 0.78,
  "stop_loss_z": 3.0,
  "reason": "Z-Score > 2, ML Confirmed"
}
```

**Actions:** `LONG_SPREAD`, `SHORT_SPREAD`, `FLAT`, `HOLD`

### Schema Versioning

All messages MUST include `"schema_version": "v1"` field. Messages without this field or with incorrect version will be rejected with 400 error.

Schemas are located in `schemas/v1/` directory and enforce strict validation with `additionalProperties: false`.

---

## 🧪 Testing

### Unit Tests

Run the unit test suite:

```bash
# Install test dependencies
pip install -r requirements.txt

# Run all tests
pytest tests/ -v

# Run only unit tests
pytest tests/test_endpoints.py -v

# Run with coverage
pytest tests/ --cov=. --cov-report=html
```

### Integration Tests

Integration tests require docker-compose services to be running:

```bash
# Start services
docker-compose up -d

# Run integration tests
pytest tests/integration/ -v

# Stop services
docker-compose down
```

**CI/CD:**

GitHub Actions workflow automatically runs all tests on every push to `main`, `claude/**`, or `develop` branches.

The CI pipeline includes:
- Linting with flake8
- Unit tests
- Integration tests with docker-compose
- Docker build validation

See `.github/workflows/ci.yml` for details.

**Test Coverage:**
- ✅ Schema validation (all 4 channels)
- ✅ Publishing valid messages
- ✅ Rejecting invalid messages
- ✅ Kill-switch persistence
- ✅ Health checks
- ✅ Error handling
- ✅ Schema versioning enforcement
- ✅ API key authentication
- ✅ End-to-end docker-compose integration

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

### 4. Schema Versioning
- All messages require `schema_version` field
- Currently only `v1` is supported
- Prevents schema drift and breaking changes

---

## 🛠️ Configuration

### Environment Variables

See the full table in the Quick Start section above.

### S3 Historical Data Storage (Optional)

To enable historical data retrieval via `/tool/retrieve`, configure S3 storage:

**1. Create S3 Bucket:**
```bash
# Using AWS CLI
aws s3 mb s3://my-mcp-data-bucket --region us-east-1
```

**2. Set Environment Variables:**
```bash
export S3_DATA_BUCKET="my-mcp-data-bucket"
export AWS_ACCESS_KEY_ID="your-access-key"
export AWS_SECRET_ACCESS_KEY="your-secret-key"
export AWS_REGION="us-east-1"
```

**3. Update Docker Compose:**
```yaml
# docker-compose.yml
services:
  mcp-server:
    environment:
      - S3_DATA_BUCKET=my-mcp-data-bucket
      - AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID}
      - AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY}
      - AWS_REGION=us-east-1
```

**4. Verify Configuration:**
```bash
# Test retrieval endpoint
curl -X POST http://localhost:8080/tool/retrieve \
  -H "Content-Type: application/json" \
  -H "x-api-key: your-api-key" \
  -d '{"collection":"market:data","limit":10}'

# Should return data if S3 configured, or 501 if not
```

**S3 Bucket Structure:**

The retrieval module expects messages stored in S3 with this structure:
```
s3://my-mcp-data-bucket/
  market:data/
    2024/03/
      btc-eth-20240315.json
      btc-eth-20240316.json
  sentiment:data/
    2024/03/
      sentiment-20240315.json
```

**Note:** Data archival to S3 must be handled by your data pipeline (external to MCP Server). The retrieval endpoint only reads from S3.

### Docker Compose Configuration

Edit `docker-compose.yml` to customize:
- Port mappings
- Redis persistence settings
- Resource limits
- Network configuration
- S3 credentials (see above)

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

# Check Docker logs
docker-compose logs mcp-server
```

### Schema validation failing
```bash
# Validate JSON against schema manually
python -c "
import json
import jsonschema

with open('schemas/v1/market.schema.json') as f:
    schema = json.load(f)

message = {
    'schema_version': 'v1',
    'timestamp': 1678886400,
    'pair': 'BTC-ETH',
    'price_btc': 30000.0,
    'price_eth': 2000.0,
    'volume_btc': 150.5
}
jsonschema.validate(instance=message, schema=schema)
print('Valid!')
"
```

**Common schema errors:**
- Missing `schema_version` field → Add `"schema_version": "v1"`
- Wrong schema version → Use `"v1"`, not `"v2"` or other versions
- Extra fields → Remove fields not in schema (schemas use `additionalProperties: false`)
- Wrong data types → Check timestamps are integers, prices are floats, etc.

### Kill-switch stuck
```bash
# Check kill-switch state
redis-cli GET mcp:kill_switch

# View the JSON content
redis-cli GET mcp:kill_switch | python -m json.tool

# Manually clear kill-switch (use with caution!)
redis-cli DEL mcp:kill_switch
```

### Retrieval endpoint returns 501
This is expected when S3 is not configured.

**Fix:**
```bash
# Set required environment variables
export S3_DATA_BUCKET="your-bucket-name"
export AWS_ACCESS_KEY_ID="your-key"
export AWS_SECRET_ACCESS_KEY="your-secret"

# Restart server
docker-compose restart mcp-server

# Or for local development
python server.py
```

**Verify S3 credentials:**
```bash
# Test AWS credentials
aws s3 ls s3://your-bucket-name/

# Test from Python
python -c "
import boto3
s3 = boto3.client('s3')
response = s3.list_objects_v2(Bucket='your-bucket-name', MaxKeys=1)
print('S3 connection OK!')
"
```

### Authentication failing (401 errors)
```bash
# Check if dev mode is enabled
curl http://localhost:8080/health
# If this works but /tool/get_status returns 401, authentication is required

# Enable dev mode (development only!)
export MCP_DEV=true
docker-compose restart mcp-server

# Or set API key
export MCP_API_KEY="your-secure-key"
docker-compose restart mcp-server

# Test with API key
curl -H "x-api-key: your-secure-key" http://localhost:8080/tool/get_status
```

### Integration tests failing
```bash
# Make sure services are running
docker-compose up -d

# Wait for services to be ready
sleep 5

# Run tests
pytest tests/integration/ -v

# Check service logs if failing
docker-compose logs redis
docker-compose logs mcp-server
```

---

## 📁 Project Structure

```
mcp/
├── server.py                    # FastAPI application
├── redis_client.py              # Redis pub/sub wrapper
├── retrieval.py                 # S3 historical data retrieval
├── schemas/
│   └── v1/
│       ├── market.schema.json       # market:data schema
│       ├── sentiment.schema.json    # sentiment:data schema
│       ├── control.schema.json      # agent:control schema
│       └── signal.schema.json       # agent:signal schema
├── tests/
│   ├── test_endpoints.py        # Unit tests
│   └── integration/
│       └── test_integration.py  # Docker-based integration tests
├── Dockerfile                   # Container definition
├── docker-compose.yml           # Multi-service orchestration
├── requirements.txt             # Python dependencies
└── README.md                    # This file

.github/
└── workflows/
    └── ci.yml                   # GitHub Actions CI/CD pipeline
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
