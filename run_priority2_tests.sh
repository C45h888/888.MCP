#!/bin/bash

# Priority 2: Core Functionality Tests (A2.1-A2.4)

MCP_URL="https://mcp-server-7h8i.onrender.com"
MCP_API_KEY="92a746171ea6a580f8b29bf31dfe0b0c"

echo "========================================="
echo "PRIORITY 2: Core Functionality Tests"
echo "Date: $(date)"
echo "========================================="
echo ""

# ============================================
echo "### Task A2.1: Publish Valid market:data Message ###"
echo ""
curl -X POST "$MCP_URL/tool/publish" \
  -H "x-api-key: $MCP_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"channel\": \"market:data\",
    \"message\": {
      \"schema_version\": \"v1\",
      \"timestamp\": $(date +%s),
      \"pair\": \"BTC-ETH-TEST-A2.1\",
      \"price_btc\": 30000.0,
      \"price_eth\": 2000.0,
      \"volume_btc\": 150.5
    }
  }" | jq .
echo ""
echo "✅ A2.1 Complete"
echo ""

# ============================================
echo "### Task A2.2: Reject Invalid Messages ###"
echo ""
echo "Publishing message WITHOUT schema_version (should fail):"
curl -X POST "$MCP_URL/tool/publish" \
  -H "x-api-key: $MCP_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"channel\": \"market:data\",
    \"message\": {
      \"timestamp\": $(date +%s),
      \"pair\": \"BTC-ETH\",
      \"price_btc\": 30000.0
    }
  }"
echo ""
echo "✅ A2.2 Complete"
echo ""

# ============================================
echo "### Task A2.3: Kill-Switch Activation & Persistence ###"
echo ""
echo "Step 1: Activate kill-switch"
curl -X POST "$MCP_URL/tool/publish" \
  -H "x-api-key: $MCP_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"channel\": \"agent:control\",
    \"message\": {
      \"schema_version\": \"v1\",
      \"timestamp\": $(date +%s),
      \"command\": \"EMERGENCY_HALT\",
      \"reason\": \"PHASE_A_TEST_A2.3\"
    }
  }" | jq .
echo ""
echo "Step 2: Verify kill-switch persistence"
curl -H "x-api-key: $MCP_API_KEY" "$MCP_URL/tool/get_status" | jq '.kill_switch'
echo ""
echo "✅ A2.3 Complete"
echo ""

# ============================================
echo "### Task A2.4: Kill-Switch Resume (CLEAR) ###"
echo ""
echo "Step 1: Clear kill-switch"
curl -X POST "$MCP_URL/tool/publish" \
  -H "x-api-key: $MCP_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"channel\": \"agent:control\",
    \"message\": {
      \"schema_version\": \"v1\",
      \"timestamp\": $(date +%s),
      \"command\": \"RESUME\",
      \"reason\": \"PHASE_A_TEST_A2.4_COMPLETE\"
    }
  }" | jq .
echo ""
echo "Step 2: Verify kill-switch cleared"
curl -H "x-api-key: $MCP_API_KEY" "$MCP_URL/tool/get_status" | jq '.kill_switch.active'
echo ""
echo "✅ A2.4 Complete"
echo ""

echo "========================================="
echo "Priority 2 (P1) Tests Complete!"
echo "========================================="
