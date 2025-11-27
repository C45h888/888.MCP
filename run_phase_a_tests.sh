#!/bin/bash

# Phase A Testing Script
# Executes tasks A1.2 through A3.3

MCP_URL="https://mcp-server-7h8i.onrender.com"
MCP_API_KEY="92a746171ea6a580f8b29bf31dfe0b0c"

# Create results directory
mkdir -p docs/test-results

echo "========================================="
echo "PHASE A TESTING - Starting $(date)"
echo "========================================="
echo ""

# ============================================
# Priority 1: Baseline Health (Remaining)
# ============================================

echo "### Task A1.2: Health Endpoint Performance ###"
echo ""
for i in {1..3}; do
  echo "Request $i:"
  curl -w "\nTime: %{time_total}s\n" -s "$MCP_URL/health" | jq .
  echo ""
  sleep 2
done

echo "✅ A1.2 Complete"
echo ""

# ============================================
echo "### Task A1.3: Redis Connectivity ###"
echo ""
curl -H "x-api-key: $MCP_API_KEY" "$MCP_URL/tool/get_status" | jq .
echo ""
echo "✅ A1.3 Complete"
echo ""

# ============================================
echo "### Task A1.4: Authentication Enforcement ###"
echo ""
echo "Test 1: WITHOUT API key (should fail with 401/403):"
curl -i "$MCP_URL/tool/get_status" 2>&1 | grep -E "HTTP|401|403|{" | head -5
echo ""
echo "Test 2: WITH API key (should succeed with 200):"
curl -i -H "x-api-key: $MCP_API_KEY" "$MCP_URL/tool/get_status" 2>&1 | grep -E "HTTP|200|redis_connected" | head -5
echo ""
echo "✅ A1.4 Complete"
echo ""

echo "========================================="
echo "Priority 1 (P0) Tests Complete!"
echo "========================================="
