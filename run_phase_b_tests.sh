#!/bin/bash

# Phase B: Controlled Load Introduction
# Tests system under realistic message throughput

MCP_URL="https://mcp-server-7h8i.onrender.com"
MCP_API_KEY="92a746171ea6a580f8b29bf31dfe0b0c"

# Configuration
TOTAL_MESSAGES=100
SAMPLE_INTERVAL=300  # 5 minutes
MONITORING_SAMPLES=4  # 20 minutes total

echo "========================================="
echo "PHASE B: CONTROLLED LOAD INTRODUCTION"
echo "Date: $(date)"
echo "========================================="
echo ""

# ============================================
# BASELINE: Capture pre-test state
# ============================================
echo "### BASELINE: Pre-Test State ###"
echo ""
echo "Capturing baseline status..."
curl -s -H "x-api-key: $MCP_API_KEY" "$MCP_URL/tool/get_status" | jq . > baseline-status.json
echo "Baseline saved to baseline-status.json"
echo ""
echo "Baseline Redis Connection:"
jq -r '"Redis connected: \(.redis_connected)"' baseline-status.json
echo ""
echo "Baseline Channel Counts:"
jq '.channels' baseline-status.json
echo ""
echo "📊 TIP: Open Render dashboard now to monitor CPU/Memory during the test"
echo "Starting load test in 3 seconds..."
sleep 3

# ============================================
# B1: Light Throughput Testing
# ============================================
echo "========================================="
echo "### B1: Light Throughput Testing ###"
echo "Sending $TOTAL_MESSAGES messages rapidly..."
echo "========================================="
echo ""

SUCCESS_COUNT=0
FAIL_COUNT=0
TOTAL_TIME=0
MIN_TIME=99999
MAX_TIME=0

START_TIME=$(date +%s)

for i in $(seq 1 $TOTAL_MESSAGES); do
  # Show progress every 10 messages
  if [ $((i % 10)) -eq 0 ]; then
    echo "Progress: $i/$TOTAL_MESSAGES messages..."
  fi

  # Send message and capture response time
  RESPONSE=$(curl -s -w "\n%{time_total}" -X POST "$MCP_URL/tool/publish" \
    -H "x-api-key: $MCP_API_KEY" \
    -H "Content-Type: application/json" \
    -d "{\"channel\":\"market:data\",\"message\":{\"schema_version\":\"v1\",\"timestamp\":$(date +%s),\"pair\":\"BTC-ETH\",\"price_btc\":$((30000 + i)),\"price_eth\":2000.0,\"volume_btc\":1.0}}")

  # Parse response
  BODY=$(echo "$RESPONSE" | head -1)
  TIME=$(echo "$RESPONSE" | tail -1)

  # Check success
  if echo "$BODY" | grep -q '"success":true'; then
    SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
  else
    FAIL_COUNT=$((FAIL_COUNT + 1))
    echo "  ❌ Message $i FAILED: $BODY"
  fi

  # Track timing
  TOTAL_TIME=$(echo "$TOTAL_TIME + $TIME" | bc)
  if (( $(echo "$TIME < $MIN_TIME" | bc -l) )); then
    MIN_TIME=$TIME
  fi
  if (( $(echo "$TIME > $MAX_TIME" | bc -l) )); then
    MAX_TIME=$TIME
  fi
done

END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))
AVG_TIME=$(echo "scale=3; $TOTAL_TIME / $TOTAL_MESSAGES" | bc)

echo ""
echo "========================================="
echo "B1: Load Test Results"
echo "========================================="
echo "Total messages sent: $TOTAL_MESSAGES"
echo "Successful: $SUCCESS_COUNT"
echo "Failed: $FAIL_COUNT"
echo "Success rate: $(echo "scale=1; ($SUCCESS_COUNT * 100) / $TOTAL_MESSAGES" | bc)%"
echo ""
echo "Timing:"
echo "  Total duration: ${DURATION}s"
echo "  Average response time: ${AVG_TIME}s"
echo "  Min response time: ${MIN_TIME}s"
echo "  Max response time: ${MAX_TIME}s"
echo "  Throughput: $(echo "scale=2; $TOTAL_MESSAGES / $DURATION" | bc) msg/sec"
echo ""

# Check Redis stability after load
echo "Checking Redis stability after load..."
REDIS_STATUS=$(curl -s -H "x-api-key: $MCP_API_KEY" "$MCP_URL/tool/get_status" | jq -r '.redis_connected')
if [ "$REDIS_STATUS" = "true" ]; then
  echo "✅ Redis still connected after load test"
else
  echo "❌ CRITICAL: Redis disconnected during load test!"
fi
echo ""

# ============================================
# B2: Queue & Memory Health Analysis
# ============================================
echo "========================================="
echo "### B2: Queue & Memory Health Analysis ###"
echo "Monitoring system over $((SAMPLE_INTERVAL * MONITORING_SAMPLES / 60)) minutes..."
echo "========================================="
echo ""

for sample in $(seq 1 $MONITORING_SAMPLES); do
  echo "--- Sample $sample/$MONITORING_SAMPLES at $(date) ---"

  STATUS=$(curl -s -H "x-api-key: $MCP_API_KEY" "$MCP_URL/tool/get_status")

  echo "Redis connected: $(echo "$STATUS" | jq -r '.redis_connected')"
  echo "Channel depths:"
  echo "$STATUS" | jq '.channels'
  echo ""

  # Save sample
  echo "$STATUS" | jq . > "sample-$sample.json"

  if [ $sample -lt $MONITORING_SAMPLES ]; then
    echo "Waiting $((SAMPLE_INTERVAL / 60)) minutes until next sample..."
    echo "(Check Render dashboard for CPU/Memory trends)"
    sleep $SAMPLE_INTERVAL
  fi
done

echo ""
echo "========================================="
echo "B2: Health Analysis Complete"
echo "========================================="
echo ""
echo "Analyzing queue growth patterns..."
echo ""

# Compare samples
INITIAL_MARKET=$(jq -r '.channels."market:data"' sample-1.json)
FINAL_MARKET=$(jq -r '.channels."market:data"' sample-$MONITORING_SAMPLES.json)

echo "market:data channel:"
echo "  Initial: $INITIAL_MARKET"
echo "  Final: $FINAL_MARKET"
echo "  Change: $((FINAL_MARKET - INITIAL_MARKET))"

if [ $FINAL_MARKET -gt $((INITIAL_MARKET + 50)) ]; then
  echo "  ⚠️  WARNING: Queue growing significantly (archiver may be slow)"
elif [ $FINAL_MARKET -lt $((INITIAL_MARKET - 50)) ]; then
  echo "  ✅ Queue shrinking (archiver processing efficiently)"
else
  echo "  ✅ Queue stable (system in balance)"
fi

echo ""
echo "========================================="
echo "PHASE B COMPLETE!"
echo "========================================="
echo ""
echo "Next steps:"
echo "1. Review Render dashboard for CPU/Memory trends"
echo "2. Check if memory usage plateaued or grew linearly"
echo "3. Review sample-*.json files for detailed metrics"
echo "4. Document results in docs/test-results/"
echo ""
echo "Files generated:"
echo "  - baseline-status.json"
echo "  - sample-1.json through sample-$MONITORING_SAMPLES.json"
echo ""
