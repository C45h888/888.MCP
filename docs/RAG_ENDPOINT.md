# RAG Endpoint Documentation

## Overview

The MCP Server now includes a lightweight RAG (Retrieval Augmented Generation) endpoint for semantic search over historical market data and sentiment. This implementation uses an adapter pattern to support multiple external vector database backends without bloating server RAM.

**Key Design Principles:**
- ⚡ **Lightweight**: No heavy ML libraries (torch, transformers) in production
- 🔌 **Pluggable**: Swap vector DB backends via environment variables
- 📦 **External**: All embedding/search happens in external vector DB APIs
- 💾 **Low Memory**: RAM usage stays under 512MB (Standard Plan compatible)

---

## Architecture

### Components

1. **Vector Engine Abstraction** ([mcp/vector_engine.py](../mcp/vector_engine.py))
   - Abstract base class: `VectorEngine`
   - Mock implementation: `MockVectorEngine` (for dev/testing)
   - Remote implementation: `RemoteVectorEngine` (generic HTTP adapter)
   - Factory function: `get_vector_engine()` (reads env vars)

2. **RAG Endpoint** ([mcp/server.py](../mcp/server.py))
   - Route: `POST /tool/search_rag`
   - Authentication: Requires `x-api-key` header (except dev mode)
   - Rate limiting: Per-IP and per-key limits apply

3. **Test Script** ([mcp/scripts/test_rag_endpoint.sh](../mcp/scripts/test_rag_endpoint.sh))
   - Comprehensive test suite for RAG endpoint
   - Tests: basic search, filters, limits, validation, edge cases

---

## Configuration

### Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `VECTOR_DB_TYPE` | Engine type | `mock` | No |
| `VECTOR_DB_URL` | Vector DB endpoint URL | `""` | Yes (for remote) |
| `VECTOR_DB_API_KEY` | API key for authentication | `""` | No |

### Supported Vector DB Types

| Type | Description | URL Example |
|------|-------------|-------------|
| `mock` | Fake results for testing/dev | N/A |
| `pinecone` | Pinecone vector database | `https://your-index.pinecone.io` |
| `weaviate` | Weaviate vector database | `https://your-cluster.weaviate.network` |
| `upstash` | Upstash vector database | `https://your-index.upstash.io` |
| `custom` | Generic HTTP backend | `https://your-vector-db.com` |

---

## Usage

### Request Format

```bash
POST /tool/search_rag
Content-Type: application/json
x-api-key: <your-api-key>

{
  "query": "bitcoin market sentiment",
  "limit": 5,
  "min_score": 0.7,
  "filters": {
    "pair": "BTC-ETH",
    "source": "Twitter"
  }
}
```

### Request Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `query` | `string` | *required* | Natural language search query |
| `limit` | `int` | `5` | Max results to return (1-100) |
| `min_score` | `float` | `0.0` | Min similarity score (0.0-1.0) |
| `filters` | `object` | `null` | Metadata filters (pair, source, etc.) |

### Response Format

```json
{
  "success": true,
  "results": [
    {
      "id": "doc_123",
      "score": 0.92,
      "text": "Bitcoin sentiment surges as institutional adoption increases...",
      "metadata": {
        "timestamp": 1678886400,
        "source": "Twitter",
        "pair": "BTC-ETH"
      }
    }
  ],
  "count": 1,
  "query": "bitcoin market sentiment",
  "filters": {"pair": "BTC-ETH"},
  "latency_seconds": 0.042
}
```

### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `success` | `bool` | Always `true` for successful requests |
| `results` | `array` | List of search results |
| `count` | `int` | Number of results returned |
| `query` | `string` | Original search query |
| `filters` | `object` | Applied metadata filters |
| `latency_seconds` | `float` | Search latency in seconds |

---

## Examples

### Example 1: Basic Search

```bash
curl -X POST http://localhost:8080/tool/search_rag \
  -H "Content-Type: application/json" \
  -H "x-api-key: your-api-key" \
  -d '{
    "query": "ethereum price prediction",
    "limit": 3
  }'
```

### Example 2: Filtered Search

```bash
curl -X POST http://localhost:8080/tool/search_rag \
  -H "Content-Type: application/json" \
  -H "x-api-key: your-api-key" \
  -d '{
    "query": "market crash news",
    "limit": 5,
    "min_score": 0.8,
    "filters": {
      "pair": "BTC-ETH",
      "source": "NewsAPI"
    }
  }'
```

### Example 3: Using Test Script

```bash
# Test against localhost (dev mode)
cd /Users/kamii/888.mcp/888.MCP/mcp
./scripts/test_rag_endpoint.sh

# Test against remote server
MCP_API_KEY=your-key ./scripts/test_rag_endpoint.sh https://your-mcp-server.com
```

---

## Deployment

### Development Mode (Mock Engine)

The default configuration uses `MockVectorEngine` which returns fake results. This is safe for local testing and CI environments.

```bash
# Start MCP server with mock vector engine (default)
export MCP_DEV=true
export REDIS_URL=redis://localhost:6379
python -m mcp.server
```

Test the endpoint:
```bash
curl -X POST http://localhost:8080/tool/search_rag \
  -H "Content-Type: application/json" \
  -d '{"query": "test", "limit": 2}'
```

Expected response (mock data):
```json
{
  "success": true,
  "results": [
    {
      "id": "doc_0",
      "score": 0.95,
      "text": "Mock document 0 about test",
      "metadata": {"source": "mock_data", "timestamp": 1678886400, "pair": "BTC-ETH"}
    }
  ],
  "count": 1,
  "query": "test",
  "filters": null,
  "latency_seconds": 0.001
}
```

### Production Mode (Pinecone Example)

Configure environment variables for Pinecone:

```bash
# render.yaml or Render.com dashboard
VECTOR_DB_TYPE=pinecone
VECTOR_DB_URL=https://your-index-123abc.svc.pinecone.io
VECTOR_DB_API_KEY=<secret-pinecone-api-key>  # sync: false in render.yaml
```

Restart the server and test:
```bash
curl -X POST https://your-mcp-server.com/tool/search_rag \
  -H "Content-Type: application/json" \
  -H "x-api-key: your-mcp-api-key" \
  -d '{
    "query": "bitcoin sentiment analysis",
    "limit": 5
  }'
```

### Production Mode (Weaviate Example)

```bash
# Environment variables
VECTOR_DB_TYPE=weaviate
VECTOR_DB_URL=https://your-cluster-abc123.weaviate.network
VECTOR_DB_API_KEY=<secret-weaviate-api-key>
```

### Production Mode (Upstash Example)

```bash
# Environment variables
VECTOR_DB_TYPE=upstash
VECTOR_DB_URL=https://your-index-xyz789.upstash.io
VECTOR_DB_API_KEY=<secret-upstash-api-key>
```

---

## Vector Database Integration

### Pinecone Setup

1. **Create Index** (Pinecone Console)
   - Dimensions: Match your embedding model (e.g., 1536 for OpenAI text-embedding-ada-002)
   - Metric: Cosine similarity
   - Pod type: s1.x1 (starter) or p1.x1 (production)

2. **Populate Index** (via Feeder Agent or batch script)
   ```python
   import pinecone

   pinecone.init(api_key="your-api-key")
   index = pinecone.Index("mcp-trading-data")

   # Upsert vectors
   index.upsert(vectors=[
       ("doc_1", embedding_vector, {"text": "...", "pair": "BTC-ETH", "timestamp": 1678886400})
   ])
   ```

3. **Configure MCP Server**
   ```bash
   VECTOR_DB_TYPE=pinecone
   VECTOR_DB_URL=https://your-index-123abc.svc.pinecone.io
   VECTOR_DB_API_KEY=your-pinecone-api-key
   ```

### Weaviate Setup

1. **Create Schema** (Weaviate Console or API)
   ```graphql
   {
     "class": "Document",
     "vectorizer": "text2vec-openai",
     "properties": [
       {"name": "text", "dataType": ["text"]},
       {"name": "pair", "dataType": ["string"]},
       {"name": "timestamp", "dataType": ["int"]},
       {"name": "source", "dataType": ["string"]}
     ]
   }
   ```

2. **Populate Data** (via Feeder Agent or batch script)

3. **Configure MCP Server**
   ```bash
   VECTOR_DB_TYPE=weaviate
   VECTOR_DB_URL=https://your-cluster.weaviate.network
   VECTOR_DB_API_KEY=your-weaviate-api-key
   ```

### Upstash Setup

1. **Create Index** (Upstash Console)
   - Dimensions: Match your embedding model
   - Similarity: Cosine

2. **Populate Index** (via Upstash REST API or SDK)

3. **Configure MCP Server**
   ```bash
   VECTOR_DB_TYPE=upstash
   VECTOR_DB_URL=https://your-index.upstash.io
   VECTOR_DB_API_KEY=your-upstash-api-key
   ```

---

## Error Handling

### Common Errors

| HTTP Code | Error | Cause | Solution |
|-----------|-------|-------|----------|
| `401` | Unauthorized | Missing or invalid API key | Add `x-api-key` header |
| `400` | Bad Request | Invalid limit or min_score | Check parameter ranges |
| `422` | Unprocessable Entity | Missing required field | Include `query` field |
| `501` | Not Implemented | Vector engine not configured | Set `VECTOR_DB_TYPE` and `VECTOR_DB_URL` |
| `500` | Internal Server Error | Vector DB connection failed | Check `VECTOR_DB_URL` and API key |

### Example Error Response

```json
{
  "detail": "RAG search not configured. Set VECTOR_DB_TYPE and VECTOR_DB_URL."
}
```

---

## Testing

### Unit Tests (Mock Engine)

```bash
# Run test script with mock engine (default)
cd /Users/kamii/888.mcp/888.MCP/mcp
MCP_DEV=true ./scripts/test_rag_endpoint.sh
```

### Integration Tests (Remote Vector DB)

```bash
# Test against real Pinecone instance
export VECTOR_DB_TYPE=pinecone
export VECTOR_DB_URL=https://your-index.pinecone.io
export VECTOR_DB_API_KEY=your-api-key
export MCP_API_KEY=your-mcp-key

./scripts/test_rag_endpoint.sh https://your-mcp-server.com
```

### Test Coverage

The test script ([test_rag_endpoint.sh](../mcp/scripts/test_rag_endpoint.sh)) covers:

**Functional Tests:**
- ✅ Basic search queries
- ✅ Custom limit parameters
- ✅ Min score thresholds
- ✅ Metadata filters
- ✅ Invalid limit validation (exceeds max)
- ✅ Invalid min_score validation (out of range)
- ✅ Missing required field validation
- ✅ Empty query edge case

**Security Tests (Phase 6 Compliance):**
- ✅ No API key rejection (401 Unauthorized)
- ✅ Invalid API key rejection (401 Unauthorized)
- ✅ Feeder key denial (403 Forbidden - RBAC)
- ✅ Readonly key denial (403 Forbidden - RBAC)
- ✅ Admin/Brain key acceptance (200 OK)

**How to Run Security Tests:**
```bash
# Basic security tests (no API key / invalid API key)
./scripts/test_rag_endpoint.sh

# Full RBAC tests (requires API keys for each role)
export ADMIN_KEY=mcp_admin_...
export FEEDER_KEY=mcp_feeder_...
export READONLY_KEY=mcp_readonly_...
./scripts/test_rag_endpoint.sh

# Skip security tests (functional tests only)
SKIP_SECURITY_TESTS=true ./scripts/test_rag_endpoint.sh
```

**Expected Results:**
- Feeder/readonly keys must return **403 Forbidden**
- Admin/brain keys must return **200 OK**
- If feeder/readonly keys get 200 OK, this is a **CRITICAL RBAC VIOLATION**

---

## Performance

### Latency Benchmarks

| Vector DB | Typical Latency | Notes |
|-----------|----------------|-------|
| Mock | 1-5ms | In-memory, no network |
| Pinecone | 50-200ms | Depends on region/pod type |
| Weaviate | 100-300ms | Depends on cluster size |
| Upstash | 50-150ms | Serverless, varies by load |

### Memory Usage

The RAG endpoint adds minimal memory overhead:
- MockVectorEngine: ~1KB (negligible)
- RemoteVectorEngine: ~5-10KB (httpx client + config)
- Total MCP server RAM: **~100-200MB** (well under 512MB limit)

### Rate Limits

RAG search respects existing MCP server rate limits:
- Per-IP global: 100 requests/minute (configurable via `RATE_LIMIT_GLOBAL_IP`)
- Per-key global: 200 requests/minute (configurable via `RATE_LIMIT_GLOBAL_KEY`)

---

## Security

### 🔒 Phase 6 Security Compliance

The RAG endpoint follows **Phase 4 Security Standards** with 3-layer protection:

```
┌─────────────────────────────────────┐
│  Layer 1: Per-IP Global Limit      │  ← 100/minute (middleware)
│  Prevents DoS from single IP       │
├─────────────────────────────────────┤
│  Layer 2: Per-Key Global Limit     │  ← 200/minute (middleware)
│  Fair usage enforcement             │
├─────────────────────────────────────┤
│  Layer 3: RBAC + Endpoint Limit    │  ← 30/minute (endpoint-specific)
│  retrieve:rag permission required   │  ← verify_permission("retrieve:rag")
└─────────────────────────────────────┘
```

### Role-Based Access Control (RBAC)

**Only the following roles can access `/tool/search_rag`:**

| Role | Access | Permission | Reason |
|------|--------|------------|--------|
| `admin` | ✅ **ALLOWED** | `*` (wildcard) | Full system access |
| `brain` | ✅ **ALLOWED** | `retrieve:*` | Needs RAG for trading signals |
| `feeder` | ❌ **DENIED** | No retrieve permission | Should only publish data |
| `ops` | ❌ **DENIED** | No retrieve permission | Control-only access |
| `readonly` | ❌ **DENIED** | No retrieve permission | Metrics/status only |

**Permission Enforcement:**
- Endpoint requires `retrieve:rag` permission
- `brain` role has `retrieve:*` (wildcard matches `retrieve:rag`)
- Attempts by unauthorized roles return **403 Forbidden**
- See [auth.py:29-57](../mcp/auth.py#L29-L57) for permission definitions

### Rate Limiting

**Endpoint-Specific Limits:**
- **RATE_LIMIT_RAG**: 30 requests/minute (default)
- Same as `RATE_LIMIT_RETRIEVE` (both are read operations)
- Configurable via environment variable

**Cost Protection:**
- External vector DB calls cost ~$0.0001/query
- Rate limiting prevents cost bleed from spam/bugs
- 30/minute = max $43.20/month even if fully saturated

### Authentication

- **Dev mode** (`MCP_DEV=true`): No authentication required
- **Production mode**: Requires valid `x-api-key` header with `retrieve:rag` permission
- **Invalid key**: Returns **401 Unauthorized**
- **Valid but wrong role**: Returns **403 Forbidden**

### API Key Management

Create API keys with appropriate roles:
```bash
# ✅ CORRECT: Create brain key (has retrieve:* permission)
curl -X POST https://your-mcp-server.com/admin/keys/create \
  -H "x-api-key: admin-key" \
  -H "Content-Type: application/json" \
  -d '{
    "role": "brain",
    "description": "RAG search for Brain agent"
  }'

# ❌ INCORRECT: Don't use readonly for RAG (no retrieve permission)
curl -X POST https://your-mcp-server.com/admin/keys/create \
  -H "x-api-key: admin-key" \
  -H "Content-Type: application/json" \
  -d '{
    "role": "readonly",
    "description": "This will NOT work for RAG"
  }'
```

### Security Best Practices

**1. Least Privilege**
- Use `brain` role keys for Brain agent RAG access
- Don't use `admin` keys in production (overly permissive)
- Revoke keys immediately if compromised

**2. Audit Logging**
- All RAG requests logged with key role and suffix
- Monitor logs for unexpected access patterns
- Set up alerts for 403 Forbidden responses

**3. Secrets Management**

**NEVER commit secrets to Git!**

Store secrets in:
- **Render.com**: Environment variables with `sync: false`
- **Local dev**: `.env` file (gitignored)
- **CI/CD**: GitHub Secrets or encrypted environment variables

**4. Cost Monitoring**
- Monitor RAG endpoint usage metrics
- Set up billing alerts on vector DB provider (Pinecone, Weaviate, etc.)
- Consider lower rate limits if costs exceed budget

---

## Troubleshooting

### Issue: "RAG search not configured" (501)

**Cause**: Vector engine not initialized (VECTOR_DB_TYPE not set or invalid)

**Solution**:
```bash
# Check current config
echo $VECTOR_DB_TYPE
echo $VECTOR_DB_URL

# Set to mock for testing
export VECTOR_DB_TYPE=mock

# Or configure real vector DB
export VECTOR_DB_TYPE=pinecone
export VECTOR_DB_URL=https://your-index.pinecone.io
export VECTOR_DB_API_KEY=your-api-key

# Restart server
python -m mcp.server
```

### Issue: "Vector DB search failed" (500)

**Cause**: Cannot connect to external vector DB

**Solution**:
1. Verify `VECTOR_DB_URL` is correct
2. Check `VECTOR_DB_API_KEY` is valid
3. Test vector DB health directly:
   ```bash
   curl https://your-index.pinecone.io/health \
     -H "Api-Key: your-api-key"
   ```
4. Check server logs for detailed error messages

### Issue: Empty results

**Cause**: No matching documents or min_score threshold too high

**Solution**:
1. Lower `min_score` threshold (try 0.0)
2. Verify vector DB has indexed data
3. Try broader query terms
4. Check `filters` aren't too restrictive

---

## Future Enhancements

### Planned Features

- [ ] **Hybrid Search**: Combine vector search with keyword search (BM25)
- [ ] **Query Expansion**: Automatically expand user queries with synonyms
- [ ] **Re-ranking**: Re-rank results using cross-encoder models
- [ ] **Caching**: Cache frequent queries to reduce vector DB calls
- [ ] **Streaming**: Stream results as they're found (SSE/WebSockets)
- [ ] **Multi-vector**: Support multiple embedding models per document

### Integration Ideas

- **Brain Agent**: Use RAG search to augment trading signals with historical context
- **Feeder Agent**: Populate vector DB with sentiment summaries from n8n pipeline
- **Alert System**: Trigger alerts when RAG search detects unusual patterns

---

## References

- [Pinecone Documentation](https://docs.pinecone.io/)
- [Weaviate Documentation](https://weaviate.io/developers/weaviate)
- [Upstash Vector Documentation](https://upstash.com/docs/vector)
- [MCP Server Architecture](../CLAUDE.md)
- [RUNBOOK](./RUNBOOK.md)
- [SECURITY](./SECURITY.md)

---

**Last Updated**: 2025-12-13
**Version**: 1.0.0
**Status**: ✅ Production Ready (Mock Engine) / 🚧 Beta (Remote Engines)
