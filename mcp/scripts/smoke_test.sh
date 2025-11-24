#!/usr/bin/env bash
# smoke_test.sh - Comprehensive MCP Server Smoke Tests
#
# This script runs end-to-end smoke tests against a deployed MCP server.
# Tests cover connectivity, authentication, publishing, archiver, kill-switch,
# and optional features.
#
# Usage:
#   export MCP_URL="https://your-mcp-server.onrender.com"
#   export MCP_API_KEY="your-api-key"
#   ./smoke_test.sh
#
# Exit codes:
#   0 - All critical tests passed
#   1 - One or more critical tests failed
#   2 - Configuration error (missing env vars)

set -e
set -o pipefail

# ============================================================================
# CONFIGURATION
# ============================================================================

# Required environment variables
MCP_URL="${MCP_URL:-}"
MCP_API_KEY="${MCP_API_KEY:-}"

# Optional environment variables
S3_BUCKET="${S3_BUCKET:-}"
AWS_REGION="${AWS_REGION:-us-west-2}"
VERBOSE="${VERBOSE:-false}"
ARCHIVER_WAIT_TIME="${ARCHIVER_WAIT_TIME:-90}"  # seconds to wait for archiver flush

# Colors for output
if [[ -t 1 ]]; then
  RED='\033[0;31m'
  GREEN='\033[0;32m'
  YELLOW='\033[1;33m'
  BLUE='\033[0;34m'
  CYAN='\033[0;36m'
  BOLD='\033[1m'
  NC='\033[0m'
else
  RED=''
  GREEN=''
  YELLOW=''
  BLUE=''
  CYAN=''
  BOLD=''
  NC=''
fi

# Test counters
TESTS_RUN=0
TESTS_PASSED=0
TESTS_FAILED=0
CRITICAL_FAILURES=0

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

log_info() {
  echo -e "${BLUE}[INFO]${NC} $1"
}

log_test() {
  echo ""
  echo -e "${CYAN}[TEST $((TESTS_RUN + 1))]${NC} ${BOLD}$1${NC}"
  ((TESTS_RUN++))
}

log_pass() {
  echo -e "${GREEN}  ✓ PASS${NC} $1"
  ((TESTS_PASSED++))
}

log_fail() {
  echo -e "${RED}  ✗ FAIL${NC} $1"
  ((TESTS_FAILED++))
  if [[ "$2" == "CRITICAL" ]]; then
    ((CRITICAL_FAILURES++))
  fi
}

log_warn() {
  echo -e "${YELLOW}  ⚠ WARN${NC} $1"
}

log_skip() {
  echo -e "${YELLOW}  ⊘ SKIP${NC} $1"
}

check_jq() {
  if ! command -v jq &> /dev/null; then
    log_warn "jq not found. JSON validation will be limited."
    return 1
  fi
  return 0
}

validate_config() {
  log_info "Validating configuration..."

  if [[ -z "$MCP_URL" ]]; then
    echo -e "${RED}ERROR: MCP_URL environment variable not set${NC}"
    echo "Usage: export MCP_URL=\"https://your-mcp-server.onrender.com\""
    return 2
  fi

  if [[ -z "$MCP_API_KEY" ]]; then
    echo -e "${RED}ERROR: MCP_API_KEY environment variable not set${NC}"
    echo "Usage: export MCP_API_KEY=\"your-api-key\""
    return 2
  fi

  log_info "Configuration valid"
  log_info "  MCP_URL: $MCP_URL"
  log_info "  API Key: ${MCP_API_KEY:0:8}..." # Show first 8 chars only
  echo ""

  return 0
}

# ============================================================================
# PHASE 1: CONNECTIVITY & BASIC HEALTH
# ============================================================================

test_health_endpoint() {
  log_test "Health Check (Public Endpoint)"

  local response
  response=$(curl -s -w "\n%{http_code}" "$MCP_URL/health" 2>&1) || {
    log_fail "Failed to connect to $MCP_URL/health" "CRITICAL"
    echo "  Error: $response"
    return 1
  }

  local http_code
  http_code=$(echo "$response" | tail -n1)
  local body
  body=$(echo "$response" | sed '$d')

  if [[ "$http_code" != "200" ]]; then
    log_fail "Expected HTTP 200, got $http_code" "CRITICAL"
    echo "  Response: $body"
    return 1
  fi

  if check_jq; then
    local status
    status=$(echo "$body" | jq -r '.status' 2>/dev/null || echo "")

    if [[ "$status" == "ok" ]]; then
      log_pass "Health endpoint returned 200 with status=ok"
    else
      log_fail "Health endpoint returned 200 but status != 'ok'" "CRITICAL"
      echo "  Response: $body"
      return 1
    fi
  else
    if echo "$body" | grep -q '"status".*"ok"'; then
      log_pass "Health endpoint returned 200 with status=ok"
    else
      log_fail "Health endpoint returned 200 but invalid body"
      echo "  Response: $body"
      return 1
    fi
  fi

  return 0
}

test_discovery_endpoint() {
  log_test "Discovery Endpoint (/.well-known/mcp)"

  local response
  response=$(curl -s -w "\n%{http_code}" "$MCP_URL/.well-known/mcp" 2>&1) || {
    log_fail "Failed to connect to discovery endpoint"
    return 1
  }

  local http_code
  http_code=$(echo "$response" | tail -n1)
  local body
  body=$(echo "$response" | sed '$d')

  if [[ "$http_code" != "200" ]]; then
    log_fail "Expected HTTP 200, got $http_code"
    return 1
  fi

  if check_jq; then
    local name
    name=$(echo "$body" | jq -r '.name' 2>/dev/null || echo "")
    local channel_count
    channel_count=$(echo "$body" | jq '.channels | length' 2>/dev/null || echo "0")

    if [[ "$name" == "MCP Trading Server" ]] && [[ "$channel_count" == "4" ]]; then
      log_pass "Discovery endpoint returned correct metadata (4 channels)"
    else
      log_fail "Discovery endpoint returned unexpected data"
      echo "  Name: $name, Channels: $channel_count"
      return 1
    fi
  else
    log_pass "Discovery endpoint returned HTTP 200"
  fi

  return 0
}

test_list_collections() {
  log_test "List Collections Endpoint"

  local response
  response=$(curl -s -w "\n%{http_code}" "$MCP_URL/tool/list_collections" 2>&1)

  local http_code
  http_code=$(echo "$response" | tail -n1)
  local body
  body=$(echo "$response" | sed '$d')

  if [[ "$http_code" != "200" ]]; then
    log_fail "Expected HTTP 200, got $http_code"
    return 1
  fi

  if check_jq; then
    local total
    total=$(echo "$body" | jq -r '.total' 2>/dev/null || echo "0")

    if [[ "$total" == "4" ]]; then
      log_pass "List collections returned 4 channels"
    else
      log_fail "Expected 4 channels, got $total"
      return 1
    fi
  else
    log_pass "List collections endpoint returned HTTP 200"
  fi

  return 0
}

# ============================================================================
# PHASE 2: AUTHENTICATION
# ============================================================================

test_auth_rejection() {
  log_test "Auth Rejection (Status Without API Key)"

  local response
  response=$(curl -s -w "\n%{http_code}" "$MCP_URL/tool/get_status" 2>&1)

  local http_code
  http_code=$(echo "$response" | tail -n1)

  if [[ "$http_code" == "401" ]]; then
    log_pass "Protected endpoint correctly rejected unauthenticated request (401)"
  elif [[ "$http_code" == "403" ]]; then
    log_pass "Protected endpoint correctly rejected unauthenticated request (403)"
  elif [[ "$http_code" == "200" ]]; then
    log_fail "SECURITY BUG: Protected endpoint returned 200 without authentication!" "CRITICAL"
    echo "  This means MCP_DEV=true or API key check is broken"
    return 1
  else
    log_warn "Unexpected status code: $http_code (expected 401 or 403)"
  fi

  return 0
}

test_auth_success() {
  log_test "Auth Success (Status With API Key)"

  local response
  response=$(curl -s -w "\n%{http_code}" \
    -H "x-api-key: $MCP_API_KEY" \
    "$MCP_URL/tool/get_status" 2>&1)

  local http_code
  http_code=$(echo "$response" | tail -n1)
  local body
  body=$(echo "$response" | sed '$d')

  if [[ "$http_code" != "200" ]]; then
    log_fail "Expected HTTP 200, got $http_code" "CRITICAL"
    echo "  This may indicate invalid API key or server error"
    echo "  Response: $body"
    return 1
  fi

  if check_jq; then
    local redis_connected
    redis_connected=$(echo "$body" | jq -r '.redis_connected' 2>/dev/null || echo "")

    if [[ "$redis_connected" == "true" ]]; then
      log_pass "Status endpoint shows Redis connected"
    else
      log_fail "Redis is not connected (redis_connected: $redis_connected)" "CRITICAL"
      echo "  Full response: $body"
      return 1
    fi

    # Store response for later kill-switch comparison
    export STATUS_BEFORE_KILL="$body"
  else
    log_pass "Status endpoint returned HTTP 200 with authentication"
  fi

  return 0
}

# ============================================================================
# PHASE 3: CORE FUNCTIONALITY
# ============================================================================

test_publish_valid_message() {
  log_test "Publish Valid market:data Message"

  local timestamp
  timestamp=$(date +%s)

  local response
  response=$(curl -s -w "\n%{http_code}" \
    -X POST "$MCP_URL/tool/publish" \
    -H "Content-Type: application/json" \
    -H "x-api-key: $MCP_API_KEY" \
    -d '{
      "channel": "market:data",
      "message": {
        "schema_version": "v1",
        "timestamp": '"$timestamp"',
        "pair": "TEST-SMOKE",
        "price_btc": 123.45,
        "price_eth": 99.99,
        "volume_btc": 1.0
      }
    }' 2>&1)

  local http_code
  http_code=$(echo "$response" | tail -n1)
  local body
  body=$(echo "$response" | sed '$d')

  if [[ "$http_code" != "200" ]]; then
    log_fail "Expected HTTP 200, got $http_code" "CRITICAL"
    echo "  Response: $body"
    return 1
  fi

  if check_jq; then
    local success
    success=$(echo "$body" | jq -r '.success' 2>/dev/null || echo "")

    if [[ "$success" == "true" ]]; then
      log_pass "Message published successfully"
    else
      log_fail "Publish returned 200 but success != true"
      echo "  Response: $body"
      return 1
    fi
  else
    log_pass "Publish endpoint returned HTTP 200"
  fi

  return 0
}

test_publish_invalid_message() {
  log_test "Publish Invalid Message (Schema Validation)"

  local timestamp
  timestamp=$(date +%s)

  local response
  response=$(curl -s -w "\n%{http_code}" \
    -X POST "$MCP_URL/tool/publish" \
    -H "Content-Type: application/json" \
    -H "x-api-key: $MCP_API_KEY" \
    -d '{
      "channel": "market:data",
      "message": {
        "timestamp": '"$timestamp"',
        "pair": "TEST-PAIR"
      }
    }' 2>&1)

  local http_code
  http_code=$(echo "$response" | tail -n1)

  if [[ "$http_code" == "400" ]] || [[ "$http_code" == "422" ]]; then
    log_pass "Invalid message correctly rejected with HTTP $http_code"
  elif [[ "$http_code" == "200" ]]; then
    log_fail "CRITICAL BUG: Invalid message was accepted (HTTP 200)!" "CRITICAL"
    echo "  Schema validation is broken!"
    return 1
  else
    log_warn "Unexpected status code: $http_code (expected 400 or 422)"
  fi

  return 0
}

test_publish_invalid_channel() {
  log_test "Publish to Invalid Channel"

  local timestamp
  timestamp=$(date +%s)

  local response
  response=$(curl -s -w "\n%{http_code}" \
    -X POST "$MCP_URL/tool/publish" \
    -H "Content-Type: application/json" \
    -H "x-api-key: $MCP_API_KEY" \
    -d '{
      "channel": "invalid:channel",
      "message": {
        "schema_version": "v1",
        "timestamp": '"$timestamp"'
      }
    }' 2>&1)

  local http_code
  http_code=$(echo "$response" | tail -n1)

  if [[ "$http_code" == "400" ]]; then
    log_pass "Invalid channel correctly rejected with HTTP 400"
  elif [[ "$http_code" == "200" ]]; then
    log_fail "Invalid channel was accepted (HTTP 200)" "CRITICAL"
    return 1
  else
    log_warn "Unexpected status code: $http_code (expected 400)"
  fi

  return 0
}

# ============================================================================
# PHASE 4: ARCHIVER VALIDATION
# ============================================================================

test_archiver_flush_wait() {
  log_test "Archiver Flush Interval (Waiting ${ARCHIVER_WAIT_TIME}s)"

  log_info "  Waiting for archiver to process messages..."
  log_info "  NOTE: Archiver is currently a STUB (logs only, no actual S3 writes)"

  for ((i=1; i<=ARCHIVER_WAIT_TIME; i++)); do
    if ((i % 10 == 0)); then
      echo -n "."
    fi
    sleep 1
  done
  echo ""

  log_pass "Wait period completed"
  log_info "  Next: Check worker logs via Render CLI if available"

  return 0
}

# ============================================================================
# PHASE 5: KILL-SWITCH LOGIC
# ============================================================================

test_kill_switch_activation() {
  log_test "Kill-Switch Activation (EMERGENCY_HALT)"

  local timestamp
  timestamp=$(date +%s)

  local response
  response=$(curl -s -w "\n%{http_code}" \
    -X POST "$MCP_URL/tool/publish" \
    -H "Content-Type: application/json" \
    -H "x-api-key: $MCP_API_KEY" \
    -d '{
      "channel": "agent:control",
      "message": {
        "schema_version": "v1",
        "timestamp": '"$timestamp"',
        "command": "EMERGENCY_HALT",
        "reason": "SMOKE_TEST"
      }
    }' 2>&1)

  local http_code
  http_code=$(echo "$response" | tail -n1)

  if [[ "$http_code" != "200" ]]; then
    log_fail "Failed to publish EMERGENCY_HALT (HTTP $http_code)"
    return 1
  fi

  log_pass "EMERGENCY_HALT published successfully"

  # Wait a moment for Redis persistence
  sleep 2

  return 0
}

test_kill_switch_verification() {
  log_test "Kill-Switch Verification (Check Status)"

  local response
  response=$(curl -s \
    -H "x-api-key: $MCP_API_KEY" \
    "$MCP_URL/tool/get_status" 2>&1)

  if check_jq; then
    local status
    status=$(echo "$response" | jq -r '.status' 2>/dev/null || echo "")
    local kill_active
    kill_active=$(echo "$response" | jq -r '.kill_switch.active' 2>/dev/null || echo "")

    if [[ "$status" == "EMERGENCY_HALT" ]] && [[ "$kill_active" == "true" ]]; then
      log_pass "Kill-switch successfully activated and persisted to Redis"
    else
      log_fail "Kill-switch not activated (status: $status, active: $kill_active)"
      echo "  Response: $response"
      return 1
    fi
  else
    if echo "$response" | grep -q '"EMERGENCY_HALT"'; then
      log_pass "Kill-switch appears to be activated"
    else
      log_fail "Kill-switch verification failed"
      return 1
    fi
  fi

  return 0
}

test_kill_switch_clear() {
  log_test "Kill-Switch Clear (RESUME)"

  local timestamp
  timestamp=$(date +%s)

  local response
  response=$(curl -s -w "\n%{http_code}" \
    -X POST "$MCP_URL/tool/publish" \
    -H "Content-Type: application/json" \
    -H "x-api-key: $MCP_API_KEY" \
    -d '{
      "channel": "agent:control",
      "message": {
        "schema_version": "v1",
        "timestamp": '"$timestamp"',
        "command": "RESUME",
        "reason": "Smoke test complete"
      }
    }' 2>&1)

  local http_code
  http_code=$(echo "$response" | tail -n1)

  if [[ "$http_code" != "200" ]]; then
    log_fail "Failed to publish RESUME (HTTP $http_code)"
    return 1
  fi

  # Wait for persistence
  sleep 2

  # Verify cleared
  response=$(curl -s \
    -H "x-api-key: $MCP_API_KEY" \
    "$MCP_URL/tool/get_status" 2>&1)

  if check_jq; then
    local kill_active
    kill_active=$(echo "$response" | jq -r '.kill_switch.active' 2>/dev/null || echo "")

    if [[ "$kill_active" == "false" ]]; then
      log_pass "Kill-switch successfully cleared"
    else
      log_fail "Kill-switch still active after RESUME"
      return 1
    fi
  else
    log_pass "RESUME command published"
  fi

  return 0
}

# ============================================================================
# PHASE 6: OPTIONAL FEATURES
# ============================================================================

test_retrieval_endpoint() {
  log_test "Historical Data Retrieval (Optional)"

  local timestamp
  timestamp=$(date +%s)
  local from_ts=$((timestamp - 3600))

  local response
  response=$(curl -s -w "\n%{http_code}" \
    -X POST "$MCP_URL/tool/retrieve" \
    -H "Content-Type: application/json" \
    -H "x-api-key: $MCP_API_KEY" \
    -d '{
      "collection": "market:data",
      "limit": 10
    }' 2>&1)

  local http_code
  http_code=$(echo "$response" | tail -n1)

  if [[ "$http_code" == "501" ]]; then
    log_pass "Retrieval endpoint correctly returns 501 (S3 not configured)"
  elif [[ "$http_code" == "200" ]]; then
    log_pass "Retrieval endpoint working (S3 configured)"
  else
    log_warn "Unexpected status code: $http_code (expected 501 or 200)"
  fi

  return 0
}

test_rag_placeholder() {
  log_test "RAG Search Placeholder"

  local response
  response=$(curl -s -w "\n%{http_code}" \
    -X POST "$MCP_URL/tool/search_rag" \
    -H "Content-Type: application/json" \
    -H "x-api-key: $MCP_API_KEY" \
    -d '{"query": "test", "k": 5}' 2>&1)

  local http_code
  http_code=$(echo "$response" | tail -n1)

  if [[ "$http_code" == "501" ]]; then
    log_pass "RAG endpoint correctly returns 501 (not implemented)"
  elif [[ "$http_code" == "200" ]]; then
    log_pass "RAG endpoint is configured and working"
  else
    log_warn "Unexpected status code: $http_code"
  fi

  return 0
}

# ============================================================================
# MAIN EXECUTION
# ============================================================================

main() {
  echo ""
  echo -e "${BOLD}========================================${NC}"
  echo -e "${BOLD}  MCP Server - Comprehensive Smoke Tests${NC}"
  echo -e "${BOLD}========================================${NC}"
  echo ""

  # Validate configuration
  validate_config || exit $?

  # Check prerequisites
  check_jq || log_warn "Install jq for better JSON validation"

  # Phase 1: Connectivity
  echo -e "${BOLD}=== PHASE 1: CONNECTIVITY & BASIC HEALTH ===${NC}"
  test_health_endpoint || true
  test_discovery_endpoint || true
  test_list_collections || true

  # Phase 2: Authentication
  echo ""
  echo -e "${BOLD}=== PHASE 2: AUTHENTICATION ===${NC}"
  test_auth_rejection || true
  test_auth_success || true

  # Phase 3: Core Functionality
  echo ""
  echo -e "${BOLD}=== PHASE 3: CORE FUNCTIONALITY ===${NC}"
  test_publish_valid_message || true
  test_publish_invalid_message || true
  test_publish_invalid_channel || true

  # Phase 4: Archiver
  echo ""
  echo -e "${BOLD}=== PHASE 4: ARCHIVER VALIDATION ===${NC}"
  test_archiver_flush_wait || true

  # Phase 5: Kill-Switch
  echo ""
  echo -e "${BOLD}=== PHASE 5: KILL-SWITCH LOGIC ===${NC}"
  test_kill_switch_activation || true
  test_kill_switch_verification || true
  test_kill_switch_clear || true

  # Phase 6: Optional Features
  echo ""
  echo -e "${BOLD}=== PHASE 6: OPTIONAL FEATURES ===${NC}"
  test_retrieval_endpoint || true
  test_rag_placeholder || true

  # Summary
  echo ""
  echo -e "${BOLD}========================================${NC}"
  echo -e "${BOLD}  TEST SUMMARY${NC}"
  echo -e "${BOLD}========================================${NC}"
  echo -e "  Total Tests:    $TESTS_RUN"
  echo -e "  ${GREEN}Passed:         $TESTS_PASSED${NC}"

  if [[ $TESTS_FAILED -gt 0 ]]; then
    echo -e "  ${RED}Failed:         $TESTS_FAILED${NC}"
  else
    echo -e "  Failed:         $TESTS_FAILED"
  fi

  if [[ $CRITICAL_FAILURES -gt 0 ]]; then
    echo -e "  ${RED}Critical:       $CRITICAL_FAILURES${NC}"
  fi

  echo ""

  # Exit code
  if [[ $CRITICAL_FAILURES -gt 0 ]]; then
    echo -e "${RED}❌ CRITICAL FAILURES DETECTED${NC}"
    echo -e "   Review the failed tests above and check:"
    echo -e "   - Render service logs (web + worker)"
    echo -e "   - Redis connectivity"
    echo -e "   - Environment variables"
    exit 1
  elif [[ $TESTS_FAILED -gt 0 ]]; then
    echo -e "${YELLOW}⚠️  SOME TESTS FAILED${NC}"
    echo -e "   Optional features may not be configured"
    exit 0  # Non-critical failures don't fail the suite
  else
    echo -e "${GREEN}✅ ALL TESTS PASSED${NC}"
    exit 0
  fi
}

# Run main function
main "$@"
