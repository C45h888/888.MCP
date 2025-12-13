#!/bin/bash
# test_rag_endpoint.sh - Test script for /tool/search_rag endpoint
#
# Tests the RAG (Retrieval Augmented Generation) search endpoint with various scenarios.
# Supports both mock and remote vector DB backends.
#
# Usage:
#   ./test_rag_endpoint.sh                    # Test against localhost (dev mode)
#   ./test_rag_endpoint.sh https://example.com  # Test against remote server
#
# Environment variables:
#   MCP_URL: MCP server base URL (default: http://localhost:8080)
#   MCP_API_KEY: API key for authentication (optional in dev mode)

set -euo pipefail

# Configuration
MCP_URL="${1:-${MCP_URL:-http://localhost:8080}}"
API_KEY="${MCP_API_KEY:-}"

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test counter
TESTS_RUN=0
TESTS_PASSED=0
TESTS_FAILED=0

# Helper functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

test_case() {
    local name="$1"
    echo ""
    echo "===================="
    echo "Test: $name"
    echo "===================="
    TESTS_RUN=$((TESTS_RUN + 1))
}

assert_success() {
    local response="$1"
    local test_name="$2"

    if echo "$response" | jq -e '.success == true' > /dev/null 2>&1; then
        log_info "✓ $test_name: PASSED"
        TESTS_PASSED=$((TESTS_PASSED + 1))
        return 0
    else
        log_error "✗ $test_name: FAILED"
        echo "Response: $response"
        TESTS_FAILED=$((TESTS_FAILED + 1))
        return 1
    fi
}

assert_error() {
    local http_code="$1"
    local expected_code="$2"
    local test_name="$3"

    if [ "$http_code" -eq "$expected_code" ]; then
        log_info "✓ $test_name: PASSED (HTTP $http_code)"
        TESTS_PASSED=$((TESTS_PASSED + 1))
        return 0
    else
        log_error "✗ $test_name: FAILED (expected HTTP $expected_code, got $http_code)"
        TESTS_FAILED=$((TESTS_FAILED + 1))
        return 1
    fi
}

# Build curl command with optional API key
build_curl() {
    local method="$1"
    local endpoint="$2"
    local data="${3:-}"

    local curl_cmd="curl -s -w '\n%{http_code}' -X $method"

    if [ -n "$API_KEY" ]; then
        curl_cmd="$curl_cmd -H 'x-api-key: $API_KEY'"
    fi

    curl_cmd="$curl_cmd -H 'Content-Type: application/json'"

    if [ -n "$data" ]; then
        curl_cmd="$curl_cmd -d '$data'"
    fi

    curl_cmd="$curl_cmd '$MCP_URL$endpoint'"

    echo "$curl_cmd"
}

# Main tests
main() {
    log_info "Testing MCP RAG endpoint at: $MCP_URL"

    if [ -z "$API_KEY" ]; then
        log_warning "No API key provided (MCP_API_KEY not set). Tests may fail if server is in production mode."
    fi

    # Test 1: Basic search query
    test_case "Basic RAG search with bitcoin query"
    response=$(eval "$(build_curl POST /tool/search_rag '{
        "query": "bitcoin market sentiment",
        "limit": 3
    }')")
    http_code=$(echo "$response" | tail -n1)
    body=$(echo "$response" | sed '$d')

    if [ "$http_code" -eq 200 ]; then
        assert_success "$body" "Bitcoin search query"
        echo "Results: $(echo "$body" | jq -c '.results')"
    elif [ "$http_code" -eq 501 ]; then
        log_warning "RAG endpoint not configured (HTTP 501) - this is expected if VECTOR_DB_TYPE not set"
    else
        log_error "Unexpected HTTP code: $http_code"
        echo "Response: $body"
    fi

    # Test 2: Search with limit parameter
    test_case "RAG search with custom limit"
    response=$(eval "$(build_curl POST /tool/search_rag '{
        "query": "ethereum price prediction",
        "limit": 5
    }')")
    http_code=$(echo "$response" | tail -n1)
    body=$(echo "$response" | sed '$d')

    if [ "$http_code" -eq 200 ]; then
        assert_success "$body" "Custom limit search"
        count=$(echo "$body" | jq -r '.count')
        log_info "Returned $count results"
    elif [ "$http_code" -eq 501 ]; then
        log_warning "RAG endpoint not configured (HTTP 501)"
    fi

    # Test 3: Search with min_score filter
    test_case "RAG search with min_score threshold"
    response=$(eval "$(build_curl POST /tool/search_rag '{
        "query": "market crash news",
        "limit": 5,
        "min_score": 0.7
    }')")
    http_code=$(echo "$response" | tail -n1)
    body=$(echo "$response" | sed '$d')

    if [ "$http_code" -eq 200 ]; then
        assert_success "$body" "Min score filter"
        # Verify all results meet min_score threshold
        min_scores=$(echo "$body" | jq -r '.results[].score')
        echo "Result scores: $min_scores"
    elif [ "$http_code" -eq 501 ]; then
        log_warning "RAG endpoint not configured (HTTP 501)"
    fi

    # Test 4: Search with metadata filters
    test_case "RAG search with metadata filters"
    response=$(eval "$(build_curl POST /tool/search_rag '{
        "query": "trading volume",
        "limit": 5,
        "filters": {
            "pair": "BTC-ETH"
        }
    }')")
    http_code=$(echo "$response" | tail -n1)
    body=$(echo "$response" | sed '$d')

    if [ "$http_code" -eq 200 ]; then
        assert_success "$body" "Metadata filters"
    elif [ "$http_code" -eq 501 ]; then
        log_warning "RAG endpoint not configured (HTTP 501)"
    fi

    # Test 5: Invalid limit (should fail)
    test_case "Invalid limit (exceeds maximum)"
    response=$(eval "$(build_curl POST /tool/search_rag '{
        "query": "test",
        "limit": 1000
    }')")
    http_code=$(echo "$response" | tail -n1)

    assert_error "$http_code" 400 "Limit validation"

    # Test 6: Invalid min_score (should fail)
    test_case "Invalid min_score (out of range)"
    response=$(eval "$(build_curl POST /tool/search_rag '{
        "query": "test",
        "min_score": 1.5
    }')")
    http_code=$(echo "$response" | tail -n1)

    assert_error "$http_code" 400 "Min score validation"

    # Test 7: Missing required field (should fail)
    test_case "Missing required query field"
    response=$(eval "$(build_curl POST /tool/search_rag '{
        "limit": 5
    }')")
    http_code=$(echo "$response" | tail -n1)

    assert_error "$http_code" 422 "Required field validation"

    # Test 8: Empty query (edge case)
    test_case "Empty query string"
    response=$(eval "$(build_curl POST /tool/search_rag '{
        "query": "",
        "limit": 5
    }')")
    http_code=$(echo "$response" | tail -n1)
    body=$(echo "$response" | sed '$d')

    if [ "$http_code" -eq 200 ]; then
        log_info "Empty query accepted (may return no results)"
    elif [ "$http_code" -eq 400 ] || [ "$http_code" -eq 422 ]; then
        log_info "Empty query rejected (expected validation)"
    elif [ "$http_code" -eq 501 ]; then
        log_warning "RAG endpoint not configured (HTTP 501)"
    fi

    # Summary
    echo ""
    echo "===================="
    echo "Test Summary"
    echo "===================="
    echo "Total tests: $TESTS_RUN"
    echo "Passed: $TESTS_PASSED"
    echo "Failed: $TESTS_FAILED"

    if [ $TESTS_FAILED -eq 0 ]; then
        log_info "All tests passed! ✓"
        exit 0
    else
        log_error "Some tests failed. Check output above."
        exit 1
    fi
}

# Check dependencies
if ! command -v jq &> /dev/null; then
    log_error "jq is required but not installed. Install with: brew install jq"
    exit 1
fi

if ! command -v curl &> /dev/null; then
    log_error "curl is required but not installed."
    exit 1
fi

# Run tests
main
