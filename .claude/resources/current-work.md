# CURRENT WORK — MCP SERVER DEVELOPMENT

## Project Focus

Maintain laser focus on stabilising, hardening, and advancing the MCP Server architecture toward production-grade reliability and ecosystem integration.

This document defines the *active workstream* and should be used by all AI models and developers to stay aligned with the current execution plan.

---

## PHASE A — CORE STABILISATION (ACTIVE)

Status: ✅ Smoke tests underway / ✅ Core deployment live

### A1 — Smoke Test Execution

Objective: Verify baseline operational integrity of the MCP system on Render.

Tasks:

* [ ] Run automated smoke test suite (`smoke_test.sh`)
* [ ] Confirm /health returns 200
* [ ] Confirm /tool/get_status auth behaviour (401 unauth / 200 auth)
* [ ] Validate publish → Redis → Archiver → S3 flow
* [ ] Confirm kill-switch persistence via /tool/kill_history
* [ ] Verify /tool/retrieve returns archived data
* [ ] Validate RAG endpoint behaviour (501 if not configured)

Deliverable: MCP passes all smoke tests without critical failures.

---

### A2 — Deployment Stability & Log Audit

Objective: Ensure MCP server is not "barely running" but stable.

Tasks:

* [ ] Review Render logs (mcp-server) for stack traces or critical errors
* [ ] Review Render logs (mcp-archiver) for batch failures or S3 issues
* [ ] Confirm no repeating restart loops or memory alarms

Deliverable: Logs show consistent healthy operation over at least 10-15 minutes.

---

### A3 — Archival Reliability Verification

Objective: Confirm reliable historical data persistence.

Tasks:

* [ ] Verify multiple archive files exist in S3
* [ ] Check flush cadence matches ARCHIVE_FLUSH_INTERVAL
* [ ] Confirm naming convention and partition structure
* [ ] Ensure no silent S3 upload failures

Deliverable: Proven durable data persistence.

---

## PHASE B — CONTROLLED LOAD INTRODUCTION

Status: ⏳ Pending

### B1 — Light Throughput Testing

Objective: Validate behaviour under realistic early load.

Tasks:

* [ ] Send 50-100 rapid publish requests
* [ ] Monitor Redis stability
* [ ] Ensure no dropped messages
* [ ] Observe archiver batch efficiency
* [ ] Check Render CPU & memory metrics

Deliverable: MCP sustains light load without degradation.

---

### B2 — Queue & Memory Health Analysis

Objective: Prevent bottlenecks or memory leaks.

Tasks:

* [ ] Monitor queue sizes
* [ ] Identify any unbounded growth
* [ ] Tune:

  * ARCHIVE_BATCH_SIZE
  * ARCHIVE_FLUSH_INTERVAL
  * Redis eviction policy

Deliverable: System remains stable over time.

---

## PHASE C — INTEGRATION READINESS

Status: Planned

### C1 — Feeder Agent Integration

Objective: Validate real ingestion source compatibility.

Tasks:

* [ ] Point Feeder to MCP /tool/publish
* [ ] Validate schema compliance
* [ ] Confirm archiving + retrieval for Feeder data

Deliverable: Feeder integrated and stable.

---

### C2 — Brain Agent Shadow Testing

Objective: Validate analytical consumption layer.

Tasks:

* [ ] Connect Brain in read-only mode
* [ ] Confirm /tool/retrieve accuracy
* [ ] Validate response timing
* [ ] Ensure Brain correctly handles kill-switch signals

Deliverable: Brain can interface without side effects.

---

## PHASE D — OBSERVABILITY & OPERATIONAL INSIGHT

### D1 — Metrics Enablement

Tasks:

* [ ] Expose Prometheus-compatible metrics
* [ ] Track batch flush count
* [ ] Track error rates
* [ ] Monitor Redis latency

### D2 — Alerting Rules

Tasks:

* [ ] Alert on:

  * Server unreachable
  * Redis disconnected
  * Archiver failure
  * S3 write errors

Deliverable: System visibility achieved.

---

## PHASE E — SECURITY HARDENING

### E1 — API Security

Tasks:

* [ ] Rotate MCP_API_KEY
* [ ] Define key expiration strategy
* [ ] Add optional rate limiting

### E2 — IAM Policy Lockdown

Tasks:

* [ ] Confirm least-privilege IAM rules
* [ ] Enable S3 access logging
* [ ] Restrict bucket prefix access

Deliverable: Hardened security posture.

---

## PHASE F — PRODUCTION OPTIMISATION

### F1 — Performance Tuning

Tasks:

* [ ] Adjust worker concurrency
* [ ] Optimise archive batching
* [ ] Tune Redis pool settings
* [ ] Refine timeout values

### F2 — Storage Policy

Tasks:

* [ ] Decide JSONL vs Parquet standard
* [ ] Define retention lifecycle policy
* [ ] Evaluate storage cost optimisation

Deliverable: Optimised performance profile.

---

## PHASE G — FEATURE EXPANSION (FUTURE)

Planned enhancements:

* Vector DB + RAG engine integration
* Historical replay engine
* Strategy backtesting module
* Signal feedback loop
* Autonomous decision framework

---

## CURRENT PRIORITY ORDER

1. ✅ Complete smoke testing reliably
2. ✅ Confirm archiver stability
3. ✅ Perform light load test
4. ⏳ Begin Feeder integration
5. ⏳ Enable observability + metrics
6. ⏳ Harden security

---

## ACTIVE STATUS SNAPSHOT

| Area               | Status          |
| ------------------ | --------------- |
| Deployment         | ✅ Live          |
| Smoke Tests        | 🔄 In Progress  |
| Archiver Stability | 🔄 Under Review |
| Load Testing       | ⏳ Pending       |
| Integration Phase  | ⏳ Planned       |
| Observability      | ⏳ Not Started   |
| Security Hardening | ⏳ Not Started   |

---

## Operating Instructions for AI Agents

* Prioritise tasks in PHASE A unless explicitly overridden
* Do not propose new features until PHASE A & B are complete
* Any change must not break deployment or data integrity
* Always validate against Render logs and smoke tests
* Refer to this document before suggesting new work

---

This file defines the current execution focus of the MCP Server project.
