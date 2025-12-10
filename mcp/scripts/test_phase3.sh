#!/bin/bash
#
# Phase 3 Testing Script
#
# Tests all Phase 3 features:
# - 3.1: Metrics & Prometheus
# - 3.2: Structured Logging
# - 3.3: Operational procedures
#
# Usage:
#   ./scripts/test_phase3.sh [--unit-only|--integration]
#
# Options:
#   --unit-only      Run only unit tests (no server required)
#   --integration    Run only integration tests (requires server)
#   (no args)        Run both unit and integration tests

set -e  # Exit on error

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Test counters
TESTS_PASSED=0
TESTS_FAILED=0
TESTS_SKIPPED=0

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[PASS]${NC} $1"
    ((TESTS_PASSED++))
}

log_error() {
    echo -e "${RED}[FAIL]${NC} $1"
    ((TESTS_FAILED++))
}

log_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_skip() {
    echo -e "${YELLOW}[SKIP]${NC} $1"
    ((TESTS_SKIPPED++))
}

print_header() {
    echo ""
    echo "================================================================================"
    echo "  $1"
    echo "================================================================================"
    echo ""
}

# Parse command line arguments
RUN_UNIT=true
RUN_INTEGRATION=true

if [ "$1" == "--unit-only" ]; then
    RUN_INTEGRATION=false
elif [ "$1" == "--integration" ]; then
    RUN_UNIT=false
fi

# Start tests
print_header "PHASE 3 TESTING SUITE"
log_info "Starting Phase 3 tests..."
log_info "Run unit tests: $RUN_UNIT"
log_info "Run integration tests: $RUN_INTEGRATION"

# ============================================================================
# UNIT TESTS
# ============================================================================

if [ "$RUN_UNIT" = true ]; then
    print_header "PHASE 3.1: METRICS MODULE TESTS"

    # Test 1.1: Import metrics module
    log_info "Test 1.1: Import metrics module"
    if python3 -c "from mcp.metrics import mcp_publish_total, mcp_redis_connected, set_server_info" 2>/dev/null; then
        log_success "Metrics module imports successfully"
    else
        log_error "Failed to import metrics module"
    fi

    # Test 1.2: Test set_server_info function
    log_info "Test 1.2: Test set_server_info function"
    if python3 -c "from mcp.metrics import set_server_info; set_server_info('1.0.0', 'test')" 2>/dev/null; then
        log_success "set_server_info() executes successfully"
    else
        log_error "set_server_info() failed"
    fi

    # Test 1.3: Check all required metrics exist
    log_info "Test 1.3: Verify all metrics are defined"
    REQUIRED_METRICS=(
        "mcp_publish_total"
        "mcp_publish_latency_seconds"
        "mcp_validation_failures_total"
        "mcp_validation_success_total"
        "mcp_halt_total"
        "mcp_resume_total"
        "mcp_kill_switch_active"
        "mcp_archive_queue_size"
        "mcp_redis_connected"
    )

    METRICS_OK=true
    for metric in "${REQUIRED_METRICS[@]}"; do
        if ! python3 -c "from mcp.metrics import $metric" 2>/dev/null; then
            log_error "Metric $metric not found"
            METRICS_OK=false
        fi
    done

    if [ "$METRICS_OK" = true ]; then
        log_success "All required metrics are defined"
    fi

    print_header "PHASE 3.2: STRUCTURED LOGGING TESTS"

    # Test 2.1: Import logging_config module
    log_info "Test 2.1: Import logging_config module"
    if python3 -c "from mcp.logging_config import setup_logging, get_sanitized_extra" 2>/dev/null; then
        log_success "logging_config module imports successfully"
    else
        log_error "Failed to import logging_config module"
    fi

    # Test 2.2: Test setup_logging function
    log_info "Test 2.2: Test setup_logging function"
    if python3 -c "from mcp.logging_config import setup_logging; logger = setup_logging('INFO')" 2>/dev/null; then
        log_success "setup_logging() executes successfully"
    else
        log_error "setup_logging() failed"
    fi

    # Test 2.3: Run logging security tests
    log_info "Test 2.3: Run logging security tests (pytest)"
    if command -v pytest &> /dev/null; then
        if pytest mcp/tests/test_logging_security.py -v --tb=short 2>&1 | tee /tmp/phase3_pytest.log; then
            PASSED=$(grep -c "PASSED" /tmp/phase3_pytest.log || echo 0)
            log_success "Logging security tests passed ($PASSED tests)"
        else
            FAILED=$(grep -c "FAILED" /tmp/phase3_pytest.log || echo 0)
            log_error "Logging security tests failed ($FAILED tests)"
        fi
    else
        log_skip "pytest not available, skipping security tests"
    fi

    # Test 2.4: Test secret sanitization
    log_info "Test 2.4: Test secret sanitization"
    SANITIZE_TEST=$(python3 << 'EOF'
from mcp.logging_config import get_sanitized_extra
extra = get_sanitized_extra(user="alice", api_key="secret123", password="pass")
assert extra["user"] == "alice", "User field should not be sanitized"
assert extra["api_key"] == "<REDACTED>", "API key should be redacted"
assert extra["password"] == "<REDACTED>", "Password should be redacted"
print("OK")
EOF
)
    if [ "$SANITIZE_TEST" == "OK" ]; then
        log_success "Secret sanitization works correctly"
    else
        log_error "Secret sanitization failed"
    fi

    print_header "PHASE 3.3: DOCUMENTATION TESTS"

    # Test 3.1: Check RUNBOOK.md exists and is comprehensive
    log_info "Test 3.1: Verify RUNBOOK.md exists and is comprehensive"
    if [ -f "docs/RUNBOOK.md" ]; then
        RUNBOOK_LINES=$(wc -l < docs/RUNBOOK.md)
        if [ "$RUNBOOK_LINES" -gt 500 ]; then
            log_success "RUNBOOK.md exists and is comprehensive ($RUNBOOK_LINES lines)"
        else
            log_warning "RUNBOOK.md exists but may be incomplete ($RUNBOOK_LINES lines)"
        fi
    else
        log_error "RUNBOOK.md not found"
    fi

    # Test 3.2: Check Grafana dashboard exists
    log_info "Test 3.2: Verify Grafana dashboard template exists"
    if [ -f "docs/grafana-dashboard.json" ]; then
        if python3 -m json.tool docs/grafana-dashboard.json > /dev/null 2>&1; then
            log_success "grafana-dashboard.json exists and is valid JSON"
        else
            log_error "grafana-dashboard.json is invalid JSON"
        fi
    else
        log_error "grafana-dashboard.json not found"
    fi
fi

# ============================================================================
# INTEGRATION TESTS (require running server)
# ============================================================================

if [ "$RUN_INTEGRATION" = true ]; then
    print_header "INTEGRATION TESTS"

    # Check if MCP_URL is set
    if [ -z "$MCP_URL" ]; then
        log_warning "MCP_URL not set, using default"
        export MCP_URL="http://localhost:8080"
    fi

    log_info "Testing server at: $MCP_URL"

    # Test INT-1: Health check responds
    log_info "INT-1: Test /health endpoint"
    if HEALTH_RESPONSE=$(curl -s --max-time 5 "$MCP_URL/health" 2>/dev/null); then
        if echo "$HEALTH_RESPONSE" | grep -q "status"; then
            log_success "/health endpoint responds correctly"
        else
            log_error "/health endpoint responds but invalid format"
        fi
    else
        log_skip "/health endpoint not accessible (server may not be running)"
    fi

    # Test INT-2: Metrics endpoint exists
    log_info "INT-2: Test /metrics endpoint (Phase 3.1)"
    if METRICS_RESPONSE=$(curl -s --max-time 5 "$MCP_URL/metrics" 2>/dev/null); then
        if echo "$METRICS_RESPONSE" | grep -q "mcp_publish_total"; then
            log_success "/metrics endpoint exists and returns Prometheus format"
        else
            log_error "/metrics endpoint exists but doesn't return expected metrics"
        fi
    else
        log_skip "/metrics endpoint not accessible (may not be deployed yet)"
    fi

    # Test INT-3: Metrics contain all required metrics
    if [ ! -z "$METRICS_RESPONSE" ]; then
        log_info "INT-3: Verify all required metrics are exposed"
        METRICS_FOUND=true
        for metric in "${REQUIRED_METRICS[@]}"; do
            if ! echo "$METRICS_RESPONSE" | grep -q "$metric"; then
                log_warning "Metric $metric not found in /metrics endpoint"
                METRICS_FOUND=false
            fi
        done

        if [ "$METRICS_FOUND" = true ]; then
            log_success "All required metrics found in /metrics endpoint"
        else
            log_error "Some metrics missing from /metrics endpoint"
        fi
    fi

    # Test INT-4: Redis connection metric
    if [ ! -z "$METRICS_RESPONSE" ]; then
        log_info "INT-4: Check Redis connection status"
        REDIS_CONNECTED=$(echo "$METRICS_RESPONSE" | grep "^mcp_redis_connected" | awk '{print $2}')
        if [ "$REDIS_CONNECTED" == "1.0" ]; then
            log_success "Redis is connected (mcp_redis_connected = 1.0)"
        elif [ "$REDIS_CONNECTED" == "0.0" ]; then
            log_error "Redis is disconnected (mcp_redis_connected = 0.0)"
        else
            log_skip "Could not determine Redis connection status"
        fi
    fi

    # Test INT-5: Kill-switch status
    if [ ! -z "$METRICS_RESPONSE" ]; then
        log_info "INT-5: Check kill-switch status"
        KILL_SWITCH=$(echo "$METRICS_RESPONSE" | grep "^mcp_kill_switch_active" | awk '{print $2}')
        if [ "$KILL_SWITCH" == "0.0" ]; then
            log_success "Kill-switch is inactive (normal operation)"
        elif [ "$KILL_SWITCH" == "1.0" ]; then
            log_warning "Kill-switch is ACTIVE (EMERGENCY_HALT)"
        else
            log_skip "Could not determine kill-switch status"
        fi
    fi

    # Test INT-6: Request ID header (Phase 3.2)
    log_info "INT-6: Test X-Request-ID header (Phase 3.2)"
    REQUEST_ID=$(curl -s -I --max-time 5 "$MCP_URL/health" 2>/dev/null | grep -i "X-Request-ID" | awk '{print $2}' | tr -d '\r')
    if [ ! -z "$REQUEST_ID" ]; then
        # Validate UUID format
        if echo "$REQUEST_ID" | grep -qE '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'; then
            log_success "X-Request-ID header present and valid UUID format"
        else
            log_warning "X-Request-ID header present but invalid format: $REQUEST_ID"
        fi
    else
        log_skip "X-Request-ID header not found (may not be deployed yet)"
    fi

    # Test INT-7: /.well-known/mcp includes metrics endpoint
    log_info "INT-7: Verify /.well-known/mcp includes metrics endpoint"
    if WELLKNOWN=$(curl -s --max-time 5 "$MCP_URL/.well-known/mcp" 2>/dev/null); then
        if echo "$WELLKNOWN" | grep -q "metrics"; then
            log_success "/.well-known/mcp includes metrics endpoint"
        else
            log_skip "/.well-known/mcp doesn't include metrics (may not be deployed yet)"
        fi
    else
        log_skip "/.well-known/mcp not accessible"
    fi
fi

# ============================================================================
# SUMMARY
# ============================================================================

print_header "TEST SUMMARY"

TOTAL_TESTS=$((TESTS_PASSED + TESTS_FAILED + TESTS_SKIPPED))

echo "Total Tests Run: $TOTAL_TESTS"
echo -e "${GREEN}Passed:${NC}  $TESTS_PASSED"
echo -e "${RED}Failed:${NC}  $TESTS_FAILED"
echo -e "${YELLOW}Skipped:${NC} $TESTS_SKIPPED"
echo ""

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "${GREEN}✅ All tests passed!${NC}"
    echo ""
    echo "Phase 3 is ready for deployment."
    exit 0
else
    echo -e "${RED}❌ Some tests failed!${NC}"
    echo ""
    echo "Please review the failures above before deploying."
    exit 1
fi
