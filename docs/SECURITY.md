# MCP Server Security Documentation

**Version:** 1.0
**Last Updated:** 2025-12-10
**Maintainer:** MCP Security Team

---

## Table of Contents

1. [Security Overview](#security-overview)
2. [API Key Management](#api-key-management)
3. [IAM & S3 Security](#iam--s3-security)
4. [Rate Limiting](#rate-limiting)
5. [Network Security](#network-security)
6. [Security Best Practices](#security-best-practices)
7. [Incident Response](#incident-response)
8. [Compliance & Audit](#compliance--audit)

---

## Security Overview

### **Security Layers**

The MCP Server implements defense-in-depth with multiple security layers:

```
┌─────────────────────────────────────────┐
│  Layer 1: Network (TLS, Firewall)       │
├─────────────────────────────────────────┤
│  Layer 2: Rate Limiting (DoS Protection)│
├─────────────────────────────────────────┤
│  Layer 3: Authentication (API Keys)     │
├─────────────────────────────────────────┤
│  Layer 4: Authorization (Permissions)   │
├─────────────────────────────────────────┤
│  Layer 5: Input Validation (Schemas)    │
├─────────────────────────────────────────┤
│  Layer 6: Audit Logging (All Actions)   │
└─────────────────────────────────────────┘
```

### **Security Features**

- ✅ **Multi-Key Authentication**: Role-based API key system
- ✅ **Rate Limiting**: Per-IP and per-key limits
- ✅ **Security Headers**: HSTS, X-Frame-Options, CSP
- ✅ **Input Validation**: JSON schema validation
- ✅ **Audit Logging**: Structured JSON logs with request IDs
- ✅ **Secret Sanitization**: No credentials in logs
- ✅ **Least-Privilege IAM**: Scoped S3 permissions
- ✅ **S3 Encryption**: Server-side encryption at rest

---

## API Key Management

### **Key Format**

```
mcp_<role>_<32_random_hex_chars>

Examples:
- mcp_admin_a1b2c3d4e5f6789012345678abcdef01
- mcp_feeder_9f8e7d6c5b4a3210fedcba9876543210
- mcp_brain_1234567890abcdef1234567890abcdef
```

### **Roles & Permissions**

| Role | Permissions | Use Case |
|------|-------------|----------|
| **admin** | All operations (`*`) | System administration, key management |
| **feeder** | `publish:market:data`<br>`publish:sentiment:data`<br>`status:read` | n8n feeder agent |
| **brain** | `publish:agent:signal`<br>`retrieve:*`<br>`kill_history:read`<br>`status:read` | Python brain agent |
| **ops** | `publish:agent:control`<br>`status:read`<br>`kill_history:read`<br>`admin:keys:list` | Operations team |
| **readonly** | `status:read`<br>`metrics:read` | Monitoring systems |

### **Creating API Keys**

#### **Option 1: Via Admin Endpoint (Recommended)**

```bash
# Create a feeder key
curl -X POST https://mcp-server.example.com/admin/keys/create \
  -H "x-api-key: $ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "role": "feeder",
    "description": "Production n8n feeder agent"
  }'

# Response:
{
  "api_key": "mcp_feeder_a1b2c3d4e5f6...",  # SAVE THIS - SHOWN ONLY ONCE
  "key_hash": "sha256...",
  "role": "feeder",
  "description": "Production n8n feeder agent",
  "created_at": 1678886400,
  "key_suffix": "...def0",
  "warning": "Store this API key securely. It will not be shown again."
}
```

#### **Option 2: Initial Admin Key (First Time Setup)**

On first deployment, set the `MCP_API_KEY` environment variable. This will be auto-registered as an admin key on server startup.

```bash
# In Render.com dashboard or .env file
MCP_API_KEY=your-secure-random-key-here
```

**⚠️ IMPORTANT**: Generate a strong random key:
```bash
# Generate secure random key (32 bytes = 64 hex chars)
openssl rand -hex 32
```

### **Listing API Keys**

```bash
curl -H "x-api-key: $ADMIN_KEY" \
  https://mcp-server.example.com/admin/keys/list | jq

# Response:
{
  "keys": [
    {
      "key_hash": "a1b2c3d4...",  # Redacted
      "role": "feeder",
      "description": "Production n8n feeder agent",
      "created_at": 1678886400,
      "last_used": 1678896400,
      "usage_count": 12345,
      "key_suffix": "...def0",
      "revoked": false,
      "revoked_at": null
    }
  ],
  "count": 1,
  "include_revoked": false
}
```

### **Revoking API Keys**

```bash
# Revoke a compromised key
curl -X POST https://mcp-server.example.com/admin/keys/revoke \
  -H "x-api-key: $ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "api_key": "mcp_feeder_a1b2c3d4e5f6..."
  }'

# Response:
{
  "success": true,
  "message": "API key revoked successfully"
}
```

### **Rotating API Keys**

**Best Practice**: Rotate keys every 90 days

```bash
# Rotate a key (creates new, revokes old)
curl -X POST https://mcp-server.example.com/admin/keys/rotate \
  -H "x-api-key: $ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "old_api_key": "mcp_feeder_old_key_here"
  }'

# Response: (new key with same role)
{
  "api_key": "mcp_feeder_new_random_key",  # SAVE THIS
  "key_hash": "sha256...",
  "role": "feeder",
  "description": "Production n8n feeder agent (rotated)",
  "created_at": 1678896400,
  "key_suffix": "...xyz9",
  "warning": "Store this API key securely. It will not be shown again."
}
```

**Rotation Procedure:**
1. Generate new key via `/admin/keys/rotate`
2. Update service configuration with new key
3. Verify service works with new key
4. Old key is automatically revoked

---

## IAM & S3 Security

### **Least-Privilege IAM Policy**

**IAM User**: `888-mcp-user`
**S3 Bucket**: `mcp-data-prod-kamesh.888`
**Region**: `eu-north-1`

#### **Recommended IAM Policy**

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "MCPServerS3ReadWrite",
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:GetObject"
      ],
      "Resource": "arn:aws:s3:::mcp-data-prod-kamesh.888/mcp/*"
    },
    {
      "Sid": "MCPServerS3List",
      "Effect": "Allow",
      "Action": [
        "s3:ListBucket"
      ],
      "Resource": "arn:aws:s3:::mcp-data-prod-kamesh.888",
      "Condition": {
        "StringLike": {
          "s3:prefix": "mcp/*"
        }
      }
    }
  ]
}
```

**Policy Explanation:**
- ✅ **Scoped to specific bucket**: Not `s3:*` on all buckets
- ✅ **Scoped to specific prefix**: Only `mcp/*` directory
- ✅ **Minimal permissions**: Only PutObject, GetObject, ListBucket
- ✅ **No delete permissions**: Append-only storage (cannot delete data)
- ✅ **No public access**: Bucket is private

#### **Applying the Policy**

1. Go to AWS Console → IAM → Users → `888-mcp-user`
2. Click "Add permissions" → "Attach policies directly"
3. Create new inline policy with the JSON above
4. Save as "MCP-Server-S3-Access"

### **S3 Security Hardening**

#### **1. Enable Bucket Versioning**

Protects against accidental deletion or overwrite:

```bash
aws s3api put-bucket-versioning \
  --bucket mcp-data-prod-kamesh.888 \
  --versioning-configuration Status=Enabled \
  --region eu-north-1
```

**Why**: If data is accidentally deleted/modified, previous versions can be recovered.

#### **2. Enable Server-Side Encryption**

Encrypt data at rest:

```bash
aws s3api put-bucket-encryption \
  --bucket mcp-data-prod-kamesh.888 \
  --server-side-encryption-configuration '{
    "Rules": [{
      "ApplyServerSideEncryptionByDefault": {
        "SSEAlgorithm": "AES256"
      },
      "BucketKeyEnabled": true
    }]
  }' \
  --region eu-north-1
```

**Why**: Protects data if S3 bucket is compromised.

#### **3. Block Public Access**

Ensure bucket is private:

```bash
aws s3api put-public-access-block \
  --bucket mcp-data-prod-kamesh.888 \
  --public-access-block-configuration \
    "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true" \
  --region eu-north-1
```

**Why**: Prevents accidental public exposure of trading data.

#### **4. Enable Access Logging (Optional)**

Track all S3 access for audit:

```bash
# First, create a logging bucket
aws s3 mb s3://mcp-logs-kamesh.888 --region eu-north-1

# Enable logging
aws s3api put-bucket-logging \
  --bucket mcp-data-prod-kamesh.888 \
  --bucket-logging-status '{
    "LoggingEnabled": {
      "TargetBucket": "mcp-logs-kamesh.888",
      "TargetPrefix": "s3-access-logs/"
    }
  }' \
  --region eu-north-1
```

**Note**: Adds cost (~$0.01/GB). Enable if compliance requires audit trail.

#### **5. Enable Object Lock (Optional)**

Prevent deletion for compliance (WORM):

```bash
# WARNING: Can only be enabled on bucket creation
# Create new bucket with object lock
aws s3api create-bucket \
  --bucket mcp-data-prod-kamesh-locked.888 \
  --region eu-north-1 \
  --object-lock-enabled-for-bucket

# Set retention policy
aws s3api put-object-lock-configuration \
  --bucket mcp-data-prod-kamesh-locked.888 \
  --object-lock-configuration '{
    "ObjectLockEnabled": "Enabled",
    "Rule": {
      "DefaultRetention": {
        "Mode": "GOVERNANCE",
        "Days": 90
      }
    }
  }'
```

**Use Case**: Regulatory compliance (cannot delete data for 90 days).

### **Verifying S3 Security**

```bash
# Check versioning status
aws s3api get-bucket-versioning \
  --bucket mcp-data-prod-kamesh.888

# Check encryption
aws s3api get-bucket-encryption \
  --bucket mcp-data-prod-kamesh.888

# Check public access block
aws s3api get-public-access-block \
  --bucket mcp-data-prod-kamesh.888
```

---

## Rate Limiting

### **Rate Limit Configuration**

| Limit Type | Default | Environment Variable | Description |
|------------|---------|---------------------|-------------|
| **Global IP** | 100/minute | `RATE_LIMIT_GLOBAL_IP` | Per-IP limit (DoS protection) |
| **Global Key** | 200/minute | `RATE_LIMIT_GLOBAL_KEY` | Per-API-key limit |
| **Publish** | 60/minute | `RATE_LIMIT_PUBLISH` | `/tool/publish` endpoint |
| **Retrieve** | 30/minute | `RATE_LIMIT_RETRIEVE` | `/tool/retrieve` endpoint |
| **Status** | 120/minute | `RATE_LIMIT_STATUS` | Status endpoints |
| **Metrics** | 120/minute | `RATE_LIMIT_METRICS` | `/metrics` endpoint |
| **Admin** | 30/minute | `RATE_LIMIT_ADMIN` | Admin endpoints |
| **Health** | 300/minute | `RATE_LIMIT_HEALTH` | `/health` endpoint |

### **Rate Limit Headers**

All responses include rate limit headers:

```http
HTTP/1.1 200 OK
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 45
X-RateLimit-Reset: 1678886460
X-Request-ID: a1b2c3d4-e5f6-7890-1234-567890abcdef
```

### **Rate Limit Exceeded (429)**

```http
HTTP/1.1 429 Too Many Requests
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1678886460
Retry-After: 42

{
  "detail": "Rate limit exceeded: 60/minute",
  "retry_after": 42
}
```

### **Adjusting Rate Limits**

Update environment variables in Render.com:

```bash
# Dashboard → mcp-server → Environment
RATE_LIMIT_PUBLISH=120/minute  # Increase to 120 requests/min
```

---

## Network Security

### **TLS/HTTPS**

- ✅ **Enforced by Render.com**: All traffic is HTTPS
- ✅ **HSTS Header**: `Strict-Transport-Security: max-age=31536000`
- ✅ **TLS 1.2+**: Modern cipher suites only

### **IP Allow-listing (Optional)**

Restrict Redis access to MCP server only:

```yaml
# render.yaml
- type: redis
  name: mcp-redis
  ipAllowList: []  # Empty = private network only
```

### **Security Headers**

All responses include:

```http
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
X-XSS-Protection: 1; mode=block
Strict-Transport-Security: max-age=31536000; includeSubDomains
```

---

## Security Best Practices

### **1. API Key Management**

- ✅ **Never commit keys to git**: Use environment variables
- ✅ **Rotate keys every 90 days**: Use `/admin/keys/rotate`
- ✅ **Use least-privilege roles**: Don't use admin keys for agents
- ✅ **Revoke compromised keys immediately**: Use `/admin/keys/revoke`
- ✅ **Monitor key usage**: Check `usage_count` and `last_used`

### **2. Environment Variables**

Store secrets securely in Render.com dashboard:

```bash
# DO NOT commit to git:
MCP_API_KEY=secret-admin-key
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=secret...

# Safe to commit (no secrets):
RATE_LIMIT_PUBLISH=60/minute
LOG_LEVEL=INFO
```

### **3. Monitoring**

**Watch for:**
- Rate limit violations: `mcp_validation_failures_total{error_type="ip_limit_exceeded"}`
- Failed auth attempts: `HTTP 401` responses
- Permission denials: `HTTP 403` responses
- Unusual traffic patterns: Sudden spikes in publish rate

### **4. Incident Response**

**If API key is compromised:**
1. Immediately revoke: `POST /admin/keys/revoke`
2. Check logs for suspicious activity: Filter by `key_suffix`
3. Generate new key: `POST /admin/keys/create`
4. Update service configuration with new key
5. Document incident in security log

### **5. Regular Security Reviews**

**Monthly:**
- Review active API keys (`/admin/keys/list`)
- Check for unused keys (low `usage_count`)
- Review rate limit violations in metrics
- Verify IAM policy is still least-privilege

**Quarterly:**
- Rotate all API keys
- Review S3 access logs (if enabled)
- Security audit of endpoints and permissions
- Update dependencies: `pip list --outdated`

---

## Incident Response

### **Security Incident Classification**

| Severity | Description | Response Time | Example |
|----------|-------------|---------------|---------|
| **SEV-1** | Active attack, data breach | Immediate | Compromised admin key, S3 bucket public |
| **SEV-2** | Potential security issue | Within 1 hour | Suspected key compromise, rate limit bypass |
| **SEV-3** | Security best practice violation | Within 24 hours | Expired key rotation, weak key detected |

### **SEV-1 Incident Checklist**

**Immediate Actions (First 5 minutes):**
- [ ] Alert security team
- [ ] Identify scope (which keys/data compromised)
- [ ] Revoke compromised keys
- [ ] Check logs for unauthorized access
- [ ] Enable S3 MFA delete (if not already enabled)

**Containment (5-30 minutes):**
- [ ] Generate new keys for affected services
- [ ] Update service configurations
- [ ] Verify no ongoing unauthorized access
- [ ] Document all actions taken

**Recovery (30 minutes - 2 hours):**
- [ ] Restore normal operations
- [ ] Monitor for 24 hours
- [ ] Review and strengthen security controls

**Post-Incident:**
- [ ] Write post-mortem
- [ ] Implement preventive measures
- [ ] Update security documentation
- [ ] Notify stakeholders (if required)

### **Contact Information**

**Security Team:**
- Email: security@example.com
- Slack: #security-incidents
- On-Call: PagerDuty rotation

---

## Compliance & Audit

### **Audit Logging**

All security-relevant events are logged:

```json
{
  "@timestamp": 1678886400.123,
  "level": "INFO",
  "logger": "mcp.server",
  "message": "API key created",
  "request_id": "a1b2c3d4-...",
  "role": "feeder",
  "key_suffix": "...def0",
  "created_by": "admin"
}
```

**Searchable Fields:**
- `level:ERROR` - All errors
- `message:"API key"` - All key operations
- `role:feeder` - All feeder agent activity
- `request_id:<uuid>` - Trace specific request

### **Compliance Requirements**

**PCI DSS (if handling payment data):**
- ✅ Encrypt data in transit (TLS)
- ✅ Encrypt data at rest (S3 encryption)
- ✅ Restrict access (least-privilege IAM)
- ✅ Monitor and log access (structured logging)
- ✅ Rotate keys regularly (90-day rotation)

**GDPR (if handling EU user data):**
- ✅ Data retention policy (S3 lifecycle rules)
- ✅ Access controls (role-based permissions)
- ✅ Audit trail (structured logs)
- ✅ Right to deletion (manual process via S3)

---

## Security Checklist

### **Initial Deployment**

- [ ] Generate strong `MCP_API_KEY`
- [ ] Set up IAM user with least-privilege policy
- [ ] Enable S3 bucket versioning
- [ ] Enable S3 server-side encryption
- [ ] Block S3 public access
- [ ] Configure rate limits
- [ ] Enable structured logging
- [ ] Set up monitoring alerts

### **Ongoing Maintenance**

- [ ] Rotate API keys every 90 days
- [ ] Review active keys monthly
- [ ] Monitor rate limit violations
- [ ] Review security logs weekly
- [ ] Update dependencies quarterly
- [ ] Conduct security audit annually

---

**Document Version:** 1.0
**Last Review:** 2025-12-10
**Next Review:** 2026-03-10
**Maintained By:** MCP Security Team
