#!/usr/bin/env bash
# test_health.sh - Simple health endpoint validation script
# Usage: ./test_health.sh [BASE_URL]
# Default BASE_URL: http://localhost:8080

set -e

BASE_URL="${1:-http://localhost:8080}"
HEALTH_URL="${BASE_URL}/health"

echo "Testing health endpoint at: ${HEALTH_URL}"
echo "----------------------------------------------"

# Test 1: HTTP 200 response
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "${HEALTH_URL}")
if [ "${HTTP_CODE}" -eq 200 ]; then
    echo "✓ HTTP 200 OK"
else
    echo "✗ Failed: Expected HTTP 200, got ${HTTP_CODE}"
    exit 1
fi

# Test 2: JSON response structure
RESPONSE=$(curl -s "${HEALTH_URL}")
echo "Response: ${RESPONSE}"

# Test 3: Required fields present
echo "${RESPONSE}" | grep -q '"status"' && echo "✓ Field 'status' present" || (echo "✗ Missing 'status' field" && exit 1)
echo "${RESPONSE}" | grep -q '"time"' && echo "✓ Field 'time' present" || (echo "✗ Missing 'time' field" && exit 1)
echo "${RESPONSE}" | grep -q '"archiver_enabled"' && echo "✓ Field 'archiver_enabled' present" || (echo "✗ Missing 'archiver_enabled' field" && exit 1)

# Test 4: Ensure no sensitive data (no API keys, no internal metrics)
if echo "${RESPONSE}" | grep -qi "api_key\|secret\|password"; then
    echo "✗ Response contains sensitive data!"
    exit 1
else
    echo "✓ No sensitive data exposed"
fi

echo "----------------------------------------------"
echo "All tests passed!"
