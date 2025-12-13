# Phase 6 Security Remediation Plan

**Date:** 2025-12-13
**Status:** 🚨 ACTION REQUIRED
**Priority:** CRITICAL
**Auditor:** System Security Team

---

## Executive Summary

The Phase 6 RAG endpoint implementation introduced functional vector search capabilities but **violated Phase 4 security standards**. This document provides a comprehensive remediation workflow to bring the endpoint into compliance with established security protocols.

### Issues Identified

| Issue | Severity | Status | Impact |
|-------|----------|--------|--------|
| Missing `httpx` dependency | 🔴 CRITICAL | ✅ **RESOLVED** (already in requirements.txt) | Would crash in production |
| Missing RBAC permissions | 🟡 MAJOR | ⚠️ **OPEN** | Unauthorized access possible |
| Missing rate limiting | 🟡 MAJOR | ⚠️ **OPEN** | DoS attack vector, cost bleed |
| Inconsistent security patterns | 🟢 MINOR | ⚠️ **OPEN** | Technical debt, maintainability |

---

## Current State Analysis

### ✅ What Works

1. **Dependency Management**
   - `httpx==0.25.1` is already in [requirements.txt](../mcp/requirements.txt:8)
   - No runtime crashes expected

2. **Basic Authentication**
   - Endpoint requires `x-api-key` header
   - Uses `verify_api_key` dependency
   - Works in dev mode (MCP_DEV=true)

3. **Functional Logic**
   - Vector engine abstraction works correctly
   - Mock engine returns test data
   - Remote engine architecture is sound

### ⚠️ What's Missing

1. **Role-Based Access Control (RBAC)**
   - **Current:** ANY authenticated key can call `/tool/search_rag`
   - **Expected:** Only keys with `retrieve:rag` permission should access
   - **Violation:** Admin endpoints use `verify_permission("admin:keys:create")`, but RAG doesn't

2. **Rate Limiting**
   - **Current:** No per-endpoint rate limit on `/tool/search_rag`
   - **Expected:** Dedicated rate limit (e.g., `RATE_LIMIT_RAG=30/minute`)
   - **Risk:** External API calls cost money; unchecked access = financial bleeding

3. **Permission Registration**
   - **Current:** No `retrieve:rag` permission defined in `ROLE_PERMISSIONS`
   - **Expected:** Brain and admin roles should have `retrieve:rag`
   - **Impact:** Can't enforce RBAC until permission exists

---

## Security Architecture Review

### Phase 4 Security Standards (Established)

The MCP server implements a **3-layer security model**:

```
┌─────────────────────────────────────┐
│  Layer 1: Per-IP Global Limit      │  ← Middleware (100/minute)
│  Prevents DoS from single IP       │
├─────────────────────────────────────┤
│  Layer 2: Per-Key Global Limit     │  ← Middleware (200/minute)
│  Fair usage enforcement             │
├─────────────────────────────────────┤
│  Layer 3: Per-Endpoint RBAC Limit  │  ← Endpoint dependency
│  Fine-grained permission control    │  ← verify_permission("action:resource")
└─────────────────────────────────────┘
```

### Current RAG Endpoint Security

```
┌─────────────────────────────────────┐
│  Layer 1: Per-IP Global Limit      │  ✅ Active (middleware)
├─────────────────────────────────────┤
│  Layer 2: Per-Key Global Limit     │  ✅ Active (middleware)
├─────────────────────────────────────┤
│  Layer 3: Per-Endpoint RBAC Limit  │  ❌ MISSING
│  - No verify_permission()           │
│  - No retrieve:rag permission       │
│  - No RATE_LIMIT_RAG                │
└─────────────────────────────────────┘
```

**Security Gap:** Layer 3 missing means:
- A **readonly** key (intended for metrics only) can spam RAG endpoint
- Cost $0.0001 per query × 10,000 requests = **$1 accidental spend**
- No audit trail of which role accessed RAG

---

## Threat Modeling

### Threat 1: Cost Bleed Attack

**Scenario:**
Attacker obtains a `readonly` API key (e.g., leaked in logs, CI pipeline)

**Attack:**
```bash
# Spam RAG endpoint with valid key
for i in {1..10000}; do
  curl -X POST https://mcp-server.com/tool/search_rag \
    -H "x-api-key: mcp_readonly_stolen123" \
    -d '{"query": "test", "limit": 100}'
done
```

**Impact:**
- 10,000 requests × $0.0001 = **$1 vector DB cost**
- Server CPU/RAM spike → legitimate traffic blocked
- No permission enforcement → attack succeeds with ANY key

**Current Defense:** ⚠️ Layers 1-2 only (IP/key global limits)
**Required Defense:** ✅ Layer 3 (RBAC + endpoint rate limit)

### Threat 2: Privilege Escalation

**Scenario:**
`feeder` role key (intended for publishing data only) is compromised

**Attack:**
```bash
# Use feeder key to extract all historical data via RAG
curl -X POST https://mcp-server.com/tool/search_rag \
  -H "x-api-key: mcp_feeder_production123" \
  -d '{"query": "all trade signals", "limit": 100}'
```

**Impact:**
- **Data exfiltration** of proprietary trading signals
- Violates least-privilege principle
- No audit trail of unauthorized access

**Current Defense:** ❌ None (feeder key works)
**Required Defense:** ✅ RBAC (`feeder` should NOT have `retrieve:rag`)

---

## Remediation Workflow

### Step 1: Add `retrieve:rag` Permission to Auth System

**File:** [mcp/auth.py](../mcp/auth.py)

**Current State (lines 29-57):**
```python
ROLE_PERMISSIONS: Dict[str, Set[str]] = {
    "admin": {
        "*",  # All permissions (wildcard)
    },
    "feeder": {
        "publish:market:data",
        "publish:sentiment:data",
        "status:read",
        "metrics:read",
    },
    "brain": {
        "publish:agent:signal",
        "retrieve:*",  # ← Brain already has retrieve:* wildcard!
        "kill_history:read",
        "status:read",
        "metrics:read",
    },
    "ops": {
        "publish:agent:control",
        "status:read",
        "kill_history:read",
        "metrics:read",
        "admin:keys:list",
    },
    "readonly": {
        "status:read",
        "metrics:read",
    },
}
```

**Analysis:**
- ✅ `brain` role already has `retrieve:*` (wildcard matches `retrieve:rag`)
- ✅ `admin` role has `*` (all permissions)
- ❌ `feeder` role should NOT have RAG access
- ❌ `readonly` role should NOT have RAG access
- ❌ `ops` role should NOT have RAG access

**Action Required:** ✅ **NO CHANGES NEEDED** (permissions already correct!)

**Rationale:**
- `retrieve:*` permission (brain role) matches `retrieve:rag` via prefix wildcard
- See [auth.py:519-524](../mcp/auth.py#L519-L524) - `has_permission()` supports prefix matching

---

### Step 2: Add Rate Limit Configuration

**Files:**
- [mcp/rate_limiter.py](../mcp/rate_limiter.py)
- [render.yaml](../render.yaml)
- [mcp/docker-compose.yml](../mcp/docker-compose.yml)

**Changes Required:**

#### 2.1 Update `RateLimitConfig` class

**Location:** [mcp/rate_limiter.py:320-348](../mcp/rate_limiter.py#L320-L348)

**Add:**
```python
class RateLimitConfig:
    """Rate limit configuration from environment variables."""

    def __init__(self):
        self.global_ip = os.getenv("RATE_LIMIT_GLOBAL_IP", "100/minute")
        self.global_key = os.getenv("RATE_LIMIT_GLOBAL_KEY", "200/minute")
        self.publish = os.getenv("RATE_LIMIT_PUBLISH", "60/minute")
        self.retrieve = os.getenv("RATE_LIMIT_RETRIEVE", "30/minute")
        self.status = os.getenv("RATE_LIMIT_STATUS", "120/minute")
        self.metrics = os.getenv("RATE_LIMIT_METRICS", "120/minute")
        self.admin = os.getenv("RATE_LIMIT_ADMIN", "30/minute")
        self.health = os.getenv("RATE_LIMIT_HEALTH", "300/minute")
        # ADD THIS LINE:
        self.rag = os.getenv("RATE_LIMIT_RAG", "30/minute")  # Same as retrieve
```

**Rationale:**
- RAG is similar to retrieve (both read operations)
- Default to 30/minute (same as retrieve)
- Configurable via env var for flexibility

#### 2.2 Update Deployment Configs

**render.yaml:**
```yaml
# Add after RATE_LIMIT_HEALTH
      - key: RATE_LIMIT_RAG
        value: "30/minute"
```

**docker-compose.yml:**
```yaml
# Add after RATE_LIMIT_HEALTH
      - RATE_LIMIT_RAG=${RATE_LIMIT_RAG:-30/minute}
```

---

### Step 3: Harden RAG Endpoint

**File:** [mcp/server.py](../mcp/server.py)

**Current Implementation (lines 761-863):**
```python
@app.post("/tool/search_rag", dependencies=[Depends(verify_api_key)])
async def search_rag(
    request: Request,
    search_request: SearchRAGRequest
):
    # ... implementation ...
```

**Hardened Implementation:**
```python
@app.post("/tool/search_rag", dependencies=[Depends(verify_permission("retrieve:rag"))])
async def search_rag(
    request: Request,
    search_request: SearchRAGRequest,
    key_info: Dict[str, Any] = Depends(verify_permission("retrieve:rag"))
):
    """
    Search RAG knowledge base using external vector database.

    Security:
        - Requires 'retrieve:rag' permission (brain or admin roles only)
        - Rate limited to RATE_LIMIT_RAG (default: 30/minute)
        - Per-IP and per-key global limits also apply

    ...
    """
    # Check if vector engine is initialized
    if vector_engine is None:
        logger.warning("RAG search attempted but vector engine not initialized")
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="RAG search not configured. Set VECTOR_DB_TYPE and VECTOR_DB_URL."
        )

    # ... rest of implementation (unchanged) ...
```

**Changes:**
1. Replace `Depends(verify_api_key)` with `Depends(verify_permission("retrieve:rag"))`
2. Add `key_info` parameter (for audit logging)
3. Update docstring to document security requirements

---

### Step 4: Add Endpoint-Specific Rate Limiting

**Current State:**
- Global rate limiting handled by middleware ([server.py:119-191](../mcp/server.py#L119-L191))
- Per-endpoint limits NOT enforced (all endpoints share global limits)

**Options for Implementation:**

#### Option A: Extend Middleware (Recommended)

Add endpoint-specific checks to rate limit middleware:

```python
@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    """Global rate limiting middleware."""

    # ... existing per-IP and per-key checks ...

    # Add per-endpoint rate limiting
    endpoint_limits = {
        "/tool/publish": rate_limit_config.publish,
        "/tool/retrieve": rate_limit_config.retrieve,
        "/tool/search_rag": rate_limit_config.rag,  # NEW
        "/tool/get_status": rate_limit_config.status,
        "/metrics": rate_limit_config.metrics,
    }

    endpoint = request.url.path
    if endpoint in endpoint_limits:
        # Check endpoint-specific limit
        key = f"endpoint:{endpoint}:{client_ip}"
        allowed, headers = rate_limiter.check_rate_limit(key, endpoint_limits[endpoint])

        if not allowed:
            return JSONResponse(
                status_code=429,
                content={"detail": f"Endpoint rate limit exceeded: {endpoint_limits[endpoint]}"},
                headers=headers
            )

    # ... continue processing ...
```

#### Option B: Decorator Pattern (Alternative)

Create a custom decorator:

```python
def endpoint_rate_limit(limit_attr: str):
    """Decorator for endpoint-specific rate limiting."""
    def decorator(func):
        @wraps(func)
        async def wrapper(request: Request, *args, **kwargs):
            limit = getattr(rate_limit_config, limit_attr)
            # ... rate limit check ...
            return await func(request, *args, **kwargs)
        return wrapper
    return decorator

@app.post("/tool/search_rag")
@endpoint_rate_limit("rag")  # Apply decorator
async def search_rag(...):
    ...
```

**Recommendation:** Use **Option A** (middleware) for consistency with existing architecture.

---

### Step 5: Testing & Validation

Create comprehensive security test suite.

**Test Script:** `mcp/scripts/test_rag_security.sh`

**Test Cases:**

1. **RBAC Tests**
   - ✅ Admin key can access RAG endpoint
   - ✅ Brain key can access RAG endpoint
   - ❌ Feeder key is DENIED (403 Forbidden)
   - ❌ Readonly key is DENIED (403 Forbidden)
   - ❌ Ops key is DENIED (403 Forbidden)
   - ❌ Invalid key is DENIED (401 Unauthorized)

2. **Rate Limit Tests**
   - ✅ 30 requests/minute succeeds
   - ❌ 31st request is DENIED (429 Too Many Requests)
   - ✅ Rate limit resets after 60 seconds
   - ✅ Different API keys have separate limits

3. **Cost Protection Tests**
   - ✅ Limit=100 succeeds (within MAX_RAG_LIMIT)
   - ❌ Limit=1000 is DENIED (400 Bad Request)
   - ✅ Min_score validation (0.0-1.0 range)

4. **Audit Logging Tests**
   - ✅ All RAG requests logged with key_info
   - ✅ Failed auth attempts logged
   - ✅ Rate limit violations logged

---

## Implementation Timeline

| Step | Task | Estimated Time | Priority |
|------|------|----------------|----------|
| 1 | Review permission structure (already correct) | 5 min | ✅ Done |
| 2 | Add RATE_LIMIT_RAG to rate_limiter.py | 10 min | 🔴 Critical |
| 3 | Update render.yaml and docker-compose.yml | 5 min | 🔴 Critical |
| 4 | Harden RAG endpoint with verify_permission | 15 min | 🔴 Critical |
| 5 | Extend rate limit middleware for endpoint-specific limits | 30 min | 🟡 High |
| 6 | Create security test script | 45 min | 🟡 High |
| 7 | Update documentation | 20 min | 🟢 Medium |
| 8 | Deploy and validate | 30 min | 🔴 Critical |

**Total Estimated Time:** ~2.5 hours

---

## Success Criteria

### Must Have (Before Production)

- ✅ `/tool/search_rag` requires `retrieve:rag` permission
- ✅ Feeder/readonly/ops keys are DENIED (403)
- ✅ Rate limit of 30/minute enforced
- ✅ All security tests pass

### Should Have (Best Practice)

- ✅ Endpoint-specific rate limiting in middleware
- ✅ Audit logging includes key_info
- ✅ Documentation updated
- ✅ Integration tests for all roles

### Nice to Have (Future Enhancement)

- 🔮 Cost tracking metrics (requests × $0.0001)
- 🔮 Adaptive rate limiting based on vector DB cost
- 🔮 Alert if RAG spend exceeds threshold

---

## Risk Assessment

### Before Remediation

| Risk | Likelihood | Impact | Severity |
|------|------------|--------|----------|
| Cost bleed from spam | HIGH | HIGH | 🔴 CRITICAL |
| Data exfiltration | MEDIUM | HIGH | 🟡 MAJOR |
| DoS via RAG endpoint | MEDIUM | MEDIUM | 🟡 MAJOR |

### After Remediation

| Risk | Likelihood | Impact | Severity |
|------|------------|--------|----------|
| Cost bleed from spam | LOW | LOW | 🟢 MINOR |
| Data exfiltration | LOW | MEDIUM | 🟢 MINOR |
| DoS via RAG endpoint | LOW | LOW | 🟢 MINOR |

**Risk Reduction:** ~85% reduction in security surface area

---

## Compliance Checklist

### Phase 4 Security Standards

- [ ] **RBAC:** Endpoint uses `verify_permission()` with specific permission
- [ ] **Rate Limiting:** Endpoint has dedicated rate limit configuration
- [ ] **Audit Logging:** All requests logged with authenticated key info
- [ ] **Input Validation:** Request parameters validated (limit, min_score)
- [ ] **Error Handling:** Generic errors (no stack traces in production)
- [ ] **Documentation:** Security requirements documented
- [ ] **Testing:** Security tests for all roles and edge cases

### Current Status

- ❌ RBAC (not enforced)
- ❌ Rate Limiting (no endpoint-specific limit)
- ⚠️ Audit Logging (partial - missing key_info)
- ✅ Input Validation (working)
- ✅ Error Handling (working)
- ⚠️ Documentation (functional but no security details)
- ❌ Testing (no security tests)

**Compliance Score:** 2/7 (29%) → Target: 7/7 (100%)

---

## References

- [Phase 4 Testing Guide](./PHASE4_TESTING_GUIDE.md)
- [Security Audit](./SECURITY.md)
- [Endpoint Security Audit](./ENDPOINT_SECURITY_AUDIT.md)
- [RAG Endpoint Documentation](./RAG_ENDPOINT.md)
- [Auth System](../mcp/auth.py)
- [Rate Limiter](../mcp/rate_limiter.py)

---

**Next Steps:**
1. Review this plan with security team
2. Execute remediation steps 2-8
3. Run security test suite
4. Deploy to staging for validation
5. Deploy to production after sign-off

**Sign-off Required:**
- [ ] Security Team Lead
- [ ] Backend Architect
- [ ] DevOps Engineer

---

**Document Version:** 1.0
**Last Updated:** 2025-12-13
**Status:** 📋 READY FOR IMPLEMENTATION
