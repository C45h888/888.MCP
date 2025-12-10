# Phase 4 Deployment Checklist

**Phase:** 4 - Security & Access Control
**Version:** 1.0
**Last Updated:** 2024-12-10
**Status:** Ready for Production Deployment

---

## Overview

This checklist ensures Phase 4 (Security & Access Control) is deployed safely with minimal disruption to existing services. Phase 4 introduces multi-key authentication, rate limiting, and enhanced security controls while maintaining backward compatibility with existing deployments.

**Key Features:**
- ✅ Multi-key API authentication (5 roles)
- ✅ Triple-tier rate limiting (IP, key, endpoint)
- ✅ Content-type validation
- ✅ Enhanced error handling
- ✅ Security headers
- ✅ S3 security hardening
- ✅ Backward compatibility with legacy `MCP_API_KEY`

**Estimated Deployment Time:** 30-45 minutes
**Downtime Required:** 2-3 minutes (service restart only)
**Rollback Time:** 5 minutes

---

## Pre-Deployment Checklist

### 1. Code Review & Testing

- [ ] **All Phase 4 code reviewed and approved**
  - [ ] [mcp/auth.py](../mcp/auth.py) - API key management
  - [ ] [mcp/rate_limiter.py](../mcp/rate_limiter.py) - Rate limiting
  - [ ] [mcp/server.py](../mcp/server.py) - Server integration
  - [ ] [docs/SECURITY.md](SECURITY.md) - Security documentation
  - [ ] [docs/ENDPOINT_SECURITY_AUDIT.md](ENDPOINT_SECURITY_AUDIT.md) - Endpoint audit

- [ ] **Unit tests passing locally**
  ```bash
  cd mcp
  pytest tests/ -v --tb=short
  # Expected: All tests pass
  ```

- [ ] **Integration tests passing (if available)**
  ```bash
  docker-compose -f docker-compose.ci.yml up -d
  pytest tests/integration/ -v
  docker-compose -f docker-compose.ci.yml down -v
  ```

- [ ] **Security audit reviewed**
  - [ ] No critical vulnerabilities in dependencies
  - [ ] OWASP Top 10 compliance verified
  - [ ] Endpoint security matrix reviewed

### 2. Environment Preparation

- [ ] **Staging environment available for testing**
  - [ ] Staging deployment successful
  - [ ] Basic functionality verified in staging

- [ ] **Production environment variables documented**
  - [ ] Current `MCP_API_KEY` value saved securely
  - [ ] `REDIS_URL` confirmed
  - [ ] `S3_DATA_BUCKET` confirmed
  - [ ] AWS credentials confirmed

- [ ] **Backup current production state**
  - [ ] Last known good Git commit SHA recorded: `__________`
  - [ ] Current environment variables exported
  - [ ] Redis data snapshot taken (optional, if critical)

### 3. Communication & Coordination

- [ ] **Stakeholders notified**
  - [ ] Operations team informed of deployment window
  - [ ] Feeder agent team notified (n8n workflows)
  - [ ] Brain agent team notified
  - [ ] Monitoring team on standby

- [ ] **Deployment window scheduled**
  - [ ] Date: `__________`
  - [ ] Time: `__________` (low-traffic period recommended)
  - [ ] Duration: 30-45 minutes
  - [ ] Downtime: 2-3 minutes

- [ ] **Rollback plan communicated**
  - [ ] Team aware of rollback procedure
  - [ ] Rollback Git commit identified

### 4. Dependencies Check

- [ ] **Python dependencies reviewed**
  ```bash
  cd mcp
  pip list --outdated
  # Verify no critical security updates needed
  ```

- [ ] **Docker base image up to date**
  ```bash
  # Check Dockerfile base image
  grep "^FROM" mcp/Dockerfile
  # Consider updating to latest stable Python image
  ```

- [ ] **External services healthy**
  - [ ] Redis service: Healthy
  - [ ] S3 bucket: Accessible
  - [ ] Render.com status: Operational

---

## Deployment Steps

### Step 1: Pre-Deployment Verification (5 minutes)

#### 1.1 Current System Health Check

```bash
# Set environment variables
export MCP_URL="https://mcp-server-7h8i.onrender.com"
export MCP_API_KEY="your-current-api-key"

# Health check
curl "$MCP_URL/health"
# Expected: {"status":"ok",...}

# Status check
curl -H "x-api-key: $MCP_API_KEY" "$MCP_URL/tool/get_status" | jq .
# Expected: "redis_connected": true

# Test publish (save response for comparison)
curl -X POST "$MCP_URL/tool/publish" \
  -H "x-api-key: $MCP_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "channel": "market:data",
    "message": {
      "schema_version": "v1",
      "timestamp": '$(date +%s)',
      "pair": "TEST-PRE-DEPLOY",
      "price_btc": 1.0,
      "price_eth": 1.0,
      "volume_btc": 1.0
    }
  }'
# Expected: 200 OK

# Metrics baseline
curl "$MCP_URL/metrics" > pre_deploy_metrics.txt
```

**Verification:**
- [ ] Health endpoint returns 200 OK
- [ ] Status shows Redis connected
- [ ] Publish test successful
- [ ] Metrics captured for baseline

---

### Step 2: Deploy Phase 4 Code (10 minutes)

#### 2.1 Git Commit and Push

```bash
# From repository root
cd /path/to/888.MCP

# Verify all Phase 4 files included
git status
# Should show:
# - mcp/auth.py (new)
# - mcp/rate_limiter.py (new)
# - mcp/server.py (modified)
# - mcp/docker-compose.yml (modified)
# - render.yaml (modified)
# - docs/SECURITY.md (new)
# - docs/ENDPOINT_SECURITY_AUDIT.md (new)
# - docs/RUNBOOK.md (modified)
# - mcp/scripts/harden_s3_security.sh (new)

# Commit Phase 4 changes
git add .
git commit -m "feat: Phase 4 - Security & Access Control

- Multi-key API authentication with 5 roles
- Triple-tier rate limiting (IP, key, endpoint)
- Content-type validation middleware
- Enhanced error handling (environment-aware)
- Security headers middleware
- Admin endpoints for key management
- S3 security hardening script
- Comprehensive security documentation
- Backward compatible with legacy MCP_API_KEY

🤖 Generated with Claude Code
Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"

# Push to main branch (triggers auto-deploy on Render)
git push origin main
```

**Verification:**
- [ ] Git push successful
- [ ] GitHub shows new commit on main branch

#### 2.2 Monitor Render Deployment

```bash
# Watch deployment progress
# Navigate to: https://dashboard.render.com
# Service: mcp-server → Deploys tab
```

**Watch for:**
- [ ] Build starts (should begin within 1 minute)
- [ ] Build completes successfully (3-5 minutes)
- [ ] Deploy starts
- [ ] Service becomes "Live" (green status)

**Deployment logs to check:**
```
Building...
✓ Dependencies installed
✓ Docker image built
✓ Deploying...
✓ Health check passed
✓ Service live
```

**If deployment fails:**
- Check build logs for errors
- Verify Dockerfile syntax
- Check requirements.txt for dependency conflicts
- Proceed to Rollback section if unrecoverable

---

### Step 3: Post-Deployment Verification (10 minutes)

#### 3.1 Basic Health Checks

```bash
# Wait 30 seconds for service to stabilize
sleep 30

# Health check (public endpoint)
curl "$MCP_URL/health"
# Expected: {"status":"ok",...}

# MCP manifest
curl "$MCP_URL/.well-known/mcp" | jq .
# Expected: Valid MCP manifest with protocolVersion
```

**Verification:**
- [ ] Health endpoint returns 200 OK
- [ ] MCP manifest accessible

#### 3.2 Backward Compatibility Test (Legacy Key)

```bash
# Test with LEGACY MCP_API_KEY (should still work)
curl -H "x-api-key: $MCP_API_KEY" "$MCP_URL/tool/get_status" | jq .
# Expected: Status response with redis_connected: true

# Test legacy key publish
curl -X POST "$MCP_URL/tool/publish" \
  -H "x-api-key: $MCP_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "channel": "market:data",
    "message": {
      "schema_version": "v1",
      "timestamp": '$(date +%s)',
      "pair": "TEST-LEGACY-KEY",
      "price_btc": 1.0,
      "price_eth": 1.0,
      "volume_btc": 1.0
    }
  }'
# Expected: 200 OK (legacy key still works!)
```

**Verification:**
- [ ] Legacy key can access authenticated endpoints
- [ ] Legacy key can publish messages
- [ ] No 401 Unauthorized errors

#### 3.3 Rate Limiting Verification

```bash
# Check rate limit headers in response
curl -i -H "x-api-key: $MCP_API_KEY" "$MCP_URL/tool/get_status"
# Look for headers:
# X-RateLimit-Limit: 200
# X-RateLimit-Remaining: 199
# X-RateLimit-Reset: <timestamp>

# Check rate limiting metrics
curl "$MCP_URL/metrics" | grep "mcp_rate_limit"
# Should show rate limit counters (even if 0)
```

**Verification:**
- [ ] Rate limit headers present in responses
- [ ] Rate limit metrics exposed in /metrics

#### 3.4 Security Headers Verification

```bash
# Check security headers
curl -i "$MCP_URL/health" | grep -E "(X-Content-Type-Options|X-Frame-Options|X-XSS-Protection|Strict-Transport-Security)"
# Expected:
# X-Content-Type-Options: nosniff
# X-Frame-Options: DENY
# X-XSS-Protection: 1; mode=block
# Strict-Transport-Security: max-age=31536000; includeSubDomains
```

**Verification:**
- [ ] All security headers present
- [ ] Server header removed (should not appear)

#### 3.5 Content-Type Validation Test

```bash
# Test with invalid Content-Type (should fail)
curl -i -X POST "$MCP_URL/tool/publish" \
  -H "x-api-key: $MCP_API_KEY" \
  -H "Content-Type: text/plain" \
  -d '{"channel":"market:data",...}'
# Expected: 415 Unsupported Media Type

# Test with valid Content-Type (should succeed)
curl -X POST "$MCP_URL/tool/publish" \
  -H "x-api-key: $MCP_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "channel": "market:data",
    "message": {
      "schema_version": "v1",
      "timestamp": '$(date +%s)',
      "pair": "TEST-CONTENT-TYPE",
      "price_btc": 1.0,
      "price_eth": 1.0,
      "volume_btc": 1.0
    }
  }'
# Expected: 200 OK
```

**Verification:**
- [ ] Invalid Content-Type rejected with 415
- [ ] Valid Content-Type accepted

---

### Step 4: New Multi-Key System Verification (10 minutes)

#### 4.1 Create Admin API Key

```bash
# Export legacy key as admin key
export ADMIN_KEY="$MCP_API_KEY"

# Create a new admin key (for testing)
curl -X POST "$MCP_URL/admin/keys/create" \
  -H "X-API-Key: $ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "role": "admin",
    "description": "Post-deployment test admin key"
  }' | jq .

# SAVE THE RESPONSE! api_key is shown only once
# Store in: NEW_ADMIN_KEY environment variable
export NEW_ADMIN_KEY="<api_key_from_response>"
```

**Verification:**
- [ ] Key creation successful (200 OK)
- [ ] Response includes `api_key` (plaintext, shown only once)
- [ ] Response includes `key_hash`, `role`, `created_at`
- [ ] New key saved securely

#### 4.2 List API Keys

```bash
# List all keys (should show both legacy and new key)
curl -H "X-API-Key: $ADMIN_KEY" "$MCP_URL/admin/keys/list" | jq .
# Expected: Array with 2 keys (legacy + new admin key)
```

**Verification:**
- [ ] Both keys listed
- [ ] Legacy key has role "admin"
- [ ] New key has role "admin"
- [ ] Both keys show `last_used` timestamp

#### 4.3 Test New Admin Key

```bash
# Test new admin key can access status
curl -H "X-API-Key: $NEW_ADMIN_KEY" "$MCP_URL/tool/get_status" | jq .
# Expected: Status response

# Test new admin key can publish
curl -X POST "$MCP_URL/tool/publish" \
  -H "X-API-Key: $NEW_ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "channel": "market:data",
    "message": {
      "schema_version": "v1",
      "timestamp": '$(date +%s)',
      "pair": "TEST-NEW-ADMIN-KEY",
      "price_btc": 1.0,
      "price_eth": 1.0,
      "volume_btc": 1.0
    }
  }'
# Expected: 200 OK
```

**Verification:**
- [ ] New admin key can access authenticated endpoints
- [ ] New admin key can publish messages
- [ ] New admin key can access admin endpoints

#### 4.4 Create Role-Specific Keys

```bash
# Create feeder key
curl -X POST "$MCP_URL/admin/keys/create" \
  -H "X-API-Key: $ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "role": "feeder",
    "description": "Test feeder key"
  }' | jq .
export FEEDER_KEY="<api_key_from_response>"

# Create brain key
curl -X POST "$MCP_URL/admin/keys/create" \
  -H "X-API-Key: $ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "role": "brain",
    "description": "Test brain key"
  }' | jq .
export BRAIN_KEY="<api_key_from_response>"

# Create readonly key
curl -X POST "$MCP_URL/admin/keys/create" \
  -H "X-API-Key: $ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "role": "readonly",
    "description": "Test readonly key"
  }' | jq .
export READONLY_KEY="<api_key_from_response>"
```

**Verification:**
- [ ] All keys created successfully
- [ ] Each key has correct role

#### 4.5 Test Permission Enforcement

**Test feeder key (should publish market:data, but NOT admin endpoints):**

```bash
# Should succeed: feeder can publish market:data
curl -X POST "$MCP_URL/tool/publish" \
  -H "X-API-Key: $FEEDER_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "channel": "market:data",
    "message": {
      "schema_version": "v1",
      "timestamp": '$(date +%s)',
      "pair": "TEST-FEEDER",
      "price_btc": 1.0,
      "price_eth": 1.0,
      "volume_btc": 1.0
    }
  }'
# Expected: 200 OK

# Should fail: feeder cannot access admin endpoints
curl -X POST "$MCP_URL/admin/keys/create" \
  -H "X-API-Key: $FEEDER_KEY" \
  -H "Content-Type: application/json" \
  -d '{"role": "ops", "description": "Should fail"}'
# Expected: 403 Forbidden
```

**Test brain key (should publish agent:signal, but NOT market:data):**

```bash
# Should succeed: brain can publish agent:signal
curl -X POST "$MCP_URL/tool/publish" \
  -H "X-API-Key: $BRAIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "channel": "agent:signal",
    "message": {
      "schema_version": "v1",
      "timestamp": '$(date +%s)',
      "pair": "TEST-BRAIN",
      "action": "SHORT_SPREAD",
      "confidence": 0.75,
      "stop_loss_z": 2.5,
      "reason": "Test signal"
    }
  }'
# Expected: 200 OK

# Should fail: brain cannot publish to market:data
curl -X POST "$MCP_URL/tool/publish" \
  -H "X-API-Key: $BRAIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "channel": "market:data",
    "message": {...}
  }'
# Expected: 403 Forbidden
```

**Test readonly key (should retrieve, but NOT publish):**

```bash
# Should succeed: readonly can get status
curl -H "X-API-Key: $READONLY_KEY" "$MCP_URL/tool/get_status" | jq .
# Expected: Status response

# Should fail: readonly cannot publish
curl -X POST "$MCP_URL/tool/publish" \
  -H "X-API-Key: $READONLY_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "channel": "market:data",
    "message": {...}
  }'
# Expected: 403 Forbidden
```

**Verification:**
- [ ] Feeder key can publish market:data ✅
- [ ] Feeder key cannot access admin endpoints ❌ (expected)
- [ ] Brain key can publish agent:signal ✅
- [ ] Brain key cannot publish market:data ❌ (expected)
- [ ] Readonly key can get status ✅
- [ ] Readonly key cannot publish ❌ (expected)

---

### Step 5: S3 Security Hardening (5 minutes)

#### 5.1 Run S3 Hardening Script

```bash
# From local machine (requires AWS CLI)
cd mcp/scripts

# Set environment variables
export S3_DATA_BUCKET=mcp-data-prod-kamesh.888
export AWS_REGION=eu-north-1
export AWS_ACCESS_KEY_ID=<your_aws_access_key>
export AWS_SECRET_ACCESS_KEY=<your_aws_secret_key>

# Optional: Enable access logging
# export ENABLE_ACCESS_LOGGING=true
# export S3_LOGS_BUCKET=mcp-logs-prod-kamesh.888

# Make script executable
chmod +x harden_s3_security.sh

# Run script
./harden_s3_security.sh
```

**Expected Output:**
```
=========================================
  MCP Server S3 Security Hardening
=========================================

[✓] Bucket Versioning applied successfully
[✓] Server-Side Encryption applied successfully
[✓] Public Access Block applied successfully
[✓] Default encryption verified
[✓] Access logging skipped (not enabled)

✅ Your S3 bucket is now hardened
Security Status: EXCELLENT
```

**Verification:**
- [ ] Script completes successfully
- [ ] All 5 security measures applied (or 4 if logging skipped)
- [ ] No errors in output

#### 5.2 Verify S3 Security

```bash
# Check versioning
aws s3api get-bucket-versioning \
  --bucket $S3_DATA_BUCKET \
  --region $AWS_REGION | jq .
# Expected: "Status": "Enabled"

# Check encryption
aws s3api get-bucket-encryption \
  --bucket $S3_DATA_BUCKET \
  --region $AWS_REGION | jq .
# Expected: "SSEAlgorithm": "AES256"

# Check public access block
aws s3api get-public-access-block \
  --bucket $S3_DATA_BUCKET \
  --region $AWS_REGION | jq .
# Expected: All values true
```

**Verification:**
- [ ] Versioning enabled
- [ ] Encryption enabled (AES256)
- [ ] Public access blocked
- [ ] Bucket secure

---

### Step 6: Production Readiness Verification (5 minutes)

#### 6.1 Metrics Verification

```bash
# Capture post-deployment metrics
curl "$MCP_URL/metrics" > post_deploy_metrics.txt

# Check Phase 4 specific metrics
curl "$MCP_URL/metrics" | grep -E "(mcp_rate_limit|mcp_auth)"
# Should show rate limit counters and authentication metrics
```

**Verification:**
- [ ] All Phase 3 metrics still present
- [ ] New Phase 4 metrics present (rate limit, auth)

#### 6.2 Logs Verification

```bash
# Check recent logs (Render Dashboard)
# Navigate to: Dashboard → mcp-server → Logs

# Look for:
# - "Legacy MCP_API_KEY registered" (startup message)
# - No authentication errors
# - No rate limit errors (unless testing)
# - No unhandled exceptions
```

**Verification:**
- [ ] No ERROR level logs (except expected test failures)
- [ ] Legacy key registered message present
- [ ] Server startup clean

#### 6.3 End-to-End Test

```bash
# Full workflow test with legacy key
TEST_TIMESTAMP=$(date +%s)

# 1. Publish market:data
curl -X POST "$MCP_URL/tool/publish" \
  -H "x-api-key: $MCP_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "channel": "market:data",
    "message": {
      "schema_version": "v1",
      "timestamp": '$TEST_TIMESTAMP',
      "pair": "BTC-ETH",
      "price_btc": 30000.0,
      "price_eth": 2000.0,
      "volume_btc": 150.5
    }
  }'

# 2. Publish sentiment:data
curl -X POST "$MCP_URL/tool/publish" \
  -H "x-api-key: $MCP_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "channel": "sentiment:data",
    "message": {
      "schema_version": "v1",
      "timestamp": '$TEST_TIMESTAMP',
      "source": "Test",
      "score": 0.75,
      "summary": "Post-deployment test"
    }
  }'

# 3. Check status
curl -H "x-api-key: $MCP_API_KEY" "$MCP_URL/tool/get_status" | jq .

# 4. Check metrics
curl "$MCP_URL/metrics" | grep "mcp_publish_total"
```

**Verification:**
- [ ] All publishes successful
- [ ] Status endpoint responsive
- [ ] Metrics incrementing
- [ ] No errors in logs

---

## Post-Deployment Tasks

### Immediate (Within 1 hour)

- [ ] **Monitor for errors**
  - Watch logs for 30 minutes for unexpected errors
  - Check error rate in metrics
  - Verify no authentication failures from legitimate clients

- [ ] **Notify stakeholders of successful deployment**
  - Operations team
  - Feeder agent team
  - Brain agent team
  - Document deployment completion in team channel

- [ ] **Update documentation**
  - Mark Phase 4 as "Deployed" in project tracker
  - Update deployment history

### Short-term (Within 24 hours)

- [ ] **Create production API keys for agents**
  - Create dedicated feeder key for n8n workflows
  - Create dedicated brain key for Brain agent
  - Distribute keys securely (password manager, secure vault)

- [ ] **Rotate legacy MCP_API_KEY**
  ```bash
  # After verifying all agents have new keys:
  curl -X POST "$MCP_URL/admin/keys/rotate" \
    -H "X-API-Key: $ADMIN_KEY" \
    -H "Content-Type: application/json" \
    -d '{
      "old_key_hash": "<legacy_key_hash>",
      "description": "Rotated legacy key after Phase 4 deployment"
    }'
  ```

- [ ] **Set up monitoring alerts** (see [docs/RUNBOOK.md](RUNBOOK.md#monitoring--alerts))
  - Rate limit rejection alerts
  - Authentication failure alerts
  - Endpoint latency alerts

- [ ] **Performance baseline**
  - Capture 24-hour metrics baseline
  - Document normal rate limit usage
  - Document normal authentication patterns

### Medium-term (Within 1 week)

- [ ] **Security audit**
  - Review all API keys in `/admin/keys/list`
  - Verify least-privilege principle
  - Remove test keys created during verification

- [ ] **Load testing** (optional but recommended)
  - Test rate limiting under load
  - Verify rate limits are appropriate
  - Adjust limits if needed

- [ ] **Documentation review**
  - Ensure all team members familiar with new security procedures
  - Update team runbooks if needed
  - Schedule security training if needed

---

## Rollback Procedure

**When to Rollback:**
- Authentication completely broken (no keys work)
- Service unhealthy after deployment
- Critical functionality broken
- Rate limiting blocking all traffic

**Rollback Steps:**

### 1. Identify Last Known Good Deployment

```bash
# Render Dashboard → mcp-server → Deploys
# Find last deployment with "Live" badge before Phase 4
# Note the commit SHA: __________
```

### 2. Initiate Rollback

```bash
# Render Dashboard → mcp-server → Deploys
# Click "Redeploy" on last known good deployment
# Confirm rollback
```

**OR via Git:**

```bash
# From repository
git revert <phase4_commit_sha>
git push origin main
# Render will auto-deploy the revert
```

### 3. Verify Rollback

```bash
# Wait 2-3 minutes for deployment

# Health check
curl "$MCP_URL/health"
# Expected: 200 OK

# Test with legacy key
curl -H "x-api-key: $MCP_API_KEY" "$MCP_URL/tool/get_status"
# Expected: Status response

# Test publish
curl -X POST "$MCP_URL/tool/publish" \
  -H "x-api-key: $MCP_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "channel": "market:data",
    "message": {
      "schema_version": "v1",
      "timestamp": '$(date +%s)',
      "pair": "TEST-ROLLBACK",
      "price_btc": 1.0,
      "price_eth": 1.0,
      "volume_btc": 1.0
    }
  }'
# Expected: 200 OK
```

**Verification:**
- [ ] Health endpoint returns 200 OK
- [ ] Legacy key works
- [ ] Publish functionality restored
- [ ] Service stable

### 4. Post-Rollback Actions

- [ ] Notify stakeholders of rollback
- [ ] Investigate root cause of failure
- [ ] Fix issues in Phase 4 code
- [ ] Test fixes in staging
- [ ] Re-schedule deployment when ready

**Rollback Impact:**
- ❌ Multi-key authentication unavailable (back to single key)
- ❌ Rate limiting disabled (back to no rate limiting)
- ❌ Enhanced security features disabled
- ✅ Core functionality preserved (publish, retrieve, kill-switch)
- ✅ No data loss (Redis + S3 unaffected)

---

## Known Issues & Mitigations

### Issue 1: Legacy Key Not Auto-Registered

**Symptom:** After deployment, legacy `MCP_API_KEY` returns 401 Unauthorized

**Root Cause:** Legacy key registration failed during startup

**Mitigation:**
```bash
# Check logs for "Legacy MCP_API_KEY registered" message
# If missing, create new admin key immediately:
curl -X POST "$MCP_URL/admin/keys/create" \
  -H "X-API-Key: $MCP_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"role": "admin", "description": "Emergency admin key"}'
# Use new key for all operations
```

### Issue 2: Rate Limiting Too Restrictive

**Symptom:** Legitimate traffic receiving 429 Too Many Requests

**Mitigation:**
```bash
# Temporarily increase rate limits
# Render Dashboard → Environment
RATE_LIMIT_GLOBAL_IP=200/minute  # Double from 100
RATE_LIMIT_PUBLISH=120/minute    # Double from 60
# Save changes (triggers restart)
```

### Issue 3: Content-Type Validation Blocking Clients

**Symptom:** Clients receiving 415 Unsupported Media Type

**Root Cause:** Client not sending `Content-Type: application/json` header

**Mitigation:**
```bash
# Fix client code to include header:
# curl -H "Content-Type: application/json" ...

# Temporary workaround: No code change needed
# Validation is correct, clients must send proper Content-Type
```

### Issue 4: Redis Key Storage Full

**Symptom:** Cannot create new API keys, Redis out of memory

**Mitigation:**
```bash
# Check Redis memory usage
# Render Dashboard → mcp-redis → Metrics

# If full, upgrade Redis plan or clean old keys:
curl -H "X-API-Key: $ADMIN_KEY" "$MCP_URL/admin/keys/list" | jq .
# Revoke unused keys with old last_used timestamps
```

---

## Success Criteria

Phase 4 deployment is considered successful when ALL of the following are true:

### Critical Success Criteria (Must Pass)

- [✅] Service health check returns 200 OK
- [✅] Legacy `MCP_API_KEY` still works (backward compatibility)
- [✅] New multi-key system functional (can create/list/revoke keys)
- [✅] Rate limiting active (headers present in responses)
- [✅] Security headers present (X-Content-Type-Options, etc.)
- [✅] No authentication errors in logs (except expected test failures)
- [✅] Publish functionality works with both legacy and new keys
- [✅] All existing metrics still available

### Secondary Success Criteria (Should Pass)

- [✅] Permission enforcement working (403 for insufficient permissions)
- [✅] Content-type validation working (415 for invalid content-type)
- [✅] S3 bucket hardened (versioning, encryption, public access blocked)
- [✅] Admin endpoints accessible (create/list/revoke/rotate keys)
- [✅] Rate limit metrics exposed in /metrics
- [✅] Error handling environment-aware (generic in prod, detailed in dev)

### Performance Criteria

- [✅] P95 latency < 500ms (no significant increase from Phase 3)
- [✅] Request success rate > 99% (excluding rate limited requests)
- [✅] No memory leaks (stable memory usage over 24 hours)

---

## Appendix A: Environment Variables Reference

### Phase 4 Environment Variables (Production)

```bash
# Authentication (Existing)
MCP_API_KEY=<legacy_key>              # Auto-registered as admin role

# Rate Limiting (New in Phase 4)
RATE_LIMIT_GLOBAL_IP=100/minute       # Per-IP limit across all endpoints
RATE_LIMIT_GLOBAL_KEY=200/minute      # Per-API-key limit across all endpoints
RATE_LIMIT_PUBLISH=60/minute          # Publish endpoint specific
RATE_LIMIT_RETRIEVE=30/minute         # Retrieve endpoint specific
RATE_LIMIT_STATUS=120/minute          # Status endpoint specific
RATE_LIMIT_METRICS=120/minute         # Metrics endpoint specific
RATE_LIMIT_ADMIN=30/minute            # Admin endpoints specific
RATE_LIMIT_HEALTH=300/minute          # Health endpoint specific

# Security (Optional)
CORS_ENABLED=false                    # Disable CORS (default)
CORS_ORIGINS=                         # No origins allowed (default)
METRICS_AUTH_REQUIRED=false           # Metrics public (default)

# Logging
LOG_LEVEL=INFO                        # INFO in production, DEBUG in dev
MCP_DEV=false                         # Production mode (generic errors)
```

---

## Appendix B: Quick Reference Commands

### Health & Status

```bash
curl $MCP_URL/health
curl -H "X-API-Key: $KEY" $MCP_URL/tool/get_status
curl $MCP_URL/metrics
```

### API Key Management

```bash
# List keys
curl -H "X-API-Key: $ADMIN_KEY" $MCP_URL/admin/keys/list

# Create key
curl -X POST $MCP_URL/admin/keys/create \
  -H "X-API-Key: $ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{"role":"feeder","description":"..."}'

# Rotate key
curl -X POST $MCP_URL/admin/keys/rotate \
  -H "X-API-Key: $ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{"old_key_hash":"...","description":"..."}'

# Revoke key
curl -X POST $MCP_URL/admin/keys/revoke \
  -H "X-API-Key: $ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{"key_hash":"...","reason":"..."}'
```

### Rate Limiting

```bash
# Check rejections
curl $MCP_URL/metrics | grep "mcp_rate_limit_rejections_total"

# Check rate limit headers
curl -i -H "X-API-Key: $KEY" $MCP_URL/tool/get_status | grep "X-RateLimit"
```

---

**Document Status:** ✅ Complete
**Approved By:** Pending deployment execution
**Next Review:** After successful production deployment
