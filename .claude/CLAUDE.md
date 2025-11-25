# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

This file defines the complete system context, architectural boundaries, operational rules, and tool/governance guidelines for Claude Code.
Claude MUST follow these instructions at all times when working inside this repository.

---

# 📌 1. SYSTEM OVERVIEW

This project consists of **three independent agents** connected through a high-speed message bus (the MCP Server). The two architectural documents define strict roles:

### 1. The **Feeder Agent (Agent 1 — n8n)**
*The "Senses" of the system.*
Responsible for ingesting external data (price, volume, news, sentiment) and publishing clean structured messages to MCP.

### 2. The **MCP Server (Redis)**
*The "Central Nervous System."*
Acts as a high-speed pub/sub message bus through defined channels:
- `market:data`
- `sentiment:data`
- `agent:control`
- `agent:signal`

### 3. The **Brain Agent (Agent 2 — Python/Claude Code)**
*The "Cerebral Cortex."*
Subscribes to MCP data, performs statistical & ML calculations, and publishes final trade signals.

Claude Code **is responsible ONLY for the Brain Agent code**, MCP server utilities, testing infrastructure, and developer-side automations.

Claude Code must NOT attempt to build the n8n workflows except when explicitly asked.

---

# 📌 2. MCP SERVER CONTRACT (CRITICAL)

Claude MUST ALWAYS respect the **exact JSON schemas** specified in the architecture documents.
These schemas define the communication protocol between all agents.

### **2.1 market:data**
Published by Feeder.
Subscribed by Brain.

```json
{
  "timestamp": 1678886400,
  "pair": "BTC-ETH",
  "price_btc": 30000.0,
  "price_eth": 2000.0,
  "volume_btc": 150.5
}
```

### **2.2 sentiment:data**
Published by Feeder's RAG pipeline.
Subscribed by Brain.

```json
{
  "timestamp": 1678886405,
  "source": "Twitter",
  "score": 0.85,
  "summary": "Major institution announces Bitcoin ETF."
}
```

### **2.3 agent:control**
Published by external kill-switch or monitoring system.
Subscribed by Brain.

```json
{
  "timestamp": 1678886410,
  "command": "EMERGENCY_HALT",
  "reason": "USDT_DEPEG_DETECTED"
}
```

### **2.4 agent:signal**
Published ONLY by the Brain after statistical + ML evaluation.

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

---

# 📌 3. CLAUDE CODE — RESPONSIBILITIES

Claude Code is responsible for:

### ✔ Building the Core MCP Server
- Redis pub/sub wrapper (`redis_client.py`)
- Health and status endpoints
- Channel schema validation (strict, version-enforced)
- Logging, error-handling, and safe publishing utilities
- **Historical data retrieval** (`retrieval.py`) - S3/Parquet/JSONL with cursor pagination
- **Background uploader/archiver** (`uploader/archiver.py`) - Batched S3 uploads with local fallback
- **Parquet tooling** (`tooling/s3_parquet.py`) - Streaming reader with JSONL fallback
- **RAG endpoint placeholder** (`/tool/search_rag`) - Vector DB integration hooks
- Developer tooling scripts (`scripts/seed_minio.py`)
- CI/CD workflows (GitHub Actions with MinIO-based S3 testing)
- Deployment manifests (`render.yaml`, `docker-compose*.yml`)

### ✔ Building the Brain Agent (Python)
The Brain has four internal layers (from architecture):
1. **Listener Layer** (Redis subscriber)
2. **Statistical Layer** (Cointegration, spread, z-score)
3. **Predictive Layer** (ML model — brain_model.h5)
4. **Policy Layer** (Signal logic)

Claude must preserve this exact architecture whenever modifying code.

### ✔ Building the Offline Trainer (Python)
- Walk-Forward Analysis (WFA)
- Sentiment-augmented feature vector
- Sortino Ratio evaluation
- Producing the final `brain_model.h5`

---

# 📌 4. CLAUDE CODE — HARD RULES

These rules override all other instructions.

## 🟥 DO NOT

❌ Modify JSON schemas in `schemas/v1/` (breaks all agents)
❌ Publish to MCP channels not specified (only 4 channels allowed)
❌ Generate n8n workflow files automatically (Feeder is external)
❌ Introduce new fields into MCP messages (violates schema contract)
❌ Build trading logic outside the Policy Layer (Brain architecture is sacred)
❌ Use any model other than the offline-trained `brain_model.h5`
❌ Delete archived data from S3 or local storage (append-only, no deletion)
❌ Change channel names (`market:data`, `sentiment:data`, `agent:control`, `agent:signal`)
❌ Skip schema_version field in messages (all messages MUST have `"schema_version": "v1"`)

## 🟩 MUST

✔ Validate all MCP messages against schemas before publish
✔ Keep Brain Agent functions isolated and testable
✔ Maintain internal DataFrames exactly as defined:
  - `df_market` last 1000 rows
  - `df_sentiment` last 50 rows

✔ Enforce kill switch logic immediately on `EMERGENCY_HALT`
✔ Follow statistical → predictive → policy sequence
✔ Ask the user before generating destructive or irreversible files
✔ Document every major component inside `/docs`

---

# 📌 5. REPOSITORY STRUCTURE CLAUDE MUST FOLLOW

Claude Code should maintain this structure during development:

```
/mcp/
    server.py                   # FastAPI MCP server with pub/sub endpoints
    redis_client.py             # Redis pub/sub wrapper
    retrieval.py                # S3 historical data retrieval with Parquet support
    uploader/
        archiver.py             # Background worker for batched S3 uploads
    tooling/
        s3_parquet.py           # Parquet/JSONL reader with streaming
    schemas/
        v1/                     # Schema versioning (all messages require v1)
            market.schema.json
            sentiment.schema.json
            control.schema.json
            signal.schema.json
    tests/
        test_endpoints.py       # Unit tests for server endpoints
        test_uploader.py        # Unit tests for archiver
        test_parquet.py         # Unit tests for Parquet/JSONL reading
        integration/
            test_integration.py
            test_s3_retrieve.py # MinIO-based S3 integration tests
    docker-compose.yml          # Production: Redis + MCP server
    docker-compose.ci.yml       # CI: Redis + MinIO + MCP server
    Dockerfile
    requirements.txt

/brain/                         # ⚠️ NOT YET IMPLEMENTED
    listener.py
    stat_layer.py
    predictive_layer.py
    policy_layer.py
    publish.py
    memory/
        df_market.pkl
        df_sentiment.pkl
    models/
        brain_model.h5

/offline_trainer/               # ⚠️ NOT YET IMPLEMENTED
    trainer.py
    feature_builder.py
    wfa.py
    evaluation.py

/scripts/
    seed_minio.py               # MinIO test data seeder for CI

.github/
    workflows/
        ci.yml                  # Main CI: lint, unit, integration, Docker build
        ci-s3.yml               # S3 integration tests with MinIO

render.yaml                     # Render.com deployment manifest
```

---

# 📌 6. HOW CLAUDE SHOULD RESPOND TO USER REQUESTS

⭐ If the user requests:

**"Modify Brain logic"**
→ Claude must update only statistical, predictive, or policy-layer code.

**"Change MCP schema"**
→ Claude must refuse and warn this will break both agents.

**"Add new features"**
→ Claude must check:
- Does it break schemas?
- Does it keep the architecture intact?
- Does it violate the kill-switch contract?

**"Build the MCP server"**
→ Claude can generate Python code, tests, Dockerfiles, or dev tools — but must always follow the architecture.

---

# 📌 7. SAFETY & VALIDATION RULES

Claude must enforce:

### ✔ Strict JSON schema validation
- Reject malformed messages.
- Do NOT publish if validation fails.

### ✔ Kill switch priority
- If `EMERGENCY_HALT = True`:
  - The Brain must publish a FLAT signal immediately.

### ✔ No uncontrolled trade decisions
- All signals must follow the z-score & ML logic specified.

---

# 📌 8. DEVELOPMENT MODE RULES

When Claude Code is writing code:

- Use type hints
- Break into small testable modules
- Always create a `/tests` directory
- Use `pytest` for testing
- Prefer readability over cleverness
- Include docstrings with clear purpose statements

---

# 📌 9. COMMON DEVELOPMENT COMMANDS

### Testing

```bash
# Unit tests (fast, no external dependencies)
cd /home/user/888.MCP/mcp
pytest tests/test_endpoints.py -v
pytest tests/test_uploader.py -v
pytest tests/test_parquet.py -v

# Integration tests (requires docker-compose)
docker-compose up -d
pytest tests/integration/ -v
docker-compose down

# S3/MinIO integration tests
docker-compose -f docker-compose.ci.yml up -d
python scripts/seed_minio.py
pytest tests/integration/test_s3_retrieve.py -v
docker-compose -f docker-compose.ci.yml down -v

# Run single test
pytest tests/test_endpoints.py::TestPublishEndpoint::test_publish_valid_market_data -v
```

### Local Development

```bash
# Start MCP server in dev mode (no auth)
cd /home/user/888.MCP/mcp
export MCP_DEV=true
export REDIS_URL=redis://localhost:6379
docker run -d -p 6379:6379 redis:7-alpine
python server.py

# Or with Docker Compose
docker-compose up -d
docker-compose logs -f mcp-server

# Test endpoints
curl http://localhost:8080/health
curl http://localhost:8080/.well-known/mcp
curl http://localhost:8080/tool/get_status
```

### Git Workflow

```bash
# Current branch (auto-generated by Claude Code)
git status
# Branch format: claude/mcp-trading-server-design-<session-id>

# Commit and push
git add .
git commit -m "Description of changes"
git push -u origin <branch-name>
```

### S3 Historical Data Storage Layout

**Partitioned Hive-style layout** (auto-generated by uploader):
```
s3://{bucket}/mcp/{collection}/year=YYYY/month=MM/day=DD/hour=HH/minute=MM/part-{uuid}.{ext}

Example:
s3://my-bucket/mcp/market:data/year=2024/month=03/day=15/hour=10/minute=30/part-a1b2c3d4.jsonl.gz
```

**Key Points:**
- Uploader batches messages every 60 seconds (configurable via `FLUSH_INTERVAL_SECONDS`)
- Supports JSONL.gz (default) or Parquet (`UPLOAD_FORMAT=parquet`)
- Falls back to local `DATA_DIR` if S3 unavailable
- Retrieval endpoint supports cursor-based pagination (max 1000 messages per request)

---

# 📌 10. PROMPTS FOR CLAUDE CODE TO USE INTERNALLY

### When processing sentiment (Feeder):

```
You are a Sentiment-Augmented financial analyst. Score sentiment -1 to 1 and provide a one-sentence summary.
Return JSON:
{
  "score": <float>,
  "summary": "<string>"
}
```

### When executing Brain logic, follow the sequence exactly:

**Listener → Statistical Layer → Predictive Layer → Policy Layer**

---

# 📌 11. MCP SERVER INFRASTRUCTURE COMPONENTS

### Background Uploader/Archiver

The `uploader/archiver.py` module runs as a background thread within the MCP server:

- **Purpose**: Automatically batch and archive published messages to S3 or local storage
- **Trigger**: Enqueues messages on every `/tool/publish` call for `market:data`, `sentiment:data`, `agent:signal`
- **Flush strategy**:
  - Time-based: Every 60 seconds (default)
  - Size-based: When batch reaches 100 messages (default)
- **Storage formats**: JSONL.gz (default) or Parquet
- **Partitioning**: Hive-style by year/month/day/hour/minute
- **Metrics**: Exposed via `/tool/get_status` endpoint (queue_depth, uploads_total, uploads_failed, messages_archived)
- **Failure handling**: Falls back to local `DATA_DIR` if S3 unavailable; never deletes data

### Historical Data Retrieval

The `retrieval.py` module provides `/tool/retrieve` endpoint:

- **Input**: collection name, optional filters (pair, timestamp range, limit, cursor)
- **Storage support**: Reads both JSONL.gz and Parquet files from S3
- **Pagination**: Cursor-based (base64-encoded JSON with S3 continuation key)
- **Limits**: Max 1000 messages per request (hard cap)
- **Partitioning**: Leverages Hive-style partitions for efficient range queries
- **Fallback**: Returns 501 if `S3_DATA_BUCKET` not configured

### Parquet Support

The `tooling/s3_parquet.py` module provides:

- **Primary**: PyArrow-based Parquet reading with streaming
- **Fallback**: JSONL.gz reader if PyArrow unavailable or file is JSONL
- **Safety**: Enforces limit caps to prevent memory exhaustion
- **Flexibility**: Auto-detects file format from extension (.parquet, .jsonl.gz, .jsonl)

### RAG Endpoint (Placeholder)

The `/tool/search_rag` endpoint requires vector DB configuration:

- **Config**: `VECTOR_DB_TYPE` (weaviate/faiss/pinecone), `VECTOR_DB_URL`, `VECTOR_DB_API_KEY`
- **Current state**: Returns 501 with clear error message unless configured
- **Future**: Adapter implementations in `server.py::_search_vector_db()` (marked with TODO)
- **Design**: Config-driven behavior allows swapping vector DB backends

### CI/CD Testing with MinIO

For local S3 testing without AWS costs, use MinIO (S3-compatible storage):

**Start CI environment:**
```bash
docker-compose -f docker-compose.ci.yml up -d
# Services: redis, minio (ports 9000/9001), mcp-server
```

**Seed test data:**
```bash
python scripts/seed_minio.py
# Creates partitioned test data in mcp-test-bucket:
#   - 50 market:data messages (BTC-ETH)
#   - 20 sentiment:data messages
```

**Run S3 integration tests:**
```bash
pytest tests/integration/test_s3_retrieve.py -v
# Tests: retrieval, filtering, pagination, cursor continuation
```

**MinIO console access:**
- URL: http://localhost:9001
- Login: minioadmin / minioadmin
- Browse buckets, inspect partitioned files

**Environment override for MinIO:**
```bash
export AWS_ENDPOINT_URL=http://localhost:9000
export S3_DATA_BUCKET=mcp-test-bucket
export AWS_ACCESS_KEY_ID=minioadmin
export AWS_SECRET_ACCESS_KEY=minioadmin
```

**GitHub Actions CI:**
- `.github/workflows/ci.yml` - Main CI (lint, unit tests, Docker build)
- `.github/workflows/ci-s3.yml` - S3 integration tests with MinIO

---

# 📌 12. FINAL INSTRUCTIONS TO CLAUDE

Claude MUST always:

- Maintain system integrity
- Preserve architectural patterns
- Respect schemas
- Keep agents decoupled
- Keep MCP server simple, stateless, and fast
- Default to safe behavior when unsure

**Failure to follow this document may cause incorrect signals, financial risk, or broken communication between agents.**
