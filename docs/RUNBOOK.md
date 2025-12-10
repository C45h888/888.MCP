# MCP Server Operational Runbook

**Version:** 1.0
**Last Updated:** 2025-12-08
**Audience:** Operations, DevOps, SRE, On-Call Engineers

---

## Table of Contents

1. [Quick Reference](#quick-reference)
2. [Service Architecture](#service-architecture)
3. [Health Checks](#health-checks)
4. [Common Operations](#common-operations)
5. [Troubleshooting](#troubleshooting)
6. [Incident Response](#incident-response)
7. [Monitoring & Alerts](#monitoring--alerts)
8. [Deployment Procedures](#deployment-procedures)
9. [Emergency Procedures](#emergency-procedures)
10. [Contact Information](#contact-information)

---

## Quick Reference

### Essential URLs

| Service | URL | Auth Required |
|---------|-----|---------------|
| **Production Server** | https://mcp-server-7h8i.onrender.com | No (health only) |
| **Health Check** | /health | No |
| **Metrics** | /metrics | No |
| **Status (Detailed)** | /tool/get_status | Yes (x-api-key) |
| **Render Dashboard** | https://dashboard.render.com | Yes (Render login) |

### Quick Health Check

```bash
# Simple health check
curl https://mcp-server-7h8i.onrender.com/health

# Expected: {"status":"ok","time":"2025-12-08T...Z","archiver_enabled":"true"}
```

### Quick Status Check

```bash
export MCP_URL="https://mcp-server-7h8i.onrender.com"
export MCP_API_KEY="your-api-key-here"

curl -H "x-api-key: $MCP_API_KEY" "$MCP_URL/tool/get_status" | jq .
```

### Environment Variables Reference

| Variable | Purpose | Production Value |
|----------|---------|------------------|
| `MCP_API_KEY` | API authentication | *Secret* (from Render) |
| `REDIS_URL` | Redis connection | Auto (from Render Redis) |
| `S3_DATA_BUCKET` | S3 archiving | `mcp-data-prod-kamesh.888` |
| `AWS_REGION` | AWS region | `eu-north-1` |
| `ARCHIVE_BATCH_SIZE` | Messages per batch | `200` |
| `ARCHIVE_FLUSH_INTERVAL` | Flush frequency (seconds) | `60` |
| `LOG_LEVEL` | Logging verbosity | `INFO` |

---

## Service Architecture

### Components

```
┌─────────────────┐
│   Feeder Agent  │ (n8n - external)
│   (Agent 1)     │
└────────┬────────┘
         │ publishes
         ▼
┌─────────────────┐
│   MCP Server    │ (FastAPI + Redis)
│   (This Service)│
│                 │
│  ┌───────────┐  │
│  │  Redis    │  │ ← Pub/Sub message bus
│  │  Client   │  │
│  └───────────┘  │
│                 │
│  ┌───────────┐  │
│  │  Archiver │  │ ← Background S3 uploader
│  └───────────┘  │
└────────┬────────┘
         │ stores
         ▼
┌─────────────────┐
│   S3 Storage    │ (Historical data)
└─────────────────┘
```

### Channels

| Channel | Purpose | Publisher | Subscriber |
|---------|---------|-----------|------------|
| `market:data` | Price/volume data | Feeder | Brain |
| `sentiment:data` | News/social sentiment | Feeder | Brain |
| `agent:control` | Kill-switch commands | External | Brain |
| `agent:signal` | Trade signals | Brain | Execution |

### Technology Stack

- **Web Framework:** FastAPI 0.104.1
- **Message Bus:** Redis 5.0.1
- **Archiving:** boto3 (S3), JSONL.gz format
- **Metrics:** Prometheus (prometheus-client)
- **Logging:** python-json-logger (structured JSON)
- **Deployment:** Render.com (Docker containers)

---

## Health Checks

### Level 1: Basic Health (Public)

```bash
curl https://mcp-server-7h8i.onrender.com/health
```

**Expected Response:**
```json
{
  "status": "ok",
  "time": "2025-12-08T12:34:56.789Z",
  "archiver_enabled": "true"
}
```

**Status Codes:**
- `200`: Service is healthy
- `500`: Service is unhealthy
- `000` or timeout: Service is down or unreachable

### Level 2: Detailed Status (Authenticated)

```bash
curl -H "x-api-key: $MCP_API_KEY" \
     "$MCP_URL/tool/get_status" | jq .
```

**Expected Response:**
```json
{
  "status": "healthy",
  "redis_connected": true,
  "kill_switch": {
    "active": false,
    "last_event": null
  },
  "channels": {
    "market:data": 0,
    "sentiment:data": 0,
    "agent:control": 0,
    "agent:signal": 0
  },
  "timestamp": 1678886400
}
```

**Status Values:**
- `healthy`: All systems operational
- `degraded`: Redis disconnected or partial functionality
- `EMERGENCY_HALT`: Kill-switch activated

### Level 3: Metrics (Public)

```bash
curl https://mcp-server-7h8i.onrender.com/metrics
```

**Key Metrics to Check:**
- `mcp_redis_connected`: Should be `1.0`
- `mcp_kill_switch_active`: Should be `0.0` (normal operation)
- `mcp_publish_total`: Incrementing with traffic
- `mcp_archive_queue_size`: Should be low (< 50)

---

## Common Operations

### Restart Service

#### On Render.com

1. Go to [Render Dashboard](https://dashboard.render.com)
2. Navigate to **mcp-server** service
3. Click **Manual Deploy** → **Deploy Latest Commit**
4. Monitor logs for startup confirmation
5. Run smoke tests after restart

#### Using Render CLI

```bash
render services restart mcp-server
```

#### Expected Restart Time
- **Cold start:** 30-60 seconds
- **Warm restart:** 15-30 seconds

### View Logs

#### Real-time Logs (Render Dashboard)

1. Dashboard → mcp-server → Logs tab
2. Use filter to search: `level:ERROR` or `channel:market:data`

#### Real-time Logs (CLI)

```bash
# If you have Render CLI installed
render logs --tail mcp-server

# Filter for errors
render logs --tail mcp-server | grep '"level":"ERROR"'
```

#### Log Format (JSON)

```json
{
  "@timestamp": 1678886400.123,
  "level": "INFO",
  "logger": "mcp.server",
  "message": "Message published successfully",
  "request_id": "a1b2c3d4-e5f6-7890-1234-567890abcdef",
  "channel": "market:data"
}
```

### Scale Service

#### Increase Resources (Render Dashboard)

1. Dashboard → mcp-server → Settings
2. Change **Instance Type** (e.g., Standard → Pro)
3. Click **Save Changes**
4. Service will automatically restart

#### Horizontal Scaling

Currently **not configured**. To enable:
1. Add horizontal scaling in Render settings
2. Update Redis to handle multiple connections
3. Test with load balancer

### Check S3 Archiving

#### Verify Recent Uploads

```bash
aws s3 ls s3://mcp-data-prod-kamesh.888/mcp/market_data/ --recursive | \
  grep "$(date +%Y-%m-%d)" | tail -20
```

#### Count Today's Files

```bash
aws s3 ls s3://mcp-data-prod-kamesh.888/mcp/market_data/ --recursive | \
  grep "$(date +%Y-%m-%d)" | wc -l
```

#### Check File Sizes

```bash
aws s3 ls s3://mcp-data-prod-kamesh.888/mcp/market_data/ --recursive | \
  grep "$(date +%Y-%m-%d)" | \
  awk '{sum+=$3; count++} END {print "Files:", count, "Avg size:", sum/count/1024 "KB"}'
```

---

## Troubleshooting

### Issue 1: Service Not Responding

**Symptoms:**
- `/health` endpoint returns 500 or times out
- No response from server
- Render dashboard shows "Unhealthy"

**Diagnosis:**

1. Check Render service status:
   ```bash
   # Dashboard → mcp-server → Events
   # Look for recent crashes or deploy failures
   ```

2. Check recent logs:
   ```bash
   # Dashboard → mcp-server → Logs
   # Filter by: level:ERROR
   ```

3. Check Redis connection:
   ```bash
   curl -H "x-api-key: $MCP_API_KEY" "$MCP_URL/tool/get_status" | \
     jq '.redis_connected'
   # Should return: true
   ```

**Resolution:**

**Step 1:** Restart the service
```bash
# Render Dashboard → Manual Deploy → Deploy Latest Commit
```

**Step 2:** If restart fails, check environment variables
```bash
# Dashboard → mcp-server → Environment
# Verify: REDIS_URL, MCP_API_KEY, S3_DATA_BUCKET
```

**Step 3:** Check Redis service
```bash
# Dashboard → mcp-redis
# Ensure status is "Available"
# If down, restart Redis service
```

**Step 4:** If still failing, check recent deployments
```bash
# Dashboard → mcp-server → Deploys
# Roll back to last known good deployment if needed
```

**Prevention:**
- Set up health check alerts in Render
- Monitor metrics for early warning signs
- Always test deploys in staging first

---

### Issue 2: Redis Connection Lost

**Symptoms:**
- `redis_connected: false` in status
- Publish requests fail with 500 errors
- Logs show: "Redis connection error"

**Diagnosis:**

1. Check Redis service status:
   ```bash
   # Dashboard → mcp-redis → Status
   ```

2. Check Redis connection string:
   ```bash
   # Dashboard → mcp-server → Environment
   # Verify REDIS_URL is correct
   ```

3. Check network connectivity:
   ```bash
   # From mcp-server logs:
   # Look for "Connected to Redis" or connection errors
   ```

**Resolution:**

**Step 1:** Restart Redis service
```bash
# Dashboard → mcp-redis → Restart
```

**Step 2:** Restart MCP server
```bash
# Dashboard → mcp-server → Manual Deploy
```

**Step 3:** Verify connection
```bash
curl -H "x-api-key: $MCP_API_KEY" "$MCP_URL/tool/get_status" | \
  jq '.redis_connected'
# Should return: true
```

**Step 4:** If persistent, check Redis logs
```bash
# Dashboard → mcp-redis → Logs
# Look for memory issues, eviction policy problems
```

**Prevention:**
- Monitor `mcp_redis_connected` metric
- Set up alerts for Redis downtime
- Ensure Redis plan has sufficient memory

---

### Issue 3: S3 Upload Failures

**Symptoms:**
- `mcp_archive_queue_size` metric growing
- Logs show "S3 upload failed" errors
- No recent files in S3 bucket

**Diagnosis:**

1. Check archiver queue depth:
   ```bash
   curl "$MCP_URL/metrics" | grep "mcp_archive_queue_size"
   # Should be < 50 normally
   ```

2. Check recent S3 uploads:
   ```bash
   aws s3 ls s3://mcp-data-prod-kamesh.888/mcp/market_data/ --recursive | \
     grep "$(date +%Y-%m-%d)" | tail -5
   # Should show files from last few minutes
   ```

3. Check AWS credentials:
   ```bash
   # Dashboard → mcp-server → Environment
   # Verify: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, S3_DATA_BUCKET
   ```

**Resolution:**

**Step 1:** Verify S3 bucket exists and is accessible
```bash
aws s3 ls s3://mcp-data-prod-kamesh.888/
# Should list bucket contents
```

**Step 2:** Check IAM permissions
```bash
# Ensure IAM user has these permissions:
# - s3:PutObject
# - s3:GetObject
# - s3:ListBucket
```

**Step 3:** Restart MCP server to flush queue
```bash
# Dashboard → mcp-server → Manual Deploy
# Queue will flush on shutdown
```

**Step 4:** If still failing, check AWS credentials rotation
```bash
# AWS Console → IAM → Users → mcp-server-user
# Verify access keys are active
# Regenerate if needed, update in Render
```

**Prevention:**
- Monitor `mcp_archive_upload_failures_total` metric
- Set up alerts for queue depth > 100
- Regularly verify S3 access

---

### Issue 4: High Latency

**Symptoms:**
- `mcp_publish_latency_seconds` P95 > 1s
- Slow response times for publish requests
- Users reporting delays

**Diagnosis:**

1. Check current latency:
   ```bash
   curl "$MCP_URL/metrics" | grep "mcp_publish_latency_seconds"
   # Look at _bucket and _sum values
   ```

2. Check Redis performance:
   ```bash
   curl -H "x-api-key: $MCP_API_KEY" "$MCP_URL/tool/get_status"
   # Fast response = healthy, slow response = issue
   ```

3. Check server CPU/memory:
   ```bash
   # Dashboard → mcp-server → Metrics
   # Look for CPU or memory spikes
   ```

**Resolution:**

**Step 1:** Check Redis connection
```bash
# If Redis is slow, restart it
# Dashboard → mcp-redis → Restart
```

**Step 2:** Check server resources
```bash
# Dashboard → mcp-server → Metrics
# If CPU > 80% or Memory > 90%, upgrade plan
```

**Step 3:** Check for large message payloads
```bash
# Review logs for unusually large messages
# Consider implementing payload size limits
```

**Step 4:** Upgrade server plan if needed
```bash
# Dashboard → mcp-server → Settings → Instance Type
# Upgrade from Standard to Pro for more resources
```

**Prevention:**
- Monitor `mcp_publish_latency_seconds` P95 < 500ms
- Set up alerts for latency > 1s
- Regularly review resource usage

---

### Issue 5: Kill-Switch Stuck Active

**Symptoms:**
- `mcp_kill_switch_active` metric = 1.0
- Status shows `EMERGENCY_HALT`
- Unable to publish messages

**Diagnosis:**

1. Check kill-switch status:
   ```bash
   curl -H "x-api-key: $MCP_API_KEY" "$MCP_URL/tool/get_status" | \
     jq '.kill_switch'
   ```

2. Check kill-switch history:
   ```bash
   curl -H "x-api-key: $MCP_API_KEY" "$MCP_URL/tool/kill_history" | \
     jq '.events | .[0:5]'
   # Review recent HALT/RESUME commands
   ```

**Resolution:**

**Step 1:** Send RESUME command
```bash
curl -X POST "$MCP_URL/tool/publish" \
  -H "x-api-key: $MCP_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "channel": "agent:control",
    "message": {
      "schema_version": "v1",
      "timestamp": '$(date +%s)',
      "command": "RESUME",
      "reason": "Manual resume by operations"
    }
  }'
```

**Step 2:** Verify kill-switch cleared
```bash
curl "$MCP_URL/metrics" | grep "mcp_kill_switch_active"
# Should show: 0.0
```

**Step 3:** Test publishing
```bash
curl -X POST "$MCP_URL/tool/publish" \
  -H "x-api-key: $MCP_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "channel": "market:data",
    "message": {
      "schema_version": "v1",
      "timestamp": '$(date +%s)',
      "pair": "TEST-TEST",
      "price_btc": 1.0,
      "price_eth": 1.0,
      "volume_btc": 1.0
    }
  }'
# Should return success
```

**Prevention:**
- Document who can trigger EMERGENCY_HALT
- Set up alerts for kill-switch activation
- Require approval for HALT commands

---

## Incident Response

### Severity Levels

| Severity | Description | Response Time | Escalation |
|----------|-------------|---------------|------------|
| **SEV-1** | Service down, all traffic affected | Immediate | Escalate to on-call lead after 15min |
| **SEV-2** | Partial outage, degraded performance | Within 30min | Escalate if not resolved in 1hr |
| **SEV-3** | Minor issue, no user impact | Within 2hrs | Escalate if persists > 4hrs |

### SEV-1 Incident Response Checklist

**Immediate Actions (First 5 minutes):**

- [ ] Acknowledge incident in team channel
- [ ] Check service health: `curl $MCP_URL/health`
- [ ] Check Render dashboard for service status
- [ ] Check recent deployments (possible bad deploy?)
- [ ] Check #incidents channel for similar issues

**Diagnosis (5-15 minutes):**

- [ ] Check Redis service status (Dashboard → mcp-redis)
- [ ] Check recent logs for errors (`level:ERROR`)
- [ ] Check metrics for anomalies (latency, queue depth)
- [ ] Identify root cause or symptoms

**Resolution (15-30 minutes):**

- [ ] If bad deployment: Roll back to last known good
- [ ] If Redis down: Restart Redis service
- [ ] If resource exhaustion: Upgrade plan temporarily
- [ ] If unknown: Restart mcp-server service

**Verification:**

- [ ] Health check returns OK
- [ ] Status shows `redis_connected: true`
- [ ] Publish test message successfully
- [ ] Monitor for 5 minutes to ensure stability

**Post-Incident:**

- [ ] Document incident in incident log
- [ ] Create post-mortem (for SEV-1 only)
- [ ] Identify prevention measures
- [ ] Update runbook with learnings

### SEV-2 Incident Response Checklist

**Diagnosis:**

- [ ] Check metrics for degraded performance
- [ ] Review logs for warnings or errors
- [ ] Check S3 archiving status
- [ ] Identify affected components

**Resolution:**

- [ ] Apply targeted fix (see troubleshooting section)
- [ ] Monitor metrics for improvement
- [ ] If not improving after 30min, consider restart

**Verification:**

- [ ] All metrics return to normal ranges
- [ ] No errors in logs
- [ ] User traffic unaffected

---

## Monitoring & Alerts

### Key Metrics to Monitor

#### System Health

| Metric | Normal | Warning | Critical | Action |
|--------|--------|---------|----------|--------|
| `mcp_redis_connected` | 1.0 | N/A | 0.0 | Check Redis service |
| `mcp_kill_switch_active` | 0.0 | 1.0 | N/A | Investigate why |
| `mcp_publish_latency_seconds` (P95) | < 500ms | 500ms-1s | > 1s | Check Redis/resources |
| `mcp_archive_queue_size` | < 50 | 50-100 | > 100 | Check S3 access |
| `mcp_validation_failures_total` rate | Low | Medium | High | Check message quality |

#### Recommended Alerts

**Critical Alerts (Page On-Call):**

1. **Service Down**
   - Condition: Health check fails for 2 consecutive minutes
   - Action: Immediate response required

2. **Redis Disconnected**
   - Condition: `mcp_redis_connected` = 0 for 1 minute
   - Action: Restart Redis, escalate if persists

3. **Kill-Switch Activated**
   - Condition: `mcp_kill_switch_active` = 1
   - Action: Investigate trigger, manual intervention may be required

**Warning Alerts (Notify Team):**

1. **High Latency**
   - Condition: P95 latency > 1s for 5 minutes
   - Action: Investigate performance, consider scaling

2. **Archiver Queue Growing**
   - Condition: `mcp_archive_queue_size` > 100 for 10 minutes
   - Action: Check S3 connectivity

3. **High Validation Failures**
   - Condition: Validation failure rate > 10% for 5 minutes
   - Action: Check message publishers

### Monitoring Tools

**Prometheus + Grafana (Recommended)**
- Scrape `/metrics` endpoint every 15s
- Create dashboards for key metrics
- Set up alert rules

**Render Metrics (Built-in)**
- CPU, Memory, Network usage
- Request rate and response time
- Available in Dashboard → Metrics tab

**Log Aggregation**
- Use structured JSON logs
- Filter by `level`, `channel`, `request_id`
- Search for patterns

---

## Deployment Procedures

### Standard Deployment

**Prerequisites:**
- [ ] All tests passing locally
- [ ] Code reviewed and approved
- [ ] Changelog updated

**Steps:**

1. **Commit and Push**
   ```bash
   git add .
   git commit -m "Description of changes"
   git push origin main
   ```

2. **Monitor Auto-Deploy**
   - Render auto-deploys on push to `main`
   - Monitor: Dashboard → mcp-server → Deploys
   - Typical duration: 3-5 minutes

3. **Verify Deployment**
   ```bash
   # Health check
   curl $MCP_URL/health

   # Check new version (if version changed)
   curl $MCP_URL/.well-known/mcp | jq '.version'

   # Run smoke tests
   ./scripts/run_smoke_tests.sh
   ```

4. **Monitor Post-Deploy**
   - Watch logs for 5-10 minutes
   - Check metrics for anomalies
   - Monitor error rates

**Rollback if Needed:**
```bash
# Dashboard → mcp-server → Deploys
# Click "Redeploy" on last known good deployment
```

### Emergency Deployment

**Use Case:** Critical bug fix, security patch

**Steps:**

1. **Create hotfix branch**
   ```bash
   git checkout -b hotfix/critical-fix
   ```

2. **Make minimal changes**
   - Only fix the critical issue
   - No feature additions

3. **Test thoroughly**
   ```bash
   pytest mcp/tests/ -v
   ```

4. **Deploy**
   ```bash
   git push origin hotfix/critical-fix
   # Manually trigger deploy in Render if needed
   ```

5. **Monitor closely**
   - Stay online for 30 minutes post-deploy
   - Be ready to rollback

### Rollback Procedure

**When to Rollback:**
- Service becomes unhealthy after deploy
- Critical functionality broken
- Performance severely degraded

**Steps:**

1. **Identify Last Known Good Deployment**
   ```bash
   # Dashboard → mcp-server → Deploys
   # Find last successful deploy with "Live" badge
   ```

2. **Initiate Rollback**
   ```bash
   # Click "Redeploy" on last known good version
   ```

3. **Verify Rollback**
   ```bash
   curl $MCP_URL/health
   ./scripts/run_smoke_tests.sh
   ```

4. **Post-Rollback**
   - Investigate root cause of failure
   - Fix in separate branch
   - Re-deploy with proper testing

---

## Emergency Procedures

### Complete Service Restart

**When:** Service completely unresponsive, all other methods failed

1. Stop service (Render Dashboard → Suspend)
2. Wait 60 seconds
3. Resume service
4. Monitor startup logs
5. Run health checks
6. Escalate if still failing

### Redis Data Flush (DANGEROUS)

**⚠️ WARNING:** This deletes all messages in Redis

**When:** Redis memory full, eviction policy failing, corruption suspected

```bash
# Connect to Redis (if accessible)
redis-cli -h <redis-host> -p 6379

# Flush all data (IRREVERSIBLE)
FLUSHALL

# Exit
exit
```

**After flush:**
- Restart MCP server
- Notify all teams (Brain agent will lose state)
- Document in incident log

### S3 Bucket Restore

**When:** Accidental deletion, corruption

**Steps:**
1. Check S3 versioning is enabled
2. List deleted objects
3. Restore from backup or previous versions
4. Verify restored data
5. Resume archiving

---

## Security Operations (Phase 4)

### API Key Management

#### Create New API Key

**When:** New agent deployment, key rotation, new team member

```bash
export ADMIN_KEY="your-admin-api-key"

curl -X POST "$MCP_URL/admin/keys/create" \
  -H "X-API-Key: $ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "role": "feeder",
    "description": "Production feeder agent - n8n workflow"
  }'
```

**Response (SAVE IMMEDIATELY - shown only once):**
```json
{
  "api_key": "mcp_feeder_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6",
  "role": "feeder",
  "key_hash": "7f3e8d2a1c5b9f4e",
  "created_at": 1678886400
}
```

**⚠️ CRITICAL:** The plaintext API key is shown ONLY in this response. Store it securely immediately (e.g., password manager, secure vault). It cannot be recovered later.

#### List All API Keys

```bash
curl -H "X-API-Key: $ADMIN_KEY" "$MCP_URL/admin/keys/list" | jq .
```

**Response:**
```json
{
  "keys": [
    {
      "key_hash": "7f3e8d2a1c5b9f4e",
      "role": "feeder",
      "status": "active",
      "created_at": 1678886400,
      "last_used": 1678886500,
      "description": "Production feeder agent"
    }
  ]
}
```

**Check for:**
- Keys not used recently (potential for revocation)
- Unexpected keys (potential security breach)
- Keys with `admin` role (should be minimal)

#### Rotate API Key

**When:** Scheduled rotation (every 90 days), suspected compromise, departing team member

```bash
# Get key hash from list command above
OLD_KEY_HASH="7f3e8d2a1c5b9f4e"

curl -X POST "$MCP_URL/admin/keys/rotate" \
  -H "X-API-Key: $ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "old_key_hash": "'$OLD_KEY_HASH'",
    "description": "Rotated feeder key - scheduled 90-day rotation"
  }'
```

**Response (SAVE IMMEDIATELY):**
```json
{
  "api_key": "mcp_feeder_x9y8z7w6v5u4t3s2r1q0p9o8n7m6l5k4",
  "role": "feeder",
  "key_hash": "1a2b3c4d5e6f7g8h",
  "created_at": 1678886600,
  "old_key_revoked": true
}
```

**Post-Rotation Steps:**
1. Update client configuration with new key
2. Test client can publish/retrieve successfully
3. Monitor logs for any authentication failures
4. Document rotation in security log

#### Revoke API Key

**When:** Key compromised, agent decommissioned, unauthorized access detected

```bash
curl -X POST "$MCP_URL/admin/keys/revoke" \
  -H "X-API-Key: $ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "key_hash": "7f3e8d2a1c5b9f4e",
    "reason": "Key compromised - rotating immediately"
  }'
```

**Post-Revocation:**
- Immediately create replacement key if needed
- Update affected client configurations
- Monitor for authentication failures from old key
- Document incident if compromise suspected

#### Key Roles and Permissions

| Role | Permissions | Use Case |
|------|------------|----------|
| `admin` | All permissions (`*`) | Operations team, system administrators |
| `feeder` | Publish market/sentiment data, read status | Feeder agent (n8n workflows) |
| `brain` | Publish signals, retrieve data, read kill history | Brain agent (trading logic) |
| `ops` | Retrieve data, kill-switch control, read status | Operations, monitoring tools |
| `readonly` | Retrieve data, read status/metrics | Analytics, reporting tools |

**Principle of Least Privilege:** Always assign the minimum role needed. Most agents should use `feeder`, `brain`, or `readonly` roles. Reserve `admin` for human operators only.

---

### Rate Limiting Configuration

#### Current Rate Limits (Production)

| Limit Type | Default | Purpose |
|------------|---------|---------|
| **Global IP** | 100/minute | Prevent brute force from single source |
| **Global Key** | 200/minute | Per-API-key limit across all endpoints |
| **Publish** | 60/minute | Prevent message flooding |
| **Retrieve** | 30/minute | Protect S3/storage backend |
| **Status** | 120/minute | Allow frequent monitoring |
| **Metrics** | 120/minute | Allow Prometheus scraping |
| **Admin** | 30/minute | Protect sensitive operations |
| **Health** | 300/minute | Allow unrestricted monitoring |

#### Adjust Rate Limits

**When:** Legitimate traffic being rate limited, attack patterns observed, scaling up operations

**Steps:**

1. **Check Current Rejections:**
   ```bash
   curl "$MCP_URL/metrics" | grep "mcp_rate_limit_rejections_total"
   ```

2. **Identify Which Limit is Hit:**
   ```bash
   curl "$MCP_URL/metrics" | grep "mcp_rate_limit_rejections_total" | grep -E "(ip|key|endpoint)"
   ```

3. **Update Environment Variable (Render Dashboard):**
   - Dashboard → mcp-server → Environment
   - Modify: `RATE_LIMIT_PUBLISH=120/minute` (example: double the limit)
   - Click "Save Changes"
   - Service will auto-restart

4. **Verify New Limits:**
   ```bash
   # Check rate limit headers in response
   curl -i -X POST "$MCP_URL/tool/publish" \
     -H "X-API-Key: $KEY" \
     -H "Content-Type: application/json" \
     -d '{...}'

   # Look for headers:
   # X-RateLimit-Limit: 120
   # X-RateLimit-Remaining: 119
   # X-RateLimit-Reset: 1678886460
   ```

5. **Monitor Impact:**
   - Watch rejection metrics for 10 minutes
   - Ensure legitimate traffic no longer rate limited
   - Document change in operations log

#### Rate Limit Format

All rate limits use the format: `<requests>/<unit>`

**Supported units:**
- `second`: e.g., `10/second`
- `minute`: e.g., `100/minute`
- `hour`: e.g., `1000/hour`

**Examples:**
```bash
RATE_LIMIT_PUBLISH=60/minute      # 60 requests per minute
RATE_LIMIT_GLOBAL_IP=100/minute   # 100 requests per minute per IP
RATE_LIMIT_HEALTH=300/minute      # 300 requests per minute (for monitoring)
```

#### Monitoring Rate Limiting

**Key Metrics:**

```bash
# Total rejections by type
curl "$MCP_URL/metrics" | grep "mcp_rate_limit_rejections_total"

# Example output:
# mcp_rate_limit_rejections_total{type="ip"} 42
# mcp_rate_limit_rejections_total{type="key"} 8
# mcp_rate_limit_rejections_total{type="endpoint"} 15
```

**Set up Alerts:**
- Warning: > 10 rejections/minute for 5 minutes (may indicate legitimate traffic spike)
- Critical: > 100 rejections/minute for 1 minute (likely attack or misconfiguration)

**Response Headers:**

Every response includes rate limit information:
```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1678886460
```

**When rate limited, client receives:**
```
HTTP 429 Too Many Requests
Retry-After: 42

{
  "detail": "Rate limit exceeded. Try again in 42 seconds.",
  "request_id": "req_abc123"
}
```

---

### Security Incident Response

#### Suspected Unauthorized Access

**Indicators:**
- Unexpected API calls in logs
- Authentication attempts from unknown IPs
- Unusual publish/retrieve patterns
- Admin endpoint access from unexpected sources

**Immediate Actions (First 5 minutes):**

1. **Activate Kill-Switch (if financial risk):**
   ```bash
   curl -X POST "$MCP_URL/tool/kill_activate" \
     -H "X-API-Key: $ADMIN_KEY" \
     -H "Content-Type: application/json" \
     -d '{
       "reason": "Security incident - unauthorized access detected"
     }'
   ```

2. **Review Recent Activity:**
   ```bash
   # Check logs for suspicious API key usage
   # Dashboard → mcp-server → Logs
   # Filter: last 1 hour, search for 401/403 errors
   ```

3. **List All API Keys:**
   ```bash
   curl -H "X-API-Key: $ADMIN_KEY" "$MCP_URL/admin/keys/list" | jq .
   ```

4. **Check for Unexpected Keys:**
   - Look for recently created keys
   - Verify descriptions match expected agents
   - Check `last_used` timestamps

**Investigation (5-30 minutes):**

1. **Review Audit Logs:**
   ```bash
   # Check for key creation/rotation/revocation events
   # Look for: "Key created", "Key revoked", "Key rotated"
   # Verify "created_by" field matches expected admin keys
   ```

2. **Identify Compromised Keys:**
   - Keys with unexpected `last_used` timestamps
   - Keys accessing unexpected endpoints
   - Keys from unexpected IP addresses

3. **Assess Impact:**
   - What data was accessed?
   - Were any messages published?
   - Was admin functionality used?

**Containment (30-60 minutes):**

1. **Revoke Compromised Keys:**
   ```bash
   curl -X POST "$MCP_URL/admin/keys/revoke" \
     -H "X-API-Key: $ADMIN_KEY" \
     -H "Content-Type: application/json" \
     -d '{
       "key_hash": "COMPROMISED_KEY_HASH",
       "reason": "Security incident #001 - unauthorized access"
     }'
   ```

2. **Rotate All Potentially Affected Keys:**
   - If admin key compromised: Rotate ALL keys
   - If feeder key compromised: Rotate feeder key only
   - Update all client configurations

3. **Temporarily Reduce Rate Limits (if under attack):**
   ```bash
   # Dashboard → Environment
   RATE_LIMIT_GLOBAL_IP=50/minute  # Reduce from 100
   RATE_LIMIT_ADMIN=10/minute      # Reduce from 30
   ```

**Recovery:**

1. **Create Replacement Keys:**
   ```bash
   curl -X POST "$MCP_URL/admin/keys/create" \
     -H "X-API-Key: $ADMIN_KEY" \
     -d '{"role": "feeder", "description": "Replacement key after incident #001"}'
   ```

2. **Update Client Configurations:**
   - Update environment variables in client services
   - Restart client services
   - Verify successful authentication

3. **Deactivate Kill-Switch (if activated):**
   ```bash
   curl -X POST "$MCP_URL/tool/kill_deactivate" \
     -H "X-API-Key: $ADMIN_KEY" \
     -H "Content-Type: application/json"
   ```

4. **Restore Rate Limits:**
   - Return to normal rate limit values
   - Monitor for continued attack

**Post-Incident:**

- [ ] Document incident in security log (docs/SECURITY.md)
- [ ] Identify how unauthorized access occurred
- [ ] Implement preventative measures
- [ ] Update procedures if needed
- [ ] Schedule security review

#### Suspected Brute Force Attack

**Indicators:**
- High rate of 401 authentication failures
- High `mcp_rate_limit_rejections_total` counter
- Many requests from single IP or IP range
- Pattern of authentication attempts

**Immediate Actions:**

1. **Verify Attack Pattern:**
   ```bash
   # Check rate limit rejections
   curl "$MCP_URL/metrics" | grep "mcp_rate_limit_rejections_total"

   # Check authentication failures
   # Dashboard → Logs → Filter: "401" or "403"
   ```

2. **Verify Rate Limiting is Working:**
   ```bash
   # Should see 429 responses to attacker
   # Rate limit headers should show exhausted limits
   ```

**Response:**

**Good News:** Triple-tier rate limiting (IP, key, endpoint) should automatically mitigate brute force attacks. No immediate action needed unless:

- Legitimate traffic is being rate limited (increase limits)
- Attack is distributed across many IPs (consider CDN/WAF)
- Attack is exploiting a specific endpoint (temporarily reduce that endpoint's limit)

**If Action Needed:**

1. **Temporarily Reduce Global IP Limit:**
   ```bash
   # Dashboard → Environment
   RATE_LIMIT_GLOBAL_IP=50/minute  # Reduce from 100
   ```

2. **Monitor Metrics:**
   ```bash
   watch -n 5 'curl -s "$MCP_URL/metrics" | grep "mcp_rate_limit_rejections_total"'
   ```

3. **Consider Infrastructure-Level Blocking:**
   - Use Render.com firewall (if available in plan)
   - Consider adding Cloudflare or AWS WAF
   - Contact Render support if attack persists

**Post-Incident:**

- Document attack patterns
- Adjust rate limits if needed
- Consider additional protection (IP allowlisting for admin endpoints)

#### S3 Security Breach

**Indicators:**
- Unexpected S3 access in AWS CloudTrail
- S3 access denied errors in logs
- AWS sends security notification
- Unauthorized data modification/deletion

**Immediate Actions:**

1. **Verify S3 Bucket Access:**
   ```bash
   aws s3 ls s3://mcp-data-prod-kamesh.888/
   # Should list bucket contents
   # If denied: credentials may be revoked
   ```

2. **Check IAM User Status:**
   ```bash
   # AWS Console → IAM → Users → mcp-server-user
   # Verify: User exists, access keys active
   ```

3. **Review S3 Access Logs (if enabled):**
   ```bash
   # Check S3_LOGS_BUCKET for suspicious access
   aws s3 ls s3://$S3_LOGS_BUCKET/s3-access-logs/ --recursive | \
     grep "$(date +%Y-%m-%d)"
   ```

**Containment:**

1. **Rotate AWS Credentials Immediately:**
   ```bash
   # AWS Console → IAM → Users → mcp-server-user → Security credentials
   # Create new access key
   # Store securely
   ```

2. **Update MCP Server Configuration:**
   ```bash
   # Dashboard → Environment
   AWS_ACCESS_KEY_ID=<new_key_id>
   AWS_SECRET_ACCESS_KEY=<new_secret_key>
   # Save changes (triggers restart)
   ```

3. **Delete Old Access Key:**
   ```bash
   # AWS Console → IAM → Users → mcp-server-user
   # Delete old access key (after verifying new key works)
   ```

4. **Verify S3 Security Hardening:**
   ```bash
   # Run security hardening script
   cd mcp/scripts
   export S3_DATA_BUCKET=mcp-data-prod-kamesh.888
   export AWS_REGION=eu-north-1
   ./harden_s3_security.sh
   ```

**Recovery:**

1. **Verify Data Integrity:**
   ```bash
   # Check recent uploads
   aws s3 ls s3://$S3_DATA_BUCKET/mcp/ --recursive | \
     grep "$(date +%Y-%m-%d)" | tail -20
   ```

2. **Restore from Versioning (if data modified/deleted):**
   ```bash
   # S3 versioning should be enabled (Phase 4.3)
   # AWS Console → S3 → Bucket → Show versions
   # Restore deleted/modified objects
   ```

3. **Resume Normal Operations:**
   - Verify archiver queue is processing
   - Check metrics for upload success

**Post-Incident:**

- Review IAM policy (ensure least-privilege)
- Enable S3 access logging if not already enabled
- Document incident and resolution
- Consider additional S3 security measures (MFA delete, cross-region replication)

---

### S3 Security Hardening (Phase 4.3)

#### Run Security Hardening Script

**When:** Initial deployment, after security audit, compliance requirement

```bash
cd mcp/scripts

# Set environment variables
export S3_DATA_BUCKET=mcp-data-prod-kamesh.888
export AWS_REGION=eu-north-1

# Optional: Enable access logging
export ENABLE_ACCESS_LOGGING=true
export S3_LOGS_BUCKET=mcp-logs-prod-kamesh.888

# Run script
./harden_s3_security.sh
```

**Script Actions:**
1. ✅ Enable bucket versioning (data recovery)
2. ✅ Enable server-side encryption (AES256)
3. ✅ Block public access (prevent exposure)
4. ✅ Enable default encryption (all new objects)
5. ✅ Enable access logging (optional, for compliance)

**Expected Output:**
```
=========================================
  MCP Server S3 Security Hardening
=========================================

[✓] Bucket Versioning applied successfully
    Benefits:
      ✓ Protects against accidental deletion
      ✓ Enables data recovery from previous versions
      ✓ Maintains audit trail of changes

[✓] Server-Side Encryption applied successfully
    ...

✅ Your S3 bucket is now hardened with:
   • Versioning enabled (data recovery)
   • Server-side encryption (data at rest)
   • Public access blocked (privacy)
   • Default encryption enforced (all new objects)

Security Status: EXCELLENT
```

#### Verify S3 Security Configuration

**Check Versioning:**
```bash
aws s3api get-bucket-versioning \
  --bucket $S3_DATA_BUCKET \
  --region $AWS_REGION | jq .
# Should show: "Status": "Enabled"
```

**Check Encryption:**
```bash
aws s3api get-bucket-encryption \
  --bucket $S3_DATA_BUCKET \
  --region $AWS_REGION | jq .
# Should show: "SSEAlgorithm": "AES256"
```

**Check Public Access Block:**
```bash
aws s3api get-public-access-block \
  --bucket $S3_DATA_BUCKET \
  --region $AWS_REGION | jq .
# Should show all values: true
```

#### IAM Policy Review

**Verify Least-Privilege IAM Policy:**

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:GetObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::mcp-data-prod-kamesh.888",
        "arn:aws:s3:::mcp-data-prod-kamesh.888/*"
      ]
    }
  ]
}
```

**Principle:** MCP server should ONLY have access to its specific bucket and only the actions it needs (put, get, list). No delete, no other buckets.

---

### Key Rotation Schedule

**Recommended Schedule:**

| Component | Rotation Frequency | Procedure |
|-----------|-------------------|-----------|
| API Keys (non-admin) | Every 90 days | Use `/admin/keys/rotate` endpoint |
| API Keys (admin) | Every 60 days | Use `/admin/keys/rotate` endpoint |
| AWS Credentials | Every 90 days | AWS Console → IAM → Rotate keys |
| Legacy MCP_API_KEY | At deployment | Rotate immediately after initial setup |

**Rotation Calendar (Example for Q1 2025):**

- **January 15:** Rotate feeder key
- **January 22:** Rotate brain key
- **February 1:** Rotate admin key
- **February 15:** Rotate AWS credentials
- **March 1:** Rotate ops/readonly keys

**Automation Opportunity:** Consider creating a scheduled job or calendar reminders for key rotation.

---

### Security Checklist (Weekly)

Use this checklist for regular security audits:

#### Authentication & Authorization
- [ ] All API keys have recent `last_used` timestamps
- [ ] No unexpected keys in `/admin/keys/list`
- [ ] Admin keys limited to designated personnel only
- [ ] Legacy MCP_API_KEY has been rotated (not using default)

#### Rate Limiting
- [ ] Rate limit rejection metrics reviewed
- [ ] No legitimate traffic being rate limited
- [ ] Rate limits appropriate for current load

#### Access Logs
- [ ] No unusual authentication failures (401/403)
- [ ] No unexpected API endpoint access
- [ ] Admin endpoint access only from expected sources

#### Infrastructure
- [ ] S3 bucket public access still blocked
- [ ] S3 bucket versioning still enabled
- [ ] S3 bucket encryption still enabled
- [ ] AWS IAM user status: active and healthy

#### Dependencies
- [ ] No known vulnerabilities in Python packages
- [ ] Docker base image up to date

---

## Contact Information

### Escalation Path

1. **Level 1:** Operations Team (you)
2. **Level 2:** On-Call Engineering Lead
3. **Level 3:** System Architect / CTO

### Communication Channels

- **Incidents:** #incidents (Slack/Teams)
- **Operations:** #ops (Slack/Teams)
- **Engineering:** #engineering (Slack/Teams)

### External Dependencies

| Service | Contact | SLA |
|---------|---------|-----|
| Render.com | support@render.com | Response within 24hrs (Free tier) |
| AWS Support | AWS Console | Depends on support plan |

---

## Appendix

### Useful Commands Cheat Sheet

```bash
# Health & Status
curl $MCP_URL/health
curl -H "x-api-key: $KEY" $MCP_URL/tool/get_status
curl $MCP_URL/metrics

# Publish Test Message
curl -X POST $MCP_URL/tool/publish \
  -H "x-api-key: $KEY" \
  -H "Content-Type: application/json" \
  -d '{"channel":"market:data","message":{...}}'

# Check S3 Files
aws s3 ls s3://$BUCKET/mcp/market_data/ --recursive | tail -20

# View Logs (with jq filtering)
render logs --tail mcp-server | jq 'select(.level == "ERROR")'

# Check Metrics for Specific Channel
curl $MCP_URL/metrics | grep 'channel="market:data"'
```

---

**Document Version:** 1.0
**Maintained By:** MCP Operations Team
**Review Frequency:** Quarterly or after major incidents
**Next Review:** March 2026
