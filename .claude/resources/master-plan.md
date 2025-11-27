# MCP SERVER MASTER PLAN  
_Post-smoke tests → Production-complete_

## 0. Context Snapshot

We have a deployed MCP server on Render with:

- FastAPI-based MCP web service (`server:app`)
- Background archiver worker (`mcp-archiver`) with S3 / local archival
- Redis for pub/sub messaging
- S3 (or S3-compatible) storage for historical data
- RAG/vector DB endpoint stub (`/tool/search_rag` returning 501)
- CI + docker-compose.ci + MinIO integration tests
- Automated smoke tests + scripts
- Successful Render deployment + `/health` endpoint in place
- Core channels: `market:data`, `sentiment:data`, `agent:control`, `agent:signal`

**Status today:**  
✅ Infra & deployment working  
✅ Smoke tests green  
➡️ Next: harden, scale, integrate, and declare MCP “production complete”.

This master plan covers the steps **after smoke testing** up to “MCP server is complete and production-ready”.

---

## 1. High-Level Goals

By the end of this plan, the MCP server should:

1. Be **operationally stable** under expected load.
2. Provide **durable archival** to S3 with clear retention structure.
3. Offer **clean, documented APIs** for:
   - Feeder agent (Agent 1) publishing
   - Brain agent (Agent 2) querying & replaying data
4. Expose **observability (metrics + logs)** suitable for real operations.
5. Be **secure** (API keys, IAM locked down, no unauth leaks).
6. Optionally be **RAG-ready** (vector DB integration toggleable via config).

---

## 2. Phase 1 — Post-Smoke Hardening & Archiver Stability

**Goal:** Turn “it passes tests” into “it’s solid and predictable.”

### 1.1 Archiver Stability & S3 Behaviour

**Tasks:**
- [ ] Run smoke tests multiple times over different days (idempotence check).
- [ ] Inspect S3 object layout over time:
  - Confirm `year=YYYY/month=MM/day=DD/hour=HH` partitions are correct.
  - Confirm filenames (`part-*.jsonl.gz` / `.parquet`) follow the spec.
- [ ] Verify:
  - No duplicate or overlapping time ranges (unless intended).
  - No obvious gaps if traffic is regular.
- [ ] Ensure local fallback logic behaves correctly when S3 is unavailable (simulate S3 failure and check logs).

**Acceptance:**
- At least N (e.g. 3–5) separate runs produce consistent, correctly partitioned data.
- No recurring S3 errors in `mcp-archiver` logs during normal operation.

---

### 1.2 Retrieval Accuracy & Limits

**Tasks:**
- [ ] Test `/tool/retrieve` with:
  - Different `pair` values.
  - Edge `from_ts` / `to_ts` ranges (very small, wide windows).
  - `limit` near max (e.g. 1000) and small (e.g. 10).
- [ ] Confirm:
  - Correct time-ordering of returned records.
  - `limit` respected.
  - Cursor-based pagination working as designed (if implemented).
- [ ] Document retrieval semantics in `README` / `DEVELOPMENT.md`:
  - Time range behaviour.
  - How pagination works.
  - Safety limits.

**Acceptance:**
- Retrieval matches expectations for multiple scenarios.
- No unbounded memory growth during large-window retrievals.

---

### 1.3 Kill-Switch & Control Channel Reliability

**Tasks:**
- [ ] Repeatedly send `EMERGENCY_HALT` and related control messages.
- [ ] Confirm `kill_history` returns correct and ordered control events.
- [ ] Ensure kill events are **durable** (survive pod restart).
- [ ] Document kill-switch behaviour for Brain agent:
  - How to interpret `EMERGENCY_HALT`.
  - Where to read the last state.

**Acceptance:**
- Kill history survives restarts, and the latest state is always accessible.
- Docs clearly describe the contract for Brain/Feeder.

---

## 3. Phase 2 — Controlled Load & Performance

**Goal:** Confirm MCP handles realistic traffic without degrading.

### 2.1 Light & Moderate Load Testing

**Tasks:**
- [ ] Run a simple load generator:
  - e.g. 50–200 `market:data` messages/minute for 15–60 minutes.
- [ ] Monitor via Render:
  - CPU and memory usage on `mcp-server` and `mcp-archiver`.
  - Restart counts (should be zero).
- [ ] Track:
  - Archiver flush frequency and batch sizes.
  - Latency for `/tool/publish` and `/tool/retrieve`.

**Acceptance:**
- No crashes or restarts.
- Latency stays within acceptable bounds.
- S3 continues to receive well-formed archives.

---

### 2.2 Tuning Archiver Parameters

**Tasks:**
- [ ] Adjust and document:
  - `ARCHIVE_BATCH_SIZE`
  - `ARCHIVE_FLUSH_INTERVAL`
  - Any `ARCHIVE_FORMAT` options (jsonl vs parquet)
- [ ] Choose **production-defaults** based on:
  - Tradeoff between latency vs. file size.
  - S3 cost vs. frequency.
- [ ] Update `DEVELOPMENT.md` with tuning guidelines.

**Acceptance:**
- A default configuration is chosen and works well for expected traffic.
- Tuning instructions exist for future scaling.

---

## 4. Phase 3 — Observability & Operations

**Goal:** Make MCP “operable” not just “running.”

### 3.1 Metrics & Prometheus Integration

**Tasks:**
- [ ] Implement basic metrics using `prometheus-client`:
  - Request counts + latencies per endpoint.
  - Archiver batches flushed.
  - Errors encountered (by type).
- [ ] Expose metrics endpoint (e.g. `/metrics`) protected or internal-only.
- [ ] Verify metrics scrape works in staging.

**Acceptance:**
- Prometheus (or another scraper) can ingest metrics successfully.
- Dashboards can be built from these metrics.

---

### 3.2 Logging & Structured Logs

**Tasks:**
- [ ] Standardize logs using `python-json-logger`:
  - Include request id / correlation id.
  - Channel + collection for archiver events.
- [ ] Ensure logs:
  - Are structured JSON where needed.
  - Avoid leaking secrets.
- [ ] Add minimal log-level config:
  - DEBUG in dev.
  - INFO in staging/production.

**Acceptance:**
- Logs are easy to filter and search by request/channel.
- No secrets or credentials appear in logs.

---

### 3.3 Runbook & Operational Docs

**Tasks:**
- [ ] Create a short `RUNBOOK.md` or section in `DEVELOPMENT.md`:
  - “How to restart services.”
  - “How to debug S3 problems.”
  - “How to interpret key metrics.”
  - “Incident checklist for: S3 down, Redis down, MCP down.”

**Acceptance:**
- Someone new can operate MCP without tribal knowledge.

---

## 5. Phase 4 — Security & Access Control

**Goal:** Lock down access and be safe for real traffic.

### 4.1 API Key & Auth Hardening

**Tasks:**
- [ ] Review `/tool/*` endpoints and ensure:
  - Everything sensitive requires `x-api-key`.
  - Only `/health` is public.
- [ ] Add support (optionally) for:
  - Multiple API keys (e.g. Feeder, Brain, Ops).
  - Rotation procedure documented.

**Acceptance:**
- Auth is consistent and no “forgotten public” endpoints exist.
- Rotation process is documented and tested at least once.

---

### 4.2 IAM & S3 Permissions

**Tasks:**
- [ ] Check IAM policies for MCP Render user:
  - Scoped to the exact S3 bucket + prefix.
  - No broad `s3:*` on all resources.
- [ ] Enable S3 access logging or CloudTrail for bucket access.
- [ ] Document the IAM policy in `DEVELOPMENT.md` / `SECURITY.md`.

**Acceptance:**
- IAM is least-privilege.
- Security review (even if informal) passes.

---

## 6. Phase 5 — Feeder & Brain Integration Surfaces (Server-Side)

**Goal:** Make MCP's API rock-solid for the two external agents without building them here.

### 5.1 Feeder Agent (Agent 1) Contract

**Tasks:**
- [ ] Finalize and document Feeder → MCP publishing contract:
  - Allowed channels.
  - Required fields in `market:data` and `sentiment:data`.
  - Rate expectations.
- [ ] Provide concrete examples (curl + JSON).

**Acceptance:**
- Feeder agent can publish without guessing field names or semantics.

---

### 5.2 Brain Agent (Agent 2) Contract

**Tasks:**
- [ ] Finalize and document Brain → MCP retrieval contract:
  - `/tool/retrieve` usage patterns.
  - Time ranges, pagination, limits.
  - Kill history usage (`/tool/kill_history`).
- [ ] Provide examples:
  - “Get last 24h of BTC-USD.”
  - “Get last 10 kill events.”

**Acceptance:**
- Brain agent can query without ambiguity and can implement backtesting/replay on top of MCP.

---

## 7. Phase 6 — RAG & Vector DB (Optional but “Complete” for V2+)

**Goal:** Turn the RAG stub into a configurable, optional feature.

### 6.1 Enable Vector DB Integration

**Tasks:**
- [ ] Implement `VECTOR_DB_TYPE` and `VECTOR_DB_URL` handling for one concrete backend (e.g. Weaviate, Pinecone, or FAISS).
- [ ] Implement ingestion pipeline (out of MCP server’s hot path):
  - Take news / signals → embeddings → vector DB.
- [ ] Implement real `/tool/search_rag` behaviour:
  - Accept query text.
  - Return top-k results with metadata.

**Acceptance:**
- When `VECTOR_DB_TYPE` is set, `/tool/search_rag` returns meaningful results.
- When unset, it cleanly returns 501 with clear message.

---

## 8. Phase 7 — Production Readiness Checklist

**Goal:** Have a clear definition of “MCP server is complete.”

Before calling this server “done”, check:

- [ ] ✅ Deployment:
  - Render services stable for X days.
- [ ] ✅ Smoke tests:
  - `smoke_test.sh` green in staging and/or prod.
- [ ] ✅ Archival:
  - S3 structure validated; no recurring errors.
- [ ] ✅ Performance:
  - Survives expected load + headroom.
- [ ] ✅ Observability:
  - Metrics endpoint in place; basic dashboards possible.
- [ ] ✅ Security:
  - API keys, IAM, and public endpoints reviewed.
- [ ] ✅ Integration:
  - Feeder & Brain contracts documented and tested.
- [ ] ✅ RAG (if in scope):
  - Either fully implemented or clearly marked “not included in v1”.

When all boxes above are checked, the MCP server can be declared **production-complete for this project scope**.

---

## 9. Suggested Work Order (Post-Smoke)

Given that **smoke tests are DONE**, the recommended execution order is:

1. **Phase 1** – Archiver + retrieval hardening  
2. **Phase 2** – Controlled load and performance tuning  
3. **Phase 3** – Observability (metrics + logs + runbook)  
4. **Phase 4** – Security hardening (auth + IAM)  
5. **Phase 5** – Finalize Feeder & Brain server-side contracts  
6. **Phase 6** – RAG/vector DB (if included in “complete”)  
7. **Phase 7** – Run the production-ready checklist and freeze v1

---

This master plan is ready to be:

- Saved as `MASTER-PLAN_MCP-SERVER.md`  
- Fed into Claude Code as context for future sprints  
- Used to drive your next “current work” updates

If you’d like, I can now:

- Turn this into a **GitHub Project / issues breakdown**, or  
- Generate **exact prompts** for Claude Code for the *next phase only* (e.g. “Implement Phase 1.1 & 1.2 safely”).
::contentReference[oaicite:0]{index=0}
