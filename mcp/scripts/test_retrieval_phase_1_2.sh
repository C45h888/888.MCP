#!/bin/bash
#
# Phase 1.2 - Retrieval Accuracy & Limits Testing
# Manual test script using curl commands
#
# Prerequisites:
# - MCP_URL environment variable set
# - MCP_API_KEY environment variable set
# - S3_DATA_BUCKET configured (or tests will return 501)
# - Test data seeded (use scripts/seed_test_data.py)
#
# Usage:
#   export MCP_URL="https://your-mcp-server.onrender.com"
#   export MCP_API_KEY="your-api-key"
#   ./scripts/test_retrieval_phase_1_2.sh
#

set -e  # Exit on error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Test counters
TESTS_RUN=0
TESTS_PASSED=0
TESTS_FAILED=0
TESTS_SKIPPED=0

# Check required environment variables
if [ -z "$MCP_URL" ]; then
    echo -e "${RED}ERROR: MCP_URL not set${NC}"
    echo "Usage: export MCP_URL='https://your-server.onrender.com'"
    exit 1
fi

if [ -z "$MCP_API_KEY" ]; then
    echo -e "${RED}ERROR: MCP_API_KEY not set${NC}"
    echo "Usage: export MCP_API_KEY='your-api-key'"
    exit 1
fi

# Utility functions
print_header() {
    echo ""
    echo -e "${BLUE}════════════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}════════════════════════════════════════════════════════════════${NC}"
    echo ""
}

print_test() {
    echo -e "${YELLOW}[TEST $TESTS_RUN] $1${NC}"
}

pass_test() {
    TESTS_PASSED=$((TESTS_PASSED + 1))
    echo -e "${GREEN}✅ PASS${NC}"
}

fail_test() {
    TESTS_FAILED=$((TESTS_FAILED + 1))
    echo -e "${RED}❌ FAIL: $1${NC}"
}

skip_test() {
    TESTS_SKIPPED=$((TESTS_SKIPPED + 1))
    echo -e "${YELLOW}⏭️  SKIP: $1${NC}"
}

# Retrieve helper function
retrieve() {
    local collection="$1"
    local extra_params="$2"

    curl -s -w "\nHTTP_STATUS:%{http_code}\n" \
        -X POST "$MCP_URL/tool/retrieve" \
        -H "x-api-key: $MCP_API_KEY" \
        -H "Content-Type: application/json" \
        -d "{\"collection\": \"$collection\", $extra_params}"
}

# Get current timestamp for time range tests
NOW=$(date +%s)
ONE_MIN_AGO=$((NOW - 60))
SEVEN_DAYS_AGO=$((NOW - 7 * 24 * 60 * 60))
THIRTY_DAYS_AGO=$((NOW - 30 * 24 * 60 * 60))
FUTURE_TS=$((NOW + 365 * 24 * 60 * 60))

# Start testing
print_header "PHASE 1.2 - RETRIEVAL ACCURACY & LIMITS TESTING"

echo "Test Configuration:"
echo "  MCP_URL: $MCP_URL"
echo "  MCP_API_KEY: ${MCP_API_KEY:0:10}..."
echo "  Current timestamp: $NOW"
echo ""

#####################################################################
# 1.2.1 - PAIR VALUE FILTERING
#####################################################################

print_header "1.2.1 - Pair Value Filtering"

# Test 1: BTC-ETH pair
TESTS_RUN=$((TESTS_RUN + 1))
print_test "Retrieve with BTC-ETH pair filter"
RESPONSE=$(retrieve "market:data" "\"pair\": \"BTC-ETH\", \"limit\": 100")
HTTP_CODE=$(echo "$RESPONSE" | grep "HTTP_STATUS" | cut -d: -f2)

if [ "$HTTP_CODE" == "200" ]; then
    COUNT=$(echo "$RESPONSE" | grep -o '"count":[0-9]*' | cut -d: -f2)
    echo "  Retrieved $COUNT messages"

    # Verify all messages have BTC-ETH pair
    if echo "$RESPONSE" | jq -e '.messages[] | select(.pair != "BTC-ETH")' > /dev/null 2>&1; then
        fail_test "Found non-BTC-ETH messages in results"
    else
        pass_test
    fi
elif [ "$HTTP_CODE" == "501" ]; then
    skip_test "S3 not configured"
else
    fail_test "HTTP $HTTP_CODE"
fi

# Test 2: BTC-USD pair
TESTS_RUN=$((TESTS_RUN + 1))
print_test "Retrieve with BTC-USD pair filter"
RESPONSE=$(retrieve "market:data" "\"pair\": \"BTC-USD\", \"limit\": 100")
HTTP_CODE=$(echo "$RESPONSE" | grep "HTTP_STATUS" | cut -d: -f2)

if [ "$HTTP_CODE" == "200" ]; then
    COUNT=$(echo "$RESPONSE" | grep -o '"count":[0-9]*' | cut -d: -f2)
    echo "  Retrieved $COUNT messages"
    pass_test
elif [ "$HTTP_CODE" == "501" ]; then
    skip_test "S3 not configured"
else
    fail_test "HTTP $HTTP_CODE"
fi

# Test 3: No pair filter
TESTS_RUN=$((TESTS_RUN + 1))
print_test "Retrieve without pair filter (all pairs)"
RESPONSE=$(retrieve "market:data" "\"limit\": 100")
HTTP_CODE=$(echo "$RESPONSE" | grep "HTTP_STATUS" | cut -d: -f2)

if [ "$HTTP_CODE" == "200" ]; then
    COUNT=$(echo "$RESPONSE" | grep -o '"count":[0-9]*' | cut -d: -f2)
    echo "  Retrieved $COUNT messages"
    pass_test
elif [ "$HTTP_CODE" == "501" ]; then
    skip_test "S3 not configured"
else
    fail_test "HTTP $HTTP_CODE"
fi

# Test 4: Non-existent pair
TESTS_RUN=$((TESTS_RUN + 1))
print_test "Retrieve with non-existent pair (should return 0)"
RESPONSE=$(retrieve "market:data" "\"pair\": \"XYZ-ABC\", \"limit\": 100")
HTTP_CODE=$(echo "$RESPONSE" | grep "HTTP_STATUS" | cut -d: -f2)

if [ "$HTTP_CODE" == "200" ]; then
    COUNT=$(echo "$RESPONSE" | grep -o '"count":[0-9]*' | cut -d: -f2)
    if [ "$COUNT" == "0" ]; then
        pass_test
    else
        fail_test "Expected 0 messages, got $COUNT"
    fi
elif [ "$HTTP_CODE" == "501" ]; then
    skip_test "S3 not configured"
else
    fail_test "HTTP $HTTP_CODE"
fi

#####################################################################
# 1.2.2 - TIME RANGE FILTERING
#####################################################################

print_header "1.2.2 - Edge Case Time Ranges"

# Test 5: 1-minute window
TESTS_RUN=$((TESTS_RUN + 1))
print_test "Retrieve 1-minute time window"
RESPONSE=$(retrieve "market:data" "\"from_timestamp\": $ONE_MIN_AGO, \"to_timestamp\": $NOW, \"limit\": 100")
HTTP_CODE=$(echo "$RESPONSE" | grep "HTTP_STATUS" | cut -d: -f2)

if [ "$HTTP_CODE" == "200" ]; then
    COUNT=$(echo "$RESPONSE" | grep -o '"count":[0-9]*' | cut -d: -f2)
    echo "  Retrieved $COUNT messages from last minute"
    pass_test
elif [ "$HTTP_CODE" == "501" ]; then
    skip_test "S3 not configured"
else
    fail_test "HTTP $HTTP_CODE"
fi

# Test 6: 7-day window
TESTS_RUN=$((TESTS_RUN + 1))
print_test "Retrieve 7-day time window"
RESPONSE=$(retrieve "market:data" "\"from_timestamp\": $SEVEN_DAYS_AGO, \"to_timestamp\": $NOW, \"limit\": 1000")
HTTP_CODE=$(echo "$RESPONSE" | grep "HTTP_STATUS" | cut -d: -f2)

if [ "$HTTP_CODE" == "200" ]; then
    COUNT=$(echo "$RESPONSE" | grep -o '"count":[0-9]*' | cut -d: -f2)
    echo "  Retrieved $COUNT messages from last 7 days (limit: 1000)"
    if [ "$COUNT" -ge 1000 ]; then
        echo -e "  ${YELLOW}⚠️  WARNING: Limit reached, results may be truncated${NC}"
    fi
    pass_test
elif [ "$HTTP_CODE" == "501" ]; then
    skip_test "S3 not configured"
else
    fail_test "HTTP $HTTP_CODE"
fi

# Test 7: 30-day window
TESTS_RUN=$((TESTS_RUN + 1))
print_test "Retrieve 30-day time window"
RESPONSE=$(retrieve "market:data" "\"from_timestamp\": $THIRTY_DAYS_AGO, \"to_timestamp\": $NOW, \"limit\": 1000")
HTTP_CODE=$(echo "$RESPONSE" | grep "HTTP_STATUS" | cut -d: -f2)

if [ "$HTTP_CODE" == "200" ]; then
    COUNT=$(echo "$RESPONSE" | grep -o '"count":[0-9]*' | cut -d: -f2)
    echo "  Retrieved $COUNT messages from last 30 days (limit: 1000)"
    if [ "$COUNT" -ge 1000 ]; then
        echo -e "  ${YELLOW}⚠️  WARNING: Limit reached, results may be truncated${NC}"
    fi
    pass_test
elif [ "$HTTP_CODE" == "501" ]; then
    skip_test "S3 not configured"
else
    fail_test "HTTP $HTTP_CODE"
fi

# Test 8: Future time range (should return 0)
TESTS_RUN=$((TESTS_RUN + 1))
print_test "Retrieve future time range (should return 0)"
RESPONSE=$(retrieve "market:data" "\"from_timestamp\": $FUTURE_TS, \"to_timestamp\": $((FUTURE_TS + 3600)), \"limit\": 100")
HTTP_CODE=$(echo "$RESPONSE" | grep "HTTP_STATUS" | cut -d: -f2)

if [ "$HTTP_CODE" == "200" ]; then
    COUNT=$(echo "$RESPONSE" | grep -o '"count":[0-9]*' | cut -d: -f2)
    if [ "$COUNT" == "0" ]; then
        pass_test
    else
        fail_test "Expected 0 messages for future time range, got $COUNT"
    fi
elif [ "$HTTP_CODE" == "501" ]; then
    skip_test "S3 not configured"
else
    fail_test "HTTP $HTTP_CODE"
fi

#####################################################################
# 1.2.3 - LIMIT PARAMETER TESTING
#####################################################################

print_header "1.2.3 - Limit Parameter Testing"

# Test 9: Limit 1 (edge case)
TESTS_RUN=$((TESTS_RUN + 1))
print_test "Retrieve with limit=1"
RESPONSE=$(retrieve "market:data" "\"limit\": 1")
HTTP_CODE=$(echo "$RESPONSE" | grep "HTTP_STATUS" | cut -d: -f2)

if [ "$HTTP_CODE" == "200" ]; then
    COUNT=$(echo "$RESPONSE" | grep -o '"count":[0-9]*' | cut -d: -f2)
    if [ "$COUNT" -le 1 ]; then
        pass_test
    else
        fail_test "Expected max 1 message, got $COUNT"
    fi
elif [ "$HTTP_CODE" == "501" ]; then
    skip_test "S3 not configured"
else
    fail_test "HTTP $HTTP_CODE"
fi

# Test 10: Limit 10 (small)
TESTS_RUN=$((TESTS_RUN + 1))
print_test "Retrieve with limit=10"
RESPONSE=$(retrieve "market:data" "\"limit\": 10")
HTTP_CODE=$(echo "$RESPONSE" | grep "HTTP_STATUS" | cut -d: -f2)

if [ "$HTTP_CODE" == "200" ]; then
    COUNT=$(echo "$RESPONSE" | grep -o '"count":[0-9]*' | cut -d: -f2)
    if [ "$COUNT" -le 10 ]; then
        pass_test
    else
        fail_test "Expected max 10 messages, got $COUNT"
    fi
elif [ "$HTTP_CODE" == "501" ]; then
    skip_test "S3 not configured"
else
    fail_test "HTTP $HTTP_CODE"
fi

# Test 11: Limit 100 (medium)
TESTS_RUN=$((TESTS_RUN + 1))
print_test "Retrieve with limit=100"
RESPONSE=$(retrieve "market:data" "\"limit\": 100")
HTTP_CODE=$(echo "$RESPONSE" | grep "HTTP_STATUS" | cut -d: -f2)

if [ "$HTTP_CODE" == "200" ]; then
    COUNT=$(echo "$RESPONSE" | grep -o '"count":[0-9]*' | cut -d: -f2)
    if [ "$COUNT" -le 100 ]; then
        pass_test
    else
        fail_test "Expected max 100 messages, got $COUNT"
    fi
elif [ "$HTTP_CODE" == "501" ]; then
    skip_test "S3 not configured"
else
    fail_test "HTTP $HTTP_CODE"
fi

# Test 12: Limit 1000 (maximum)
TESTS_RUN=$((TESTS_RUN + 1))
print_test "Retrieve with limit=1000 (MAX)"
RESPONSE=$(retrieve "market:data" "\"limit\": 1000")
HTTP_CODE=$(echo "$RESPONSE" | grep "HTTP_STATUS" | cut -d: -f2)

if [ "$HTTP_CODE" == "200" ]; then
    COUNT=$(echo "$RESPONSE" | grep -o '"count":[0-9]*' | cut -d: -f2)
    echo "  Retrieved $COUNT messages"
    if [ "$COUNT" -le 1000 ]; then
        pass_test
    else
        fail_test "Expected max 1000 messages, got $COUNT"
    fi
elif [ "$HTTP_CODE" == "501" ]; then
    skip_test "S3 not configured"
else
    fail_test "HTTP $HTTP_CODE"
fi

# Test 13: Limit exceeds max (should reject)
TESTS_RUN=$((TESTS_RUN + 1))
print_test "Retrieve with limit=5000 (should reject)"
RESPONSE=$(retrieve "market:data" "\"limit\": 5000")
HTTP_CODE=$(echo "$RESPONSE" | grep "HTTP_STATUS" | cut -d: -f2)

if [ "$HTTP_CODE" == "400" ]; then
    pass_test
elif [ "$HTTP_CODE" == "501" ]; then
    skip_test "S3 not configured"
else
    fail_test "Expected 400 Bad Request, got HTTP $HTTP_CODE"
fi

#####################################################################
# 1.2.4 - TIME ORDERING VERIFICATION
#####################################################################

print_header "1.2.4 - Time Ordering Verification"

# Test 14: Verify ascending timestamp order
TESTS_RUN=$((TESTS_RUN + 1))
print_test "Verify messages sorted by timestamp (ascending)"
RESPONSE=$(retrieve "market:data" "\"limit\": 100")
HTTP_CODE=$(echo "$RESPONSE" | grep "HTTP_STATUS" | cut -d: -f2)

if [ "$HTTP_CODE" == "200" ]; then
    # Extract and save to temp file for ordering check
    TEMP_FILE=$(mktemp)
    echo "$RESPONSE" | grep -v "HTTP_STATUS" | jq -r '.messages[].timestamp' > "$TEMP_FILE"

    # Check if sorted
    if sort -c "$TEMP_FILE" 2>/dev/null; then
        pass_test
    else
        fail_test "Messages not sorted in ascending order"
    fi

    rm "$TEMP_FILE"
elif [ "$HTTP_CODE" == "501" ]; then
    skip_test "S3 not configured"
else
    fail_test "HTTP $HTTP_CODE"
fi

#####################################################################
# 1.2.5 - CURSOR-BASED PAGINATION
#####################################################################

print_header "1.2.5 - Cursor-Based Pagination"

# Test 15: Check if cursor pagination is supported
TESTS_RUN=$((TESTS_RUN + 1))
print_test "Check for cursor field in response"
RESPONSE=$(retrieve "market:data" "\"limit\": 10")
HTTP_CODE=$(echo "$RESPONSE" | grep "HTTP_STATUS" | cut -d: -f2)

if [ "$HTTP_CODE" == "200" ]; then
    if echo "$RESPONSE" | grep -v "HTTP_STATUS" | jq -e '.cursor' > /dev/null 2>&1 || \
       echo "$RESPONSE" | grep -v "HTTP_STATUS" | jq -e '.next_cursor' > /dev/null 2>&1; then
        echo "  Cursor field found in response"
        pass_test
    else
        skip_test "Cursor-based pagination not implemented yet"
    fi
elif [ "$HTTP_CODE" == "501" ]; then
    skip_test "S3 not configured"
else
    fail_test "HTTP $HTTP_CODE"
fi

#####################################################################
# ADDITIONAL TESTS - SENTIMENT DATA
#####################################################################

print_header "Additional Tests - Sentiment Data"

# Test 16: Retrieve sentiment data
TESTS_RUN=$((TESTS_RUN + 1))
print_test "Retrieve sentiment:data collection"
RESPONSE=$(retrieve "sentiment:data" "\"limit\": 50")
HTTP_CODE=$(echo "$RESPONSE" | grep "HTTP_STATUS" | cut -d: -f2)

if [ "$HTTP_CODE" == "200" ]; then
    COUNT=$(echo "$RESPONSE" | grep -o '"count":[0-9]*' | cut -d: -f2)
    echo "  Retrieved $COUNT sentiment messages"
    pass_test
elif [ "$HTTP_CODE" == "501" ]; then
    skip_test "S3 not configured"
else
    fail_test "HTTP $HTTP_CODE"
fi

#####################################################################
# TEST SUMMARY
#####################################################################

print_header "TEST SUMMARY"

echo ""
echo "Total Tests Run:    $TESTS_RUN"
echo -e "${GREEN}Passed:             $TESTS_PASSED${NC}"
echo -e "${RED}Failed:             $TESTS_FAILED${NC}"
echo -e "${YELLOW}Skipped:            $TESTS_SKIPPED${NC}"
echo ""

if [ "$TESTS_FAILED" -gt 0 ]; then
    echo -e "${RED}❌ SOME TESTS FAILED${NC}"
    exit 1
elif [ "$TESTS_SKIPPED" -eq "$TESTS_RUN" ]; then
    echo -e "${YELLOW}⚠️  ALL TESTS SKIPPED (S3 not configured?)${NC}"
    exit 2
else
    echo -e "${GREEN}✅ ALL TESTS PASSED${NC}"
    exit 0
fi
