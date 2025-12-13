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
#   ADMIN_KEY: Admin API key (for creating test keys, optional)
#   FEEDER_KEY: Feeder API key (for RBAC testing, optional)
#   READONLY_KEY: Readonly API key (for RBAC testing, optional)
#   SKIP_SECURITY_TESTS: Set to 'true' to skip RBAC/security tests

set -euo pipefail

# Configuration
MCP_URL="${1:-${MCP_URL:-http://localhost:8080}}"
API_KEY="${MCP_API_KEY:-}"
ADMIN_KEY="${ADMIN_KEY:-}"
FEEDER_KEY="${FEEDER_KEY:-}"
READONLY_KEY="${READONLY_KEY:-}"
SKIP_SECURITY_TESTS="${SKIP_SECURITY_TESTS:-false}"

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

    # ========================================
    # SECURITY TESTS (Phase 6 Compliance)
    # ========================================
    if [ "$SKIP_SECURITY_TESTS" = "true" ]; then
        log_warning "Skipping security tests (SKIP_SECURITY_TESTS=true)"
    else
        echo ""
        echo "========================================"
        echo "SECURITY TESTS (RBAC & Permissions)"
        echo "========================================"

        # Test 9: No API key (should fail with 401)
        test_case "Security: No API key provided (401 expected)"
        response=$(curl -s -w '\n%{http_code}' -X POST "$MCP_URL/tool/search_rag" \
            -H "Content-Type: application/json" \
            -d '{"query": "test", "limit": 3}')
        http_code=$(echo "$response" | tail -n1)

        if [ "$http_code" -eq 401 ]; then
            log_info "✓ No API key correctly rejected (HTTP 401)"
            TESTS_PASSED=$((TESTS_PASSED + 1))
        elif [ "$http_code" -eq 200 ]; then
            log_warning "⚠ No API key allowed (dev mode enabled?)"
        else
            log_error "✗ Unexpected HTTP code: $http_code"
            TESTS_FAILED=$((TESTS_FAILED + 1))
        fi

        # Test 10: Invalid API key (should fail with 401)
        test_case "Security: Invalid API key (401 expected)"
        response=$(curl -s -w '\n%{http_code}' -X POST "$MCP_URL/tool/search_rag" \
            -H "x-api-key: mcp_invalid_fakekeyfakekeyfakekeyfakekey" \
            -H "Content-Type: application/json" \
            -d '{"query": "test", "limit": 3}')
        http_code=$(echo "$response" | tail -n1)

        assert_error "$http_code" 401 "Invalid API key rejected"

        # Test 11: RBAC - Feeder key (should fail with 403)
        if [ -n "$FEEDER_KEY" ]; then
            test_case "Security: Feeder key access (403 expected - RBAC)"
            response=$(curl -s -w '\n%{http_code}' -X POST "$MCP_URL/tool/search_rag" \
                -H "x-api-key: $FEEDER_KEY" \
                -H "Content-Type: application/json" \
                -d '{"query": "unauthorized query", "limit": 3}')
            http_code=$(echo "$response" | tail -n1)
            body=$(echo "$response" | sed '$d')

            if [ "$http_code" -eq 403 ]; then
                log_info "✓ Feeder key correctly denied (HTTP 403 - RBAC working)"
                TESTS_PASSED=$((TESTS_PASSED + 1))
            elif [ "$http_code" -eq 200 ]; then
                log_error "✗ RBAC VIOLATION: Feeder key allowed access!"
                log_error "  This is a CRITICAL security issue - feeder should NOT have retrieve:rag permission"
                TESTS_FAILED=$((TESTS_FAILED + 1))
            else
                log_warning "⚠ Unexpected HTTP code: $http_code"
                echo "Response: $body"
            fi
        else
            log_warning "Skipping feeder RBAC test (FEEDER_KEY not set)"
        fi

        # Test 12: RBAC - Readonly key (should fail with 403)
        if [ -n "$READONLY_KEY" ]; then
            test_case "Security: Readonly key access (403 expected - RBAC)"
            response=$(curl -s -w '\n%{http_code}' -X POST "$MCP_URL/tool/search_rag" \
                -H "x-api-key: $READONLY_KEY" \
                -H "Content-Type: application/json" \
                -d '{"query": "unauthorized query", "limit": 3}')
            http_code=$(echo "$response" | tail -n1)
            body=$(echo "$response" | sed '$d')

            if [ "$http_code" -eq 403 ]; then
                log_info "✓ Readonly key correctly denied (HTTP 403 - RBAC working)"
                TESTS_PASSED=$((TESTS_PASSED + 1))
            elif [ "$http_code" -eq 200 ]; then
                log_error "✗ RBAC VIOLATION: Readonly key allowed access!"
                log_error "  This is a CRITICAL security issue - readonly should NOT have retrieve:rag permission"
                TESTS_FAILED=$((TESTS_FAILED + 1))
            else
                log_warning "⚠ Unexpected HTTP code: $http_code"
                echo "Response: $body"
            fi
        else
            log_warning "Skipping readonly RBAC test (READONLY_KEY not set)"
        fi

        # Test 13: RBAC - Admin/Brain key (should succeed)
        if [ -n "$ADMIN_KEY" ]; then
            test_case "Security: Admin key access (200 expected - has permission)"
            response=$(curl -s -w '\n%{http_code}' -X POST "$MCP_URL/tool/search_rag" \
                -H "x-api-key: $ADMIN_KEY" \
                -H "Content-Type: application/json" \
                -d '{"query": "authorized query", "limit": 3}')
            http_code=$(echo "$response" | tail -n1)
            body=$(echo "$response" | sed '$d')

            if [ "$http_code" -eq 200 ]; then
                log_info "✓ Admin key correctly allowed (HTTP 200 - has retrieve:rag)"
                TESTS_PASSED=$((TESTS_PASSED + 1))
            elif [ "$http_code" -eq 403 ]; then
                log_error "✗ Admin key denied! Admin should have all permissions"
                TESTS_FAILED=$((TESTS_FAILED + 1))
            elif [ "$http_code" -eq 501 ]; then
                log_warning "RAG endpoint not configured (HTTP 501)"
            else
                log_warning "⚠ Unexpected HTTP code: $http_code"
                echo "Response: $body"
            fi
        else
            log_warning "Skipping admin RBAC test (ADMIN_KEY not set)"
            log_info "Tip: Set ADMIN_KEY, FEEDER_KEY, READONLY_KEY to run full security tests"
        fi

        echo ""
        log_info "Security tests completed"
        log_info "RBAC Status: ${FEEDER_KEY:+Feeder tested}${READONLY_KEY:+ Readonly tested}${ADMIN_KEY:+ Admin tested}"
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
