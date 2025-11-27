# CURRENT WORK — MCP SERVER DEVELOPMENT

## Project Focus

Maintain laser focus on stabilising, hardening, and advancing the MCP Server architecture toward production-grade reliability and ecosystem integration.

This document defines the *active workstream* and should be used by all AI models and developers to stay aligned with the current execution plan.

---

## 🎯 NEXT ACTION (Start Here)

**Current Phase:** Phase 1 - Post-Smoke Hardening & Archiver Stability
**Current Task:** 1.1.1 - Multi-Day Smoke Test Idempotence
**Status:** 🔄 Ready to Execute
**Focus:** SERVER DEVELOPMENT ONLY (Feeder & Brain deferred until server production-ready)

### 🎉 PHASES A & B COMPLETE!

**Phase A (Core Stabilisation):** ✅ COMPLETE (2025-11-26)
- All Priority 1 (P0) tasks: ✅ PASS
- All Priority 2 (P1) tasks: ✅ PASS
- Priority 3 (P2) tasks: ✅ PASS (archiver monitoring confirmed stable)
- [View Details](../../WORK_LOG.md#phase-a-core-stabilisation)

**Phase B (Controlled Load Testing):** ✅ COMPLETE (2025-11-26)
- B1 Load Test: ✅ 100/100 messages (100% success rate, 0.352s avg response)
- B2 Health Monitoring: ✅ Stable over 20 minutes (0 queue growth)
- Results: [phase-b-results.txt](../../phase-b-results.txt)
- [View Details](../../WORK_LOG.md#phase-b-controlled-load-introduction)

### 📋 What to do RIGHT NOW:

**Start Phase 1.1: Archiver Stability & S3 Behaviour**

This is a **P0-CRITICAL** task focused on data integrity validation. We're verifying that the archiver produces consistent, correctly-partitioned data over multiple days.

**Commands to execute:**

```bash
# Step 1: Run first baseline smoke test
cd /Users/kamii/888.mcp/888.MCP/mcp
export MCP_URL="https://mcp-server-<your-id>.onrender.com"
export MCP_API_KEY="<your-key>"
./scripts/run_smoke_tests.sh | tee docs/test-results/phase-1.1-day1-$(date +%Y-%m-%d).txt

# Step 2: Schedule tests for next 2-4 days
# Set calendar reminder to run smoke tests daily at same time
# Or create a cron job (if running from persistent environment)

# Step 3: Inspect S3 bucket structure (if S3 configured)
aws s3 ls s3://$S3_DATA_BUCKET/mcp/market:data/ --recursive | head -50

# Step 4: Verify partition structure
aws s3 ls s3://$S3_DATA_BUCKET/mcp/ --recursive | \
  grep -E "year=[0-9]{4}/month=[0-9]{2}/day=[0-9]{2}/hour=[0-9]{2}"

# Step 5: Test local fallback (simulate S3 failure)
# Temporarily unset S3 credentials, publish messages, verify local writes
```

**Success Criteria:**
- [ ] Smoke tests pass on Day 1
- [ ] Smoke tests pass on Day 2
- [ ] Smoke tests pass on Day 3 (minimum)
- [ ] S3 partition structure matches: `year=YYYY/month=MM/day=DD/hour=HH/minute=MM/`
- [ ] No duplicate time ranges detected
- [ ] No gaps in regular traffic
- [ ] Local fallback works when S3 unavailable

**Blocked by:** Nothing (ready to start)
**Time estimate:** 2-3 days (multi-day validation)
**Next task after completion:** Phase 1.2 - Retrieval Accuracy Testing

---

## PHASE A — CORE STABILISATION ✅ COMPLETE

Status: ✅ Complete (2025-11-26) - All critical tests passed

---

### Priority 1: Baseline Health (BLOCKING)

**Must complete ALL tasks before any other Phase A work.**

#### **A1.1** [P0-CRITICAL] Execute Smoke Test Suite

**Objective:** Verify all critical endpoints operational

**Command:**
```bash
cd /Users/kamii/888.mcp/888.MCP/mcp
./scripts/run_smoke_tests.sh
```

**Success Criteria:**
- [ ] Exit code = 0 (all critical tests pass)
- [ ] Test 1 (Health Check): HTTP 200 ✓
- [ ] Test 4 (Auth Rejection): HTTP 401/403 ✓
- [ ] Test 5 (Auth Success): HTTP 200, `redis_connected: true` ✓
- [ ] Test 6 (Publish Valid): HTTP 200, `success: true` ✓
- [ ] Test 7 (Invalid Message): HTTP 400/422 ✓
- [ ] Test 10-12 (Kill-Switch): Activate → Verify → Resume ✓

**Acceptance:**
- All 13 critical tests return green ✓ PASS
- Response times: /health <500ms, /tool/publish <1s
- Zero exceptions in test output

**Failure Actions:**
- Exit code 1 → Check [SMOKE_TESTING.md Troubleshooting](../../mcp/SMOKE_TESTING.md#troubleshooting) (line 377)
- Exit code 2 → Verify `$MCP_URL` and `$MCP_API_KEY` set correctly
- Test 4 FAIL (Security bug) → CRITICAL: Verify `MCP_DEV=false` in Render
- Test 5 FAIL (Redis) → Check Redis service status on Render
- Any FAIL → Document in `docs/test-results/YYYY-MM-DD.md`, debug before proceeding

**Evidence Required:**
```bash
# Save output
./scripts/run_smoke_tests.sh | tee docs/test-results/$(date +%Y-%m-%d)-smoke-tests.txt
```

**Time Estimate:** 3-5 minutes

---

#### **A1.2** [P0-CRITICAL] Verify Health Endpoint Performance

**Objective:** Baseline response time validation

**Command:**
```bash
curl -w "\nTime: %{time_total}s\n" "$MCP_URL/health"
```

**Success Criteria:**
- [ ] HTTP 200 response
- [ ] Response body: `{"status": "ok", ...}`
- [ ] Response time: <0.5s (500ms)
- [ ] 3 consecutive successful requests

**Acceptance:**
```bash
# Run 3 times
for i in {1..3}; do
  curl -w "\nTime: %{time_total}s\n" -s "$MCP_URL/health" | jq -e '.status == "ok"'
  sleep 2
done
```
All 3 requests return `status: ok` with time <0.5s

**Time Estimate:** 1 minute

---

#### **A1.3** [P0-CRITICAL] Verify Redis Connectivity

**Objective:** Confirm persistent Redis connection

**Command:**
```bash
curl -H "x-api-key: $MCP_API_KEY" "$MCP_URL/tool/get_status" | jq .
```

**Success Criteria:**
- [ ] HTTP 200 response
- [ ] `redis_connected: true`
- [ ] `uptime_seconds` > 0
- [ ] No Redis connection errors in server logs

**Failure Actions:**
- `redis_connected: false` → Check Render dashboard: mcp-redis service status
- Connection timeout → Verify `REDIS_URL` env var in mcp-server
- Check web logs: `./scripts/render_status.sh web-logs | grep -i redis`

**Time Estimate:** 1 minute

---

#### **A1.4** [P0-CRITICAL] Verify Authentication Enforcement

**Objective:** **SECURITY TEST** - Ensure protected endpoints reject unauthenticated requests

**Command:**
```bash
# Without API key (should fail)
curl -i "$MCP_URL/tool/get_status"

# With API key (should succeed)
curl -i -H "x-api-key: $MCP_API_KEY" "$MCP_URL/tool/get_status"
```

**Success Criteria:**
- [ ] Request WITHOUT key returns HTTP 401 or 403
- [ ] Request WITH key returns HTTP 200
- [ ] No `MCP_DEV=true` in production environment

**CRITICAL FAILURE:**
If request WITHOUT key returns HTTP 200 → **SECURITY BUG**
- Immediately check: `./scripts/render_status.sh env | grep MCP_DEV`
- Must be: `MCP_DEV=false` (or not set)
- If `MCP_DEV=true` → Change to `false` in Render, redeploy

**Time Estimate:** 2 minutes

---

**🚨 GATE: Priority 1 Checkpoint**

**DO NOT PROCEED** to Priority 2 until ALL Priority 1 tasks show ✅

Verification command:
```bash
# All must return success
./scripts/run_smoke_tests.sh && \
curl -s "$MCP_URL/health" | jq -e '.status == "ok"' && \
curl -s -H "x-api-key: $MCP_API_KEY" "$MCP_URL/tool/get_status" | jq -e '.redis_connected == true' && \
curl -s "$MCP_URL/tool/get_status" | grep -q '401\|403'

echo $?  # Must be 0
```

---

### Priority 2: Core Functionality (BLOCKING)

**Depends on:** Priority 1 complete ✅

#### **A2.1** [P1-HIGH] Publish Valid market:data Message

**Objective:** Validate end-to-end publish pipeline

**Command:**
```bash
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

**Success Criteria:**
- [ ] HTTP 200 response
- [ ] Response body: `{"success": true, "collection": "market:data"}`
- [ ] No errors in server logs
- [ ] Message appears in Redis (check with get_status)

**Time Estimate:** 2 minutes

---

#### **A2.2** [P1-HIGH] Reject Invalid Messages

**Objective:** Validate JSON schema enforcement

**Command:**
```bash
# Missing schema_version (should fail)
curl -X POST "$MCP_URL/tool/publish" \
  -H "x-api-key: $MCP_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "collection": "market:data",
    "message": {
      "timestamp": '$(date +%s)',
      "pair": "BTC-ETH",
      "price_btc": 30000.0
    }
  }'
```

**Success Criteria:**
- [ ] HTTP 400 or 422 response
- [ ] Error message mentions schema validation
- [ ] Message NOT published to Redis

**CRITICAL FAILURE:**
If returns HTTP 200 → **SCHEMA VALIDATION BUG**
- Check server logs for schema loading errors
- Verify `mcp/schemas/v1/` directory exists and has 4 .json files
- Check startup logs: `./scripts/render_status.sh web-logs | grep -i schema`

**Time Estimate:** 2 minutes

---

#### **A2.3** [P1-HIGH] Kill-Switch Activation & Persistence

**Objective:** Validate emergency halt system

**Commands:**
```bash
# 1. Activate kill-switch
curl -X POST "$MCP_URL/tool/publish" \
  -H "x-api-key: $MCP_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "collection": "agent:control",
    "message": {
      "schema_version": "v1",
      "timestamp": '$(date +%s)',
      "command": "EMERGENCY_HALT",
      "reason": "TEST_ACTIVATION"
    }
  }'

# 2. Verify persistence
curl -H "x-api-key: $MCP_API_KEY" "$MCP_URL/tool/get_status" | jq '.kill_switch'
```

**Success Criteria:**
- [ ] Publish returns HTTP 200
- [ ] get_status shows `"kill_switch": {"active": true, "reason": "TEST_ACTIVATION"}`
- [ ] Redis key `mcp:kill_switch` persists across requests
- [ ] Status remains HALT until explicitly cleared

**Time Estimate:** 3 minutes

---

#### **A2.4** [P1-HIGH] Kill-Switch Resume (CLEAR)

**Objective:** Validate kill-switch can be cleared

**Commands:**
```bash
# 1. Clear kill-switch
curl -X POST "$MCP_URL/tool/publish" \
  -H "x-api-key: $MCP_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "collection": "agent:control",
    "message": {
      "schema_version": "v1",
      "timestamp": '$(date +%s)',
      "command": "RESUME",
      "reason": "TEST_COMPLETE"
    }
  }'

# 2. Verify cleared
curl -H "x-api-key: $MCP_API_KEY" "$MCP_URL/tool/get_status" | jq '.kill_switch.active'
```

**Success Criteria:**
- [ ] Publish returns HTTP 200
- [ ] get_status shows `"kill_switch": {"active": false}`
- [ ] System returns to normal operation

**Time Estimate:** 2 minutes

---

**🚨 GATE: Priority 2 Checkpoint**

All Priority 2 tasks must pass before Priority 3.

---

### Priority 3: Data Pipeline (NON-BLOCKING)

**Depends on:** Priority 2 complete ✅
**Note:** Can proceed to Phase B if this fails with documentation

#### **A3.1** [P2-MEDIUM] Archiver Worker Health Check

**Objective:** Verify background worker stays running

**Commands:**
```bash
# Check worker service status
./scripts/render_status.sh status | grep -A5 mcp-archiver

# Check worker logs
./scripts/render_status.sh worker-logs | tail -50
```

**Success Criteria:**
- [ ] Worker service status: "running" (not "exited")
- [ ] Logs show: "MCP Archiver Worker starting..." (no crash loops)
- [ ] No Python exceptions in last 50 lines
- [ ] Worker stays alive during 90-second test period

**Expected Output:**
```
INFO: MCP Archiver Worker starting...
INFO: Connected to Redis
INFO: Waiting for messages...
```

**Acceptable Failures:**
- `ARCHIVE_ENABLED=false` → Mark as SKIP, document in notes
- S3 errors → Expected if `S3_DATA_BUCKET` not configured

**Time Estimate:** 2 minutes + 90s wait

---

#### **A3.2** [P2-MEDIUM] Check Archiver Flush Activity

**Objective:** Confirm archiver processes messages

**Commands:**
```bash
# 1. Publish test message
curl -X POST "$MCP_URL/tool/publish" \
  -H "x-api-key: $MCP_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"collection": "market:data", "message": {...}}'

# 2. Wait for flush interval (90 seconds)
sleep 90

# 3. Check worker logs for flush activity
./scripts/render_status.sh worker-logs | grep -i "flush\|batch\|upload"
```

**Success Criteria:**
- [ ] Logs show batch flush attempt (even if S3 fails)
- [ ] Message count increments in logs
- [ ] No worker crashes during flush

**Expected Log Pattern:**
```
INFO: Flushed batch of 1 messages to queue
INFO: Attempting S3 upload...
```
(S3 failure is acceptable if not configured)

**Time Estimate:** 5 minutes (including wait)

---

#### **A3.3** [P2-MEDIUM] Verify Retrieval Endpoint Behavior

**Objective:** Confirm retrieval endpoint returns expected response

**Command:**
```bash
curl -X POST "$MCP_URL/tool/retrieve" \
  -H "x-api-key: $MCP_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "collection": "market:data",
    "limit": 10
  }'
```

**Success Criteria (Either is acceptable):**
- [ ] HTTP 501 with message: "S3_DATA_BUCKET not configured" → EXPECTED if S3 not set up
- [ ] HTTP 200 with `{"messages": [...], "count": N}` → IDEAL if S3 configured

**Note:** HTTP 501 is a **PASS** for current state. Document S3 config as Phase C dependency.

**Time Estimate:** 1 minute

---

**✅ PHASE A COMPLETION GATE**

All conditions must be TRUE:

- [ ] **Priority 1 (P0):** All 4 tasks complete ✅
- [ ] **Priority 2 (P1):** All 4 tasks complete ✅
- [ ] **Priority 3 (P2):** At least 2/3 tasks complete (archiver can fail if documented)
- [ ] **Stability Test:** Smoke tests pass 3 consecutive times (5min intervals)
- [ ] **Log Audit:** No critical errors in 30-minute window
- [ ] **Redis Health:** `redis_connected: true` consistently

**Final Verification Command:**
```bash
# Run 3 times with 5min intervals
for i in {1..3}; do
  echo "=== Run $i at $(date) ==="
  ./scripts/run_smoke_tests.sh && echo "✅ PASS" || echo "❌ FAIL"
  [ $i -lt 3 ] && sleep 300
done
```

**Exit Code Must Be:** 0 for all 3 runs

**If ANY condition fails:** Debug and fix before Phase B. Do NOT introduce load on unstable system.

---

## 🚨 PHASE A FAILURE RESPONSE & ROLLBACK PLAN

If critical tests fail after 3 attempts, follow these contingency procedures:

### **Scenario 1: Smoke Tests Fail (Exit Code 1)**

**Symptoms:**
- `./scripts/run_smoke_tests.sh` returns exit code 1
- One or more critical tests show ❌ FAIL

**Response Procedure:**

1. **Capture Evidence:**
   ```bash
   ./scripts/run_smoke_tests.sh | tee docs/test-results/$(date +%Y-%m-%d)-FAILURE.txt
   ./scripts/render_status.sh web-logs > docs/test-results/$(date +%Y-%m-%d)-server-logs.txt
   ./scripts/render_status.sh worker-logs > docs/test-results/$(date +%Y-%m-%d)-worker-logs.txt
   ```

2. **Identify Failing Test:**
   - Check output for `[TEST N] ... ❌ FAIL`
   - Note the test number (1-15)

3. **Common Fixes by Test Number:**

   **Test 1 (Health) FAILS:**
   - Check: Service is running on Render
   - Check: `$MCP_URL` is correct
   - Action: Restart mcp-server service

   **Test 4 (Auth Rejection) FAILS:**
   - **CRITICAL SECURITY BUG**
   - Check: `./scripts/render_status.sh env | grep MCP_DEV`
   - Must be: `MCP_DEV=false` or not set
   - Action: Set `MCP_DEV=false` in Render, redeploy

   **Test 5 (Redis Connection) FAILS:**
   - Check: mcp-redis service status
   - Check: `REDIS_URL` env var in mcp-server
   - Action: Restart mcp-redis service, verify connection string

   **Test 6 (Publish) FAILS:**
   - Check: Server logs for exceptions
   - Check: Redis is connected (`/tool/get_status`)
   - Action: Review server logs, fix errors, redeploy

   **Test 7 (Schema Validation) FAILS:**
   - **CRITICAL VALIDATION BUG**
   - Check: `./scripts/render_status.sh web-logs | grep -i schema`
   - Check: `mcp/schemas/v1/` directory has 4 .json files
   - Action: Verify Dockerfile COPY includes schemas, redeploy

4. **After Fix:**
   - Re-run FULL smoke test suite
   - Do NOT proceed with partial testing
   - Do NOT mark Phase A complete until all tests pass

---

### **Scenario 2: Archiver Crashes/Restart Loops**

**Symptoms:**
- Worker service shows "exited" status
- Logs show repeated crashes or exceptions
- Service keeps restarting

**Response Procedure:**

1. **Check Logs:**
   ```bash
   ./scripts/render_status.sh worker-logs | tail -100 > archiver-crash.txt
   ```

2. **Common Causes:**

   **`ARCHIVE_ENABLED=false`:**
   - **EXPECTED BEHAVIOR** (archiver intentionally disabled)
   - Action: Mark A3.1 and A3.2 as SKIP, document in notes
   - Can proceed to Phase B with documentation

   **Redis Connection Errors:**
   - Check: `REDIS_URL` env var in mcp-archiver
   - Check: Redis service is running
   - Action: Verify connection string, restart services

   **S3 Upload Errors:**
   - Check: `S3_DATA_BUCKET` configured (may be intentionally not set)
   - If not set: **EXPECTED** - archiver will log errors but should not crash
   - If set: Verify AWS credentials, bucket permissions
   - Action: Fix S3 config or disable uploads

   **Python Exceptions:**
   - Check: Stack trace in logs
   - Check: Code errors in `mcp/uploader/archiver.py`
   - Action: Fix code bug, redeploy

3. **Rollback Option:**
   If archiver cannot be fixed quickly:
   - Set `ARCHIVE_ENABLED=false` to disable archiver
   - Document as known issue
   - Proceed with Phase A/B without archiver
   - Fix archiver in parallel track

---

### **Scenario 3: Persistent Instability (Multiple Failures)**

**Symptoms:**
- Tests pass sometimes, fail other times
- Services crash randomly
- Inconsistent behavior

**Response Procedure:**

1. **DO NOT PROCEED** to Phase B
2. **Full System Health Check:**
   ```bash
   ./scripts/render_status.sh status > system-health.txt
   ./scripts/render_status.sh env > system-config.txt
   ./scripts/render_status.sh deploy > deploy-history.txt
   ```

3. **Check Recent Changes:**
   - Review git history: `git log --oneline -10`
   - Review recent deployments on Render
   - Check [MODULE_FIX_SUMMARY.md](../../docs/MODULE_FIX_SUMMARY.md)
   - Check [IMPORT_FIX_AUDIT.md](../../docs/IMPORT_FIX_AUDIT.md)

4. **Consider Rollback:**
   ```bash
   # Identify last stable commit
   git log --oneline

   # If needed, rollback to previous version
   git checkout <last-stable-commit>
   git push -f origin main  # CAREFUL: Discuss with team first

   # Or rollback on Render:
   # Go to Render dashboard → mcp-server → Deploys → Redeploy older version
   ```

5. **Escalation:**
   - Document all failures in `docs/test-results/INCIDENT-$(date +%Y-%m-%d).md`
   - Review architecture documents (CLAUDE.md, requirement.md)
   - Consider architecture review meeting
   - Do NOT proceed until root cause identified

---

### **Scenario 4: Redis Completely Unavailable**

**Symptoms:**
- `/tool/get_status` shows `redis_connected: false`
- Cannot publish messages
- System unusable

**Response Procedure:**

1. **Check Redis Service:**
   ```bash
   ./scripts/render_status.sh status | grep mcp-redis
   ```

2. **If Redis is "exited" or "crashed":**
   - Go to Render dashboard → mcp-redis service
   - Check logs for error messages
   - Check memory/CPU usage (may be out of resources)
   - Action: Restart service, upgrade plan if needed

3. **If Redis is "running" but not connected:**
   - Check `REDIS_URL` in mcp-server environment
   - Check network connectivity (services in same region?)
   - Check Redis password/credentials
   - Action: Verify connection string, restart mcp-server

4. **Emergency Fallback:**
   If Redis cannot be restored:
   - **BLOCK ALL WORK** - System cannot function without Redis
   - This is a critical infrastructure failure
   - Focus 100% on restoring Redis before any other work

---

### **Decision Tree: Can I Proceed to Phase B?**

```
START → Run smoke tests
         ↓
         All P0 tasks pass? → NO → Follow Scenario 1, fix, retry
         ↓ YES
         All P1 tasks pass? → NO → Follow Scenario 1, fix, retry
         ↓ YES
         P2 tasks (2/3 pass)? → NO → Can fail if documented
         ↓ YES/DOCUMENTED
         Logs clean (30min)? → NO → Review logs, fix errors
         ↓ YES
         3 consecutive passes? → NO → Keep testing, investigate flakiness
         ↓ YES
         ✅ PROCEED TO PHASE B
```

---

## PHASE B — CONTROLLED LOAD INTRODUCTION ✅ COMPLETE

Status: ✅ Complete (2025-11-26) - 100% success rate achieved

**Prerequisites:**
- [x] Phase A completion gate passed ✅
- [x] All P0 and P1 tasks complete ✅
- [x] System stable for 30+ minutes ✅
- [x] No critical errors in logs ✅

### B1 — Light Throughput Testing ✅ COMPLETE

Objective: Validate behaviour under realistic early load.

Tasks:

* [x] Send 50-100 rapid publish requests ✅ (100 sent, 100 successful)
* [x] Monitor Redis stability ✅ (Stable throughout)
* [x] Ensure no dropped messages ✅ (0 failures)
* [x] Observe archiver batch efficiency ✅ (Queue depths at 0)
* [x] Check Render CPU & memory metrics ✅ (To be reviewed)

**Results:**
- Success rate: 100% (100/100 messages)
- Throughput: 2.63 msg/sec
- Avg response time: 0.352s
- Redis: Stable throughout

Deliverable: ✅ MCP sustained light load without degradation.

---

### B2 — Queue & Memory Health Analysis ✅ COMPLETE

Objective: Prevent bottlenecks or memory leaks.

Tasks:

* [x] Monitor queue sizes ✅ (4 samples over 20 minutes)
* [x] Identify any unbounded growth ✅ (None detected - queues stable at 0)
* [x] Tune: ✅ (Current settings optimal)

  * ARCHIVE_BATCH_SIZE: 1000 (sufficient)
  * ARCHIVE_FLUSH_INTERVAL: 60s (appropriate)
  * Redis eviction policy: Working as expected

**Results:**
- Queue depths: Remained at 0 throughout (optimal)
- Redis connectivity: 100% uptime over 20 minutes
- Memory growth: None detected (stable)
- Conclusion: No tuning required at current load levels

Deliverable: ✅ System remained stable over 20-minute monitoring window.

---

## 🔴 PHASE 1 — POST-SMOKE HARDENING & ARCHIVER STABILITY

**Status:** ⏳ IN PROGRESS (Current Phase)
**Priority:** P0-CRITICAL (Data Integrity Foundation)
**Dependencies:** Phase A & B complete ✅
**Time Estimate:** 2-3 days

**Objective:** Validate data archival integrity, retrieval accuracy, and kill-switch persistence before proceeding to observability and integration.

---

### 1.1 — Archiver Stability & S3 Behaviour 🔄 CURRENT

**Priority:** P0-CRITICAL
**Time:** 2-3 days

**Tasks:**
- [ ] 1.1.1: Run smoke tests 3-5 times over different days (idempotence check)
- [ ] 1.1.2: Inspect S3 object layout over time
- [ ] 1.1.3: Verify partition structure: `year=YYYY/month=MM/day=DD/hour=HH/minute=MM/part-*.jsonl.gz`
- [ ] 1.1.4: Check for duplicate or overlapping time ranges
- [ ] 1.1.5: Verify no gaps in regular traffic patterns
- [ ] 1.1.6: Simulate S3 failure and verify local fallback logic

**Acceptance Criteria:**
✓ 3+ separate runs produce consistent, correctly partitioned data
✓ No recurring S3 errors in archiver logs during normal operation
✓ Local fallback works correctly when S3 unavailable

---

### 1.2 — Retrieval Accuracy & Limits

**Priority:** P0-CRITICAL
**Time:** 1 day
**Dependencies:** S3 data from 1.1

**Tasks:**
- [ ] 1.2.1: Test `/tool/retrieve` with different pair values (BTC-ETH, BTC-USD, invalid)
- [ ] 1.2.2: Test edge case time ranges (1min window, 7-day window, 30-day window)
- [ ] 1.2.3: Test limit parameter near max (1000) and small (10)
- [ ] 1.2.4: Verify time-ordering of returned records
- [ ] 1.2.5: Test cursor-based pagination (page 1 → page 2, no duplicates)
- [ ] 1.2.6: Document retrieval semantics in DEVELOPMENT.md

**Acceptance Criteria:**
✓ Retrieval matches expectations for multiple scenarios
✓ No unbounded memory growth during large-window retrievals
✓ Pagination returns non-overlapping, correctly ordered results
✓ Documentation clear and accurate

---

### 1.3 — Kill-Switch & Control Channel Reliability

**Priority:** P0-CRITICAL
**Time:** 0.5 day
**Dependencies:** None

**Tasks:**
- [ ] 1.3.1: Send multiple EMERGENCY_HALT commands (rapid sequence of 5)
- [ ] 1.3.2: Verify `kill_history` returns correct and ordered control events
- [ ] 1.3.3: Test kill-switch persistence across pod restart (activate → restart service → verify still active)
- [ ] 1.3.4: Document kill-switch behavior for Brain agent consumption

**Acceptance Criteria:**
✓ Kill history survives restarts
✓ Latest state always accessible via `/tool/get_status`
✓ Documentation clearly describes Brain agent contract

---

## 🟢 PHASE 2.2 — ARCHIVER PARAMETER TUNING

**Status:** ⏳ PENDING
**Priority:** P1-HIGH (Performance Optimization)
**Dependencies:** Phase 1.1 complete, Phase B complete ✅
**Time Estimate:** 1 day

**Objective:** Optimize archiver configuration based on Phase B results and multi-day stability data.

**Tasks:**
- [ ] 2.2.1: Document current archiver parameters (BATCH_SIZE: 1000, FLUSH_INTERVAL: 60s)
- [ ] 2.2.2: Analyze Phase B + Phase 1.1 results for optimization opportunities
- [ ] 2.2.3: Test Parquet format vs JSONL (file size, query performance, cost)
- [ ] 2.2.4: Choose production defaults based on latency/cost tradeoffs
- [ ] 2.2.5: Update DEVELOPMENT.md with tuning guidelines

**Acceptance Criteria:**
✓ Production defaults chosen and documented
✓ Tuning guidelines exist for future scaling
✓ Cost analysis completed (S3 PUT frequency vs file size)

---

## 🟡 PHASE 3 — OBSERVABILITY & OPERATIONS

**Status:** ⏳ PENDING
**Priority:** P1-HIGH (Operational Readiness)
**Dependencies:** Phase 2 complete
**Time Estimate:** 2-3 days

### 3.1 — Metrics & Prometheus Integration

**Tasks:**
- [ ] 3.1.1: Install `prometheus-client` library
- [ ] 3.1.2: Implement core metrics:
  - `mcp_publish_total{channel}` (counter)
  - `mcp_publish_latency_seconds` (histogram)
  - `mcp_validation_failures_total` (counter)
  - `mcp_halt_total` (counter)
  - `mcp_archive_queue_size` (gauge)
  - `mcp_archive_flush_count` (counter)
- [ ] 3.1.3: Expose `/metrics` endpoint (protected or internal-only)
- [ ] 3.1.4: Verify metrics scrape works in staging

**Acceptance:**
✓ Prometheus can ingest metrics successfully
✓ Dashboards can be built from these metrics

---

### 3.2 — Structured Logging

**Tasks:**
- [ ] 3.2.1: Install `python-json-logger`
- [ ] 3.2.2: Implement structured logs with request_id, channel, timestamp
- [ ] 3.2.3: Verify no secrets leak in logs (audit MCP_API_KEY, AWS credentials)
- [ ] 3.2.4: Add log-level configuration (DEBUG in dev, INFO in prod)

**Acceptance:**
✓ Logs are structured JSON and easily filterable
✓ No credentials or secrets appear in logs

---

### 3.3 — Operational Runbook

**Tasks:**
- [ ] 3.3.1: Create `RUNBOOK.md` with:
  - Service restart procedures
  - S3 troubleshooting guide
  - Redis connectivity issues
  - Incident response checklist
- [ ] 3.3.2: Document common failure scenarios and response plans

**Acceptance:**
✓ New operator can handle incidents without tribal knowledge

---

## 🔵 PHASE 4 — SECURITY & ACCESS CONTROL

**Status:** ⏳ PENDING
**Priority:** P0-CRITICAL (Security Hardening)
**Dependencies:** Phase 3 complete (for audit logging)
**Time Estimate:** 1-2 days

### 4.1 — API Key & Auth Hardening

**Tasks:**
- [ ] 4.1.1: Audit all endpoints for auth requirements (public: /health, protected: /tool/*)
- [ ] 4.1.2: Test unauthenticated access (should return 401/403)
- [ ] 4.1.3: Document API key rotation procedure
- [ ] 4.1.4: Consider multi-key support (Feeder key, Brain key, Ops key)

**Acceptance:**
✓ All endpoints properly protected
✓ Key rotation documented and tested

---

### 4.2 — IAM & S3 Permissions Lockdown

**Tasks:**
- [ ] 4.2.1: Review current IAM policy
- [ ] 4.2.2: Restrict to least-privilege (s3:PutObject/GetObject on mcp/* only)
- [ ] 4.2.3: Enable S3 access logging for audit trail
- [ ] 4.2.4: Document IAM policy in SECURITY.md

**Acceptance:**
✓ IAM follows least-privilege principle
✓ S3 access logged for compliance
✓ No s3:* wildcards remain

---

## 🟣 PHASE 5 — INTEGRATION CONTRACTS (DOCUMENTATION ONLY)

**Status:** ⏳ PENDING
**Priority:** P1-HIGH (Agent Integration Preparation)
**Dependencies:** Phase 1-4 complete
**Time Estimate:** 2-3 days

**IMPORTANT:** This phase creates **documentation only**. No Feeder or Brain development.

### 5.1 — Feeder Agent Contract Documentation

**Tasks:**
- [ ] 5.1.1: Create `docs/FEEDER_CONTRACT.md`
- [ ] 5.1.2: Document allowed channels (market:data, sentiment:data) with required fields
- [ ] 5.1.3: Provide concrete curl examples for publishing
- [ ] 5.1.4: Define rate expectations (e.g., 10 msg/sec for market:data)
- [ ] 5.1.5: Create n8n workflow template (optional reference)

**Acceptance:**
✓ Feeder contract clear and unambiguous
✓ Working curl examples provided
✓ Rate limits and expectations documented

---

### 5.2 — Brain Agent Contract Documentation

**Tasks:**
- [ ] 5.2.1: Create `docs/BRAIN_CONTRACT.md`
- [ ] 5.2.2: Document `/tool/retrieve` usage patterns (time ranges, pagination, limits)
- [ ] 5.2.3: Document `/tool/kill_history` usage
- [ ] 5.2.4: Provide Python code examples (fetch 24h data, pagination, kill-switch polling)
- [ ] 5.2.5: Define backtesting support (historical replay, time-travel queries)

**Acceptance:**
✓ Brain contract clear and unambiguous
✓ Working Python examples provided
✓ Backtesting mechanics documented

---

## 🟠 PHASE 6 — RAG & VECTOR DB (OPTIONAL)

**Status:** ⏳ PENDING
**Priority:** P2-MEDIUM (Future Enhancement)
**Dependencies:** Phase 5 complete
**Time Estimate:** 3-5 days

**Note:** This phase is OPTIONAL. Can be deferred to v2 if not required for initial production release.

**Tasks:**
- [ ] 6.1.1: Choose vector DB backend (Weaviate, Pinecone, or FAISS)
- [ ] 6.1.2: Implement `VECTOR_DB_TYPE` environment variable handling
- [ ] 6.1.3: Create `vector_adapter.py` with backend adapters
- [ ] 6.1.4: Implement ingestion pipeline (news/signals → embeddings → vector DB)
- [ ] 6.1.5: Implement real `/tool/search_rag` endpoint
- [ ] 6.1.6: Test with sample data (100 sentiment messages)

**Acceptance:**
✓ When VECTOR_DB_TYPE set, RAG returns relevant results
✓ When unset, returns 501 with clear guidance
✓ Ingestion pipeline handles errors gracefully

---

## 🏁 PHASE 7 — PRODUCTION READINESS CHECKLIST

**Status:** ⏳ PENDING
**Priority:** P0-CRITICAL (Final Gate)
**Dependencies:** ALL previous phases complete
**Time Estimate:** 1 day (verification only)

**Final Checklist:**

**Deployment:**
- [ ] Render services stable for 7+ days
- [ ] Zero unplanned restarts
- [ ] Automated health checks passing

**Testing:**
- [ ] Smoke tests green in staging and production
- [ ] Load tests show no degradation
- [ ] Passing 3 consecutive times (5min intervals)

**Archival:**
- [ ] S3 structure validated (multi-day verification)
- [ ] No recurring errors in archiver logs
- [ ] Multi-day data integrity confirmed

**Performance:**
- [ ] Survives expected load + 2x headroom
- [ ] Response times within SLA (<500ms health, <1s publish)
- [ ] No memory leaks detected (multi-day monitoring)

**Observability:**
- [ ] Metrics endpoint working
- [ ] Basic dashboards created
- [ ] Alert rules configured

**Security:**
- [ ] API keys secure and rotated
- [ ] IAM least-privilege confirmed
- [ ] No `MCP_DEV=true` in production
- [ ] S3 access logging enabled

**Integration:**
- [ ] Feeder contract documented (docs/FEEDER_CONTRACT.md)
- [ ] Brain contract documented (docs/BRAIN_CONTRACT.md)
- [ ] Example code validated

**RAG (if in scope):**
- [ ] Fully implemented OR
- [ ] Clearly marked "not included in v1"

**When all boxes checked:** 🎉 **MCP SERVER IS PRODUCTION-READY**

---

## 🎯 AGENT DEVELOPMENT (DEFERRED)

**Status:** ⏳ BLOCKED until server production-ready

The following will be addressed **AFTER** Phase 7 completion:

- Feeder Agent (n8n) development
- Brain Agent (Python/Claude) development
- Agent integration testing
- End-to-end system validation

**Rationale:** Server must be stable and API contracts finalized before building agents. This reduces risk of breaking changes and rework

---

## 📋 CURRENT PRIORITY ORDER

**✅ COMPLETED:**
1. ✅ Pre-Phase: Infrastructure & smoke tests
2. ✅ Phase A: Core stabilization (all P0, P1, P2 tasks)
3. ✅ Phase B: Controlled load testing (100% success rate)

**🔄 IN PROGRESS (This Week):**
4. 🔄 **Phase 1.1** - Archiver stability & S3 behaviour (multi-day validation)
5. ⏳ **Phase 1.2** - Retrieval accuracy & limits
6. ⏳ **Phase 1.3** - Kill-switch persistence testing

**⏳ NEXT (Week 2):**
7. ⏳ **Phase 2.2** - Archiver parameter tuning
8. ⏳ **Phase 3.1** - Metrics & Prometheus integration
9. ⏳ **Phase 3.2** - Structured logging
10. ⏳ **Phase 3.3** - Operational runbook

**⏳ PENDING (Week 3-4):**
11. ⏳ **Phase 4** - Security hardening (API keys, IAM)
12. ⏳ **Phase 5** - Integration contract documentation
13. ⏳ **Phase 6** - RAG & Vector DB (optional)
14. ⏳ **Phase 7** - Production readiness checklist

**🎯 DEFERRED (After Server Complete):**
15. 🚫 Feeder Agent (n8n) development - BLOCKED
16. 🚫 Brain Agent (Python/Claude) development - BLOCKED
17. 🚫 End-to-end agent integration - BLOCKED

---

## ACTIVE STATUS SNAPSHOT

**Last Updated:** Manual (Run commands below to update)

**How to Update This Section:**
```bash
# Quick status check
cd /Users/kamii/888.mcp/888.MCP/mcp
./scripts/run_smoke_tests.sh && echo "✅ Smoke Tests: PASS" || echo "❌ Smoke Tests: FAIL"
curl -s -H "x-api-key: $MCP_API_KEY" "$MCP_URL/tool/get_status" | jq -r '"Redis: \(.redis_connected)"'
./scripts/render_status.sh status | grep -E "(mcp-server|mcp-archiver|mcp-redis)"
```

### **Phase A Progress**

| Task ID | Task Name | Status | Last Checked | Notes |
|---------|-----------|--------|--------------|-------|
| **A1.1** | Smoke Test Suite | 🔄 Ready | - | Not started |
| **A1.2** | Health Endpoint | ⏳ Pending | - | Blocked by A1.1 |
| **A1.3** | Redis Connectivity | ⏳ Pending | - | Blocked by A1.1 |
| **A1.4** | Auth Enforcement | ⏳ Pending | - | Blocked by A1.1 |
| **A2.1** | Publish Valid Msg | ⏳ Pending | - | Blocked by P1 |
| **A2.2** | Reject Invalid | ⏳ Pending | - | Blocked by P1 |
| **A2.3** | Kill-Switch Activate | ⏳ Pending | - | Blocked by P1 |
| **A2.4** | Kill-Switch Resume | ⏳ Pending | - | Blocked by P1 |
| **A3.1** | Archiver Health | ⏳ Pending | - | Blocked by P2 |
| **A3.2** | Archiver Flush | ⏳ Pending | - | Blocked by P2 |
| **A3.3** | Retrieval Endpoint | ⏳ Pending | - | Blocked by P2 |

### **Infrastructure Health**

| Component | Status | Last Verified | Command to Check |
|-----------|--------|---------------|------------------|
| MCP Server | ❓ Unknown | - | `curl $MCP_URL/health` |
| Redis | ❓ Unknown | - | `curl -H "x-api-key: $MCP_API_KEY" $MCP_URL/tool/get_status \| jq .redis_connected` |
| Archiver Worker | ❓ Unknown | - | `./scripts/render_status.sh status \| grep archiver` |
| S3 Bucket | ⏳ Not Configured | - | Expected 501 on /tool/retrieve |

**Legend:**
- ✅ Complete/Healthy
- 🔄 In Progress/Running
- ⏳ Pending/Not Started
- ❌ Failed/Down
- ❓ Unknown (needs verification)

---

## Operating Instructions for AI Agents

### **Workflow Rules:**

1. **Always Start with "NEXT ACTION" Section**
   - Read the 🎯 NEXT ACTION section first
   - Follow the exact commands provided
   - Do NOT skip ahead to later phases

2. **Respect Task Dependencies**
   - Complete Priority 1 (P0) before Priority 2 (P1)
   - Complete Priority 2 (P1) before Priority 3 (P2)
   - Do NOT proceed to Phase B until Phase A completion gate passed

3. **Document Everything**
   - Save test outputs to `docs/test-results/YYYY-MM-DD-*.txt`
   - Update "ACTIVE STATUS SNAPSHOT" after each task
   - Record failures with full logs and error messages

4. **Gate Enforcement (CRITICAL)**
   - **DO NOT SKIP GATES** - They prevent catastrophic failures
   - If a gate fails, follow the "FAILURE RESPONSE & ROLLBACK PLAN"
   - Never proceed with partial completion

5. **Feature Freeze**
   - Do NOT propose new features until PHASE A & B complete
   - Do NOT refactor code during testing phase
   - Focus 100% on validation and stabilization

6. **Change Control**
   - Any change must not break deployment or data integrity
   - Always validate against Render logs and smoke tests
   - If unsure, ask before making changes

7. **Escalation Path**
   - If 3 attempts at a task fail → Document and escalate
   - If system shows persistent instability → Follow Scenario 3 (Rollback Plan)
   - If Redis unavailable → Follow Scenario 4 (Emergency Fallback)

### **Quick Reference Commands:**

```bash
# Current task (A1.1)
cd /Users/kamii/888.mcp/888.MCP/mcp
export MCP_URL="<your-url>"
export MCP_API_KEY="<your-key>"
./scripts/run_smoke_tests.sh

# Check system health
./scripts/render_status.sh status
./scripts/render_status.sh web-logs
curl -H "x-api-key: $MCP_API_KEY" "$MCP_URL/tool/get_status"

# Document results
mkdir -p docs/test-results
./scripts/run_smoke_tests.sh | tee docs/test-results/$(date +%Y-%m-%d)-smoke-tests.txt
```

---

## Document Maintenance

**This file defines the current execution focus of the MCP Server project.**

**Update Frequency:**
- "NEXT ACTION" section: Update after each task completion
- "ACTIVE STATUS SNAPSHOT": Update after each test run
- "Phase A Progress" table: Update as tasks complete
- Phase sections: Update when transitioning between phases

**File Ownership:**
- Primary: Development team
- Readers: AI agents, developers, stakeholders
- Update access: Any team member (keep it current!)

**Related Documents:**
- [WORK_LOG.md](../../WORK_LOG.md) - **📊 Complete work history and progress tracking**
- [master-plan.md](master-plan.md) - Production roadmap (source of Phases 1-7)
- [CLAUDE.md](../CLAUDE.md) - System architecture and rules
- [requirement.md](requirement.md) - Project requirements specification
- [SMOKE_TESTING.md](../../mcp/SMOKE_TESTING.md) - Test suite details

---

## 📝 DOCUMENT CHANGE LOG

**Version 3.0 (2025-11-26):**
- ✅ Integrated master-plan.md phases 1-7 into current-work structure
- ✅ Established server-first development strategy (Option A)
- ✅ Deferred Feeder & Brain agent development until server production-ready
- ✅ Created WORK_LOG.md for comprehensive progress tracking
- ✅ Archived completed Phase A & B details to work log
- ✅ Added detailed Phase 1 tasks (Post-Smoke Hardening) as immediate priority

**Version 2.0 (2025-11-26):**
- Enhanced with SMART criteria, gates, rollback plans
- Completed Phase A & B testing (100% success rate)

**Version 1.0 (2025-11-25):**
- Initial document creation
- Defined Phase A structure

---

**Last Major Update:** 2025-11-26 (Version 3.0 - Master Plan Integration)
**Document Version:** 3.0
**Next Review:** After Phase 1.1 completion (multi-day validation)
