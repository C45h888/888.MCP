#!/bin/bash
#
# Phase 1.3 Kill-Switch Smoke Test
#
# Tests kill-switch and control channel reliability against a running MCP server.
# Covers Task 1.3 requirements:
#   1.3.1: Rapid EMERGENCY_HALT sequence
#   1.3.2: Kill history ordering and retrieval
#   1.3.3: Persistence (requires manual restart)
#
# Usage:
#   export MCP_URL="https://your-mcp-server.com"
#   export MCP_API_KEY="your-api-key"
#   ./scripts/test_kill_switch.sh
#
# Exit codes:
#   0 - All tests passed
#   1 - One or more tests failed
#   2 - Configuration error (missing URL or API key)

set -e  # Exit on error
set -u  # Exit on undefined variable

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Counters
TESTS_RUN=0
TESTS_PASSED=0
TESTS_FAILED=0

# Configuration
MCP_URL="${MCP_URL:-}"
MCP_API_KEY="${MCP_API_KEY:-}"

# Check configuration
if [ -z "$MCP_URL" ]; then
    echo -e "${RED}ERROR: MCP_URL not set${NC}"
    echo "Usage: export MCP_URL=\"https://your-mcp-server.com\""
    exit 2
fi

if [ -z "$MCP_API_KEY" ]; then
    echo -e "${RED}ERROR: MCP_API_KEY not set${NC}"
    echo "Usage: export MCP_API_KEY=\"your-api-key\""
    exit 2
fi

# Helper functions
function log_test() {
    echo -e "${BLUE}[TEST $TESTS_RUN]${NC} $1"
}

function log_pass() {
    echo -e "${GREEN}✓ PASS${NC} $1"
    ((TESTS_PASSED++))
}

function log_fail() {
    echo -e "${RED}✗ FAIL${NC} $1"
    ((TESTS_FAILED++))
}

function log_info() {
    echo -e "${YELLOW}ℹ INFO${NC} $1"
}

function get_timestamp() {
    date +%s
}

# Test functions

function test_1_clear_kill_switch() {
    ((TESTS_RUN++))
    log_test "Clear kill switch (prepare for tests)"

    local timestamp=$(get_timestamp)
    local response=$(curl -s -X POST "$MCP_URL/tool/publish" \
        -H "x-api-key: $MCP_API_KEY" \
        -H "Content-Type: application/json" \
        -d "{
            \"channel\": \"agent:control\",
            \"message\": {
                \"schema_version\": \"v1\",
                \"timestamp\": $timestamp,
                \"command\": \"RESUME\",
                \"reason\": \"SMOKE_TEST_INIT\"
            }
        }")

    if echo "$response" | jq -e '.success == true' > /dev/null 2>&1; then
        log_pass "Kill switch cleared"
    else
        log_fail "Failed to clear kill switch: $response"
        return 1
    fi
}

function test_2_rapid_emergency_halt() {
    ((TESTS_RUN++))
    log_test "Rapid EMERGENCY_HALT sequence (5 commands)"

    local base_timestamp=$(get_timestamp)
    local success_count=0

    # Send 5 rapid EMERGENCY_HALT commands
    for i in {1..5}; do
        local timestamp=$((base_timestamp + i))
        local response=$(curl -s -X POST "$MCP_URL/tool/publish" \
            -H "x-api-key: $MCP_API_KEY" \
            -H "Content-Type: application/json" \
            -d "{
                \"channel\": \"agent:control\",
                \"message\": {
                    \"schema_version\": \"v1\",
                    \"timestamp\": $timestamp,
                    \"command\": \"EMERGENCY_HALT\",
                    \"reason\": \"SMOKE_TEST_RAPID_$i\"
                }
            }")

        if echo "$response" | jq -e '.success == true' > /dev/null 2>&1; then
            ((success_count++))
        fi
    done

    if [ $success_count -eq 5 ]; then
        log_pass "All 5 EMERGENCY_HALT commands accepted"
    else
        log_fail "Only $success_count/5 commands succeeded"
        return 1
    fi

    # Give server time to process
    sleep 1

    # Verify kill switch is active
    local status=$(curl -s -H "x-api-key: $MCP_API_KEY" "$MCP_URL/tool/get_status")
    local active=$(echo "$status" | jq -r '.kill_switch.active')

    if [ "$active" = "true" ]; then
        log_pass "Kill switch is active after rapid sequence"
    else
        log_fail "Kill switch not active: $active"
        return 1
    fi
}

function test_3_kill_history_count() {
    ((TESTS_RUN++))
    log_test "Verify kill history contains all events"

    local history=$(curl -s -H "x-api-key: $MCP_API_KEY" "$MCP_URL/tool/kill_history")
    local count=$(echo "$history" | jq -r '.count')

    # Should have at least 5 EMERGENCY_HALT + 1 RESUME from test_1
    if [ "$count" -ge 5 ]; then
        log_pass "Kill history contains $count events (expected >= 5)"
    else
        log_fail "Kill history only contains $count events (expected >= 5)"
        return 1
    fi
}

function test_4_kill_history_ordering() {
    ((TESTS_RUN++))
    log_test "Verify kill history ordering (most recent first)"

    local history=$(curl -s -H "x-api-key: $MCP_API_KEY" "$MCP_URL/tool/kill_history")

    # Get first two events
    local first_timestamp=$(echo "$history" | jq -r '.events[0].timestamp')
    local second_timestamp=$(echo "$history" | jq -r '.events[1].timestamp')

    if [ "$first_timestamp" -ge "$second_timestamp" ]; then
        log_pass "Events ordered correctly (most recent first)"
    else
        log_fail "Events not ordered correctly: first=$first_timestamp, second=$second_timestamp"
        return 1
    fi
}

function test_5_kill_history_limit() {
    ((TESTS_RUN++))
    log_test "Verify kill history limit parameter"

    local history=$(curl -s -H "x-api-key: $MCP_API_KEY" "$MCP_URL/tool/kill_history?limit=3")
    local count=$(echo "$history" | jq -r '.count')

    if [ "$count" -le 3 ]; then
        log_pass "Kill history respects limit parameter (count=$count, limit=3)"
    else
        log_fail "Kill history exceeded limit: count=$count (expected <= 3)"
        return 1
    fi
}

function test_6_kill_history_current_status() {
    ((TESTS_RUN++))
    log_test "Verify kill history includes current status"

    local history=$(curl -s -H "x-api-key: $MCP_API_KEY" "$MCP_URL/tool/kill_history")

    # Check that current_status field exists
    local current_active=$(echo "$history" | jq -r '.current_status.active')

    if [ "$current_active" = "true" ] || [ "$current_active" = "false" ]; then
        log_pass "Kill history includes current_status (active=$current_active)"
    else
        log_fail "Kill history missing current_status: $current_active"
        return 1
    fi
}

function test_7_resume_clears_kill_switch() {
    ((TESTS_RUN++))
    log_test "Verify RESUME clears kill switch"

    local timestamp=$(get_timestamp)
    local response=$(curl -s -X POST "$MCP_URL/tool/publish" \
        -H "x-api-key: $MCP_API_KEY" \
        -H "Content-Type: application/json" \
        -d "{
            \"channel\": \"agent:control\",
            \"message\": {
                \"schema_version\": \"v1\",
                \"timestamp\": $timestamp,
                \"command\": \"RESUME\",
                \"reason\": \"SMOKE_TEST_CLEAR\"
            }
        }")

    if ! echo "$response" | jq -e '.success == true' > /dev/null 2>&1; then
        log_fail "Failed to publish RESUME: $response"
        return 1
    fi

    sleep 1

    # Verify kill switch is inactive
    local status=$(curl -s -H "x-api-key: $MCP_API_KEY" "$MCP_URL/tool/get_status")
    local active=$(echo "$status" | jq -r '.kill_switch.active')

    if [ "$active" = "false" ]; then
        log_pass "Kill switch cleared after RESUME"
    else
        log_fail "Kill switch still active: $active"
        return 1
    fi
}

function test_8_history_survives_clear() {
    ((TESTS_RUN++))
    log_test "Verify history survives kill switch clear"

    local history=$(curl -s -H "x-api-key: $MCP_API_KEY" "$MCP_URL/tool/kill_history")
    local count=$(echo "$history" | jq -r '.count')

    # Should still have history even though kill switch is cleared
    if [ "$count" -ge 6 ]; then
        log_pass "Kill history persists after RESUME (count=$count)"
    else
        log_fail "Kill history incomplete after RESUME: count=$count (expected >= 6)"
        return 1
    fi
}

# Main execution
function main() {
    echo "======================================"
    echo "  Phase 1.3 Kill-Switch Smoke Test"
    echo "======================================"
    echo ""
    echo "Target: $MCP_URL"
    echo "API Key: ${MCP_API_KEY:0:8}..."
    echo ""

    # Run tests
    test_1_clear_kill_switch || true
    test_2_rapid_emergency_halt || true
    test_3_kill_history_count || true
    test_4_kill_history_ordering || true
    test_5_kill_history_limit || true
    test_6_kill_history_current_status || true
    test_7_resume_clears_kill_switch || true
    test_8_history_survives_clear || true

    # Summary
    echo ""
    echo "======================================"
    echo "  Test Summary"
    echo "======================================"
    echo -e "Total:  $TESTS_RUN"
    echo -e "${GREEN}Passed: $TESTS_PASSED${NC}"
    echo -e "${RED}Failed: $TESTS_FAILED${NC}"
    echo ""

    if [ $TESTS_FAILED -eq 0 ]; then
        echo -e "${GREEN}✓ ALL TESTS PASSED${NC}"
        echo ""
        log_info "Manual verification still required for Task 1.3.3 (restart persistence)"
        log_info "See: tests/integration/test_phase_1_3.py::TestTask1_3_RestartVerification"
        exit 0
    else
        echo -e "${RED}✗ SOME TESTS FAILED${NC}"
        exit 1
    fi
}

# Run main
main
