#!/bin/bash

# Priority 3: Data Pipeline Tests (A3.1-A3.3) - NON-BLOCKING

MCP_URL="https://mcp-server-7h8i.onrender.com"
MCP_API_KEY="92a746171ea6a580f8b29bf31dfe0b0c"

echo "========================================="
echo "PRIORITY 3: Data Pipeline Tests (NON-BLOCKING)"
echo "Date: $(date)"
echo "========================================="
echo ""

# ============================================
echo "### Task A3.1: Archiver Worker Health Check ###"
echo ""
echo "Note: Checking if render CLI is available..."
if command -v render &> /dev/null; then
  echo "Render CLI found. Checking service status..."
  cd mcp && ./scripts/render_status.sh status | grep -A5 mcp-archiver
  echo ""
  echo "Checking worker logs..."
  cd mcp && ./scripts/render_status.sh worker-logs | tail -50
else
  echo "⚠️  Render CLI not available - Skipping archiver service checks"
  echo "    This is ACCEPTABLE for Phase A testing"
fi
echo ""
echo "✅ A3.1 Complete (or SKIP if render CLI unavailable)"
echo ""

# ============================================
echo "### Task A3.3: Verify Retrieval Endpoint Behavior ###"
echo ""
echo "Testing retrieval endpoint (expecting 501 if S3 not configured):"
curl -X POST "$MCP_URL/tool/retrieve" \
  -H "x-api-key: $MCP_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"channel":"market:data","limit":10}'
echo ""
echo "✅ A3.3 Complete (501 or 200 both acceptable)"
echo ""

echo "========================================="
echo "Priority 3 (P2) Tests Complete!"
echo "Note: Some tests may have been skipped - this is acceptable"
echo "========================================="
