# MCP Server - Smoke Testing Guide

Complete guide for running end-to-end smoke tests against the MCP (Message & Compute Protocol) server deployed on Render.com.

---

## 📋 Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Quick Start](#quick-start)
4. [Test Suite Details](#test-suite-details)
5. [Configuration](#configuration)
6. [Running Tests](#running-tests)
7. [Interpreting Results](#interpreting-results)
8. [Troubleshooting](#troubleshooting)
9. [CI/CD Integration](#cicd-integration)
10. [Advanced Usage](#advanced-usage)

---

## Overview

The smoke test suite validates critical functionality of the deployed MCP server:

- ✅ **Connectivity** - Health checks and service discovery
- ✅ **Authentication** - API key validation and security
- ✅ **Publishing** - Message publishing with schema validation
- ✅ **Kill-Switch** - Emergency halt and resume commands
- ✅ **Archiver** - Background worker validation
- ✅ **Optional Features** - S3 retrieval, RAG search (if configured)

**Test Coverage:** 15 tests across 6 phases
**Execution Time:** ~3 minutes (includes 90s archiver wait)
**Exit Codes:**
- `0` - All critical tests passed
- `1` - Critical failures detected
- `2` - Configuration error

---

## Prerequisites

### Required Tools

1. **curl** - For HTTP requests
   ```bash
   # macOS
   brew install curl

   # Linux
   apt install curl
   ```

2. **bash** - Shell version 4.0+ (macOS/Linux default)

### Optional but Recommended

3. **jq** - For better JSON parsing and validation
   ```bash
   # macOS
   brew install jq

   # Linux
   apt install jq
   ```

4. **Render CLI** - For log analysis and service inspection
   ```bash
   # Install (macOS ARM64)
   curl -L https://github.com/render-oss/cli/releases/download/v2.5.0/cli_2.5.0_darwin_arm64.zip -o render.zip
   unzip render.zip
   chmod +x cli_v2.5.0
   mv cli_v2.5.0 ~/bin/render

   # Authenticate
   render login
   ```

### Environment Information

You'll need to get these values from your Render dashboard:

- **MCP_URL** - Your web service URL (e.g., `https://mcp-server-abc123.onrender.com`)
- **MCP_API_KEY** - API key from environment variables (in Render web service settings)

---

## Quick Start

### 1. Set Environment Variables

```bash
export MCP_URL="https://your-mcp-server.onrender.com"
export MCP_API_KEY="your-secret-api-key"
```

### 2. Run Tests

```bash
cd mcp
./scripts/run_smoke_tests.sh
```

### 3. Check Results

The script will output colored test results:
- 🟢 **GREEN** = Test passed
- 🔴 **RED** = Test failed
- 🟡 **YELLOW** = Warning or expected failure (e.g., S3 not configured)

---

## Test Suite Details

### Phase 1: Connectivity & Basic Health (3 tests)

#### Test 1: Health Check
- **Endpoint:** `GET /health`
- **Auth:** None (public)
- **Expected:** HTTP 200, `{"status": "ok", ...}`
- **Purpose:** Verify web service is responding

#### Test 2: Discovery Endpoint
- **Endpoint:** `GET /.well-known/mcp`
- **Auth:** None (public)
- **Expected:** HTTP 200, metadata with 4 channels
- **Purpose:** Validate schema files loaded correctly

#### Test 3: List Collections
- **Endpoint:** `GET /tool/list_collections`
- **Auth:** None (public)
- **Expected:** HTTP 200, `{"total": 4}`
- **Purpose:** Confirm channel enumeration works

### Phase 2: Authentication (2 tests)

#### Test 4: Auth Rejection
- **Endpoint:** `GET /tool/get_status` (no API key)
- **Auth:** None
- **Expected:** HTTP 401 or 403
- **Purpose:** **Security test** - ensure protected endpoints reject unauth requests

**🚨 CRITICAL:** If this returns HTTP 200, you have a security bug!

#### Test 5: Auth Success
- **Endpoint:** `GET /tool/get_status` (with API key)
- **Auth:** `x-api-key` header
- **Expected:** HTTP 200, `{"redis_connected": true, ...}`
- **Purpose:** Validate Redis connectivity and authentication

### Phase 3: Core Functionality (3 tests)

#### Test 6: Publish Valid Message
- **Endpoint:** `POST /tool/publish`
- **Auth:** Required
- **Payload:** Valid `market:data` message with unique `pair`
- **Expected:** HTTP 200, `{"success": true}`
- **Purpose:** Validate end-to-end publish pipeline

#### Test 7: Invalid Message Rejection
- **Endpoint:** `POST /tool/publish`
- **Payload:** Message missing `schema_version`
- **Expected:** HTTP 400 or 422
- **Purpose:** Validate JSON schema enforcement

#### Test 8: Invalid Channel Rejection
- **Endpoint:** `POST /tool/publish`
- **Payload:** Message to non-existent channel
- **Expected:** HTTP 400
- **Purpose:** Validate channel name validation

### Phase 4: Archiver Validation (1 test)

#### Test 9: Archiver Flush Wait
- **Action:** Wait 90 seconds for archiver flush interval
- **Purpose:** Allow time for background worker to process messages
- **Note:** Archiver is currently a **STUB** (logs only, no S3 writes yet)

**What to check:**
- Worker stays running (no crash loops)
- Logs show: `"MCP Archiver Worker starting..."`
- No exceptions in worker logs

### Phase 5: Kill-Switch Logic (3 tests)

#### Test 10: EMERGENCY_HALT Activation
- **Endpoint:** `POST /tool/publish` to `agent:control`
- **Payload:** `{"command": "EMERGENCY_HALT", ...}`
- **Expected:** HTTP 200, message published

#### Test 11: Kill-Switch Verification
- **Endpoint:** `GET /tool/get_status`
- **Expected:** `{"status": "EMERGENCY_HALT", "kill_switch": {"active": true}}`
- **Purpose:** Verify persistence to Redis key `mcp:kill_switch`

#### Test 12: RESUME (Clear Kill-Switch)
- **Endpoint:** `POST /tool/publish` to `agent:control`
- **Payload:** `{"command": "RESUME", ...}`
- **Expected:** `kill_switch.active` returns to `false`

### Phase 6: Optional Features (2 tests)

#### Test 13: Historical Data Retrieval
- **Endpoint:** `POST /tool/retrieve`
- **Expected:** HTTP 501 (S3 not configured) OR HTTP 200 (working)
- **Purpose:** Validate retrieval endpoint behavior
- **Note:** 501 is **PASS** if S3 is not configured

#### Test 14: RAG Search Placeholder
- **Endpoint:** `POST /tool/search_rag`
- **Expected:** HTTP 501 (not implemented)
- **Purpose:** Confirm placeholder returns expected error
- **Note:** 501 is **PASS** (feature not implemented yet)

---

## Configuration

### Option 1: Environment Variables (Quick)

```bash
export MCP_URL="https://mcp-server-abc123.onrender.com"
export MCP_API_KEY="your-api-key"
./scripts/run_smoke_tests.sh
```

### Option 2: Configuration File (Recommended)

1. **Create local config:**
   ```bash
   cp smoke_test.config smoke_test.local.config
   ```

2. **Edit `smoke_test.local.config`:**
   ```bash
   export MCP_URL="https://mcp-server-abc123.onrender.com"
   export MCP_API_KEY="your-actual-key"

   # Optional
   export S3_BUCKET="your-bucket-name"
   export AWS_REGION="us-west-2"
   ```

3. **Run with config:**
   ```bash
   ./scripts/run_smoke_tests.sh --config smoke_test.local.config
   ```

4. **Add to `.gitignore`:**
   ```bash
   echo "smoke_test.local.config" >> .gitignore
   ```

### Configuration Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `MCP_URL` | ✅ Yes | - | MCP server URL |
| `MCP_API_KEY` | ✅ Yes | - | API key for authentication |
| `S3_BUCKET` | ❌ No | - | S3 bucket for retrieval tests |
| `AWS_REGION` | ❌ No | `us-west-2` | AWS region |
| `ARCHIVER_WAIT_TIME` | ❌ No | `90` | Seconds to wait for archiver |
| `VERBOSE` | ❌ No | `false` | Show full curl responses |
| `WEB_SERVICE` | ❌ No | `mcp-server` | Render web service name |
| `WORKER_SERVICE` | ❌ No | `mcp-archiver` | Render worker name |
| `REDIS_SERVICE` | ❌ No | `mcp-redis` | Render Redis name |

---

## Running Tests

### Basic Usage

```bash
# Simple run (uses env vars)
./scripts/run_smoke_tests.sh

# With configuration file
./scripts/run_smoke_tests.sh --config smoke_test.local.config

# With logs after tests
./scripts/run_smoke_tests.sh --with-logs

# Status check only (no tests)
./scripts/run_smoke_tests.sh --status-only
```

### Individual Scripts

```bash
# Run smoke tests directly
./scripts/smoke_test.sh

# Check Render service status
./scripts/render_status.sh status

# Tail web server logs
./scripts/render_status.sh web-logs

# Tail worker logs
./scripts/render_status.sh worker-logs

# Show environment variables (masked)
./scripts/render_status.sh env

# Show recent deployments
./scripts/render_status.sh deploy
```

### Advanced Options

```bash
# Reduce archiver wait time (faster tests, may miss flush)
export ARCHIVER_WAIT_TIME=30
./scripts/run_smoke_tests.sh

# Enable verbose output
export VERBOSE=true
./scripts/smoke_test.sh

# Test against staging environment
export MCP_URL="https://mcp-server-staging.onrender.com"
./scripts/run_smoke_tests.sh
```

---

## Interpreting Results

### Exit Codes

```bash
./scripts/run_smoke_tests.sh
echo $?  # Check exit code
```

- **0** - All tests passed (or only optional features failed)
- **1** - Critical test failure (service broken)
- **2** - Configuration error (env vars not set)

### Output Format

```
[TEST 1] Health Check (Public Endpoint)
  ✓ PASS Health endpoint returned 200 with status=ok

[TEST 4] Auth Rejection (Status Without API Key)
  ✓ PASS Protected endpoint correctly rejected unauthenticated request (401)

[TEST 6] Publish Valid market:data Message
  ✗ FAIL Expected HTTP 200, got 500
    Response: {"detail": "Internal server error"}
```

### Success Criteria

**MUST PASS (Critical):**
- ✅ Health check returns 200
- ✅ Redis connected (`redis_connected: true`)
- ✅ Auth enforced (401 without API key)
- ✅ Valid messages publish successfully
- ✅ Invalid messages rejected
- ✅ Kill-switch persists to Redis

**SHOULD PASS (Important):**
- ✅ Archiver worker stays running
- ✅ Discovery endpoints work

**CAN FAIL (Expected in current state):**
- ⚠️ Retrieval returns 501 (S3 not configured)
- ⚠️ RAG returns 501 (not implemented)
- ⚠️ S3 files not found (archiver is stub)

---

## Troubleshooting

### Common Issues

#### 1. Connection Refused / Timeout

**Symptoms:**
```
[FAIL] Failed to connect to https://mcp-server.onrender.com/health
  Error: curl: (7) Failed to connect
```

**Causes:**
- Service is down or restarting
- Wrong URL (check Render dashboard)
- Network/firewall issue

**Solutions:**
```bash
# Check service status
./scripts/render_status.sh status

# View recent logs
./scripts/render_status.sh web-logs

# Check Render dashboard
# Go to: https://dashboard.render.com
```

#### 2. 401 Unauthorized on Protected Endpoints

**Symptoms:**
```
[FAIL] Expected HTTP 200, got 401
```

**Causes:**
- Wrong API key
- API key not set in Render
- Typo in `MCP_API_KEY`

**Solutions:**
```bash
# Verify API key in Render
./scripts/render_status.sh env

# Check your local value
echo $MCP_API_KEY

# Get correct value from Render:
# 1. Go to mcp-server service
# 2. Click Environment tab
# 3. Copy MCP_API_KEY value
```

#### 3. Security Bug - Auth Not Enforced

**Symptoms:**
```
[FAIL] SECURITY BUG: Protected endpoint returned 200 without authentication!
```

**Causes:**
- `MCP_DEV=true` in production
- Auth middleware disabled

**Solutions:**
```bash
# Check environment
./scripts/render_status.sh env | grep MCP_DEV

# In Render dashboard:
# 1. Go to mcp-server service
# 2. Environment tab
# 3. Ensure MCP_DEV=false (or not set)
# 4. Redeploy if changed
```

#### 4. Redis Not Connected

**Symptoms:**
```
[FAIL] Redis is not connected (redis_connected: false)
```

**Causes:**
- Redis service down
- Wrong `REDIS_URL`
- Network issue between services

**Solutions:**
```bash
# Check Redis service status
./scripts/render_status.sh status

# Check logs for connection errors
./scripts/render_status.sh web-logs | grep -i redis

# In Render dashboard:
# 1. Check mcp-redis service is running
# 2. Verify REDIS_URL env var is correct
# 3. Check service is in same region
```

#### 5. Schema Validation Failures

**Symptoms:**
```
[FAIL] CRITICAL BUG: Invalid message was accepted (HTTP 200)!
```

**Causes:**
- Schema files not loaded
- Schema directory missing in Docker image
- `load_schemas()` failed at startup

**Solutions:**
```bash
# Check startup logs
./scripts/render_status.sh web-logs | grep -i schema

# Look for:
# "Loaded schema for market:data"
# "Loaded schema for sentiment:data"
# etc.

# If schemas not loading:
# 1. Check mcp/schemas/v1/ exists in repo
# 2. Verify Dockerfile COPY includes schemas
# 3. Redeploy
```

#### 6. Archiver Worker Not Running

**Symptoms:**
```
Worker service shows "exited" status
Logs show: "Archiver is DISABLED via ARCHIVE_ENABLED=false"
```

**Causes:**
- `ARCHIVE_ENABLED=false` (may be intentional)
- Redis connection failure
- Uncaught exception

**Solutions:**
```bash
# Check worker logs
./scripts/render_status.sh worker-logs

# Check ARCHIVE_ENABLED setting
./scripts/render_status.sh env | grep ARCHIVE

# If should be enabled:
# 1. Go to mcp-archiver service in Render
# 2. Environment tab
# 3. Set ARCHIVE_ENABLED=true
# 4. Restart service
```

### Diagnostic Commands

```bash
# Full service status
./scripts/render_status.sh status

# Recent web logs (last 100 lines)
./scripts/render_status.sh web-logs

# Recent worker logs
./scripts/render_status.sh worker-logs

# Environment variables (masked secrets)
./scripts/render_status.sh env

# Recent deployments
./scripts/render_status.sh deploy

# Test single endpoint manually
curl -H "x-api-key: $MCP_API_KEY" "$MCP_URL/tool/get_status" | jq .
```

---

## CI/CD Integration

### GitHub Actions

Create `.github/workflows/smoke-tests.yml`:

```yaml
name: Smoke Tests

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]
  schedule:
    - cron: '0 */6 * * *'  # Every 6 hours

jobs:
  smoke-tests:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v3

      - name: Install dependencies
        run: |
          sudo apt-get update
          sudo apt-get install -y curl jq

      - name: Run smoke tests
        env:
          MCP_URL: ${{ secrets.MCP_URL }}
          MCP_API_KEY: ${{ secrets.MCP_API_KEY }}
        run: |
          cd mcp
          ./scripts/run_smoke_tests.sh

      - name: Upload test results
        if: always()
        uses: actions/upload-artifact@v3
        with:
          name: smoke-test-results
          path: mcp/test-results.txt
```

**Required Secrets (Settings → Secrets):**
- `MCP_URL` - Production/staging URL
- `MCP_API_KEY` - API key for tests

### Render Deploy Hooks

Add smoke tests after successful deploy:

```yaml
# render.yaml
services:
  - type: web
    name: mcp-server
    # ... existing config ...

    # Post-deploy hook (requires Render deploy hook)
    postDeployScript: |
      curl -X POST https://your-ci-server.com/trigger-smoke-tests
```

### Manual Trigger

```bash
# Trigger via curl
curl -X POST \
  -H "Authorization: token $GITHUB_TOKEN" \
  -H "Accept: application/vnd.github.v3+json" \
  https://api.github.com/repos/OWNER/REPO/actions/workflows/smoke-tests.yml/dispatches \
  -d '{"ref":"main"}'
```

---

## Advanced Usage

### Custom Test Subset

Run specific test phases by editing `smoke_test.sh`:

```bash
# Comment out phases you want to skip
# Phase 4: Archiver
# test_archiver_flush_wait || true

# Phase 6: Optional Features
# test_retrieval_endpoint || true
# test_rag_placeholder || true
```

### Performance Benchmarking

Add response time tracking:

```bash
# In smoke_test.sh, modify curl calls:
curl -s -w "\nTime: %{time_total}s\n" ...

# Expected response times:
# /health: <0.2s
# /tool/publish: <0.5s
# /tool/get_status: <0.3s
```

### Load Testing

Test concurrent publishes:

```bash
# Simple concurrency test
for i in {1..10}; do
  ./scripts/smoke_test.sh &
done
wait

# Or use Apache Bench
ab -n 100 -c 10 -H "x-api-key: $MCP_API_KEY" "$MCP_URL/health"
```

### Integration with Monitoring

```bash
# Send test results to monitoring system
./scripts/run_smoke_tests.sh
EXIT_CODE=$?

# Report to Datadog/NewRelic/etc
curl -X POST https://api.datadoghq.com/api/v1/events \
  -H "DD-API-KEY: $DD_API_KEY" \
  -d "{
    \"title\": \"MCP Smoke Tests\",
    \"text\": \"Exit code: $EXIT_CODE\",
    \"alert_type\": \"$([ $EXIT_CODE -eq 0 ] && echo 'success' || echo 'error')\"
  }"
```

---

## Files Reference

### Scripts

- **`scripts/smoke_test.sh`** - Main test suite (15 tests)
- **`scripts/render_status.sh`** - Render CLI helper
- **`scripts/run_smoke_tests.sh`** - Wrapper script with prereq checks

### Configuration

- **`smoke_test.config`** - Configuration template
- **`smoke_test.local.config`** - Your local config (git ignored)

### Documentation

- **`SMOKE_TESTING.md`** - This file

---

## Getting Help

**Documentation:**
- [MCP Server README](../README.md)
- [CLAUDE.md](../../CLAUDE.md) - System architecture
- [Render CLI Docs](https://render.com/docs/cli)

**Debugging:**
```bash
# Enable verbose mode
export VERBOSE=true
./scripts/smoke_test.sh

# Run single test
# Edit smoke_test.sh and comment out other tests
./scripts/smoke_test.sh
```

**Common Questions:**

**Q: Why does archiver test wait 90 seconds?**
A: Default `ARCHIVE_FLUSH_INTERVAL` is 60s. We wait 90s to ensure at least one flush cycle completes.

**Q: Why do S3 tests return 501?**
A: The archiver is currently a stub (logs only, no file writes). Once fully implemented, you'll need to configure `S3_DATA_BUCKET`.

**Q: Can I run tests against local Docker?**
A: Yes! Start services with `docker-compose up` and set `MCP_URL=http://localhost:8080`.

**Q: How do I add custom tests?**
A: Add new test functions to `smoke_test.sh` following the existing pattern. Call them from `main()`.

---

**Last Updated:** 2024-11-24
**Version:** 1.0.0
**Maintainer:** MCP Development Team
