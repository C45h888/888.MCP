#!/bin/bash
#
# Test Load Injection Script
#
# Injects controlled message load to MCP server for archiver testing.
#
# Usage:
#   export MCP_URL="https://your-server.com"
#   export MCP_API_KEY="your-key"
#   ./inject_test_load.sh --count 1000 --rate 10 --collection "market:data"
#
# Options:
#   --count N         Number of messages to inject (default: 100)
#   --rate R          Messages per second (default: 10)
#   --collection C    Collection name (default: market:data)
#   --output FILE     Output file for results (default: stdout)

set -e

# Default parameters
COUNT=100
RATE=10
COLLECTION="market:data"
OUTPUT_FILE=""

# Parse arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --count)
      COUNT="$2"
      shift 2
      ;;
    --rate)
      RATE="$2"
      shift 2
      ;;
    --collection)
      COLLECTION="$2"
      shift 2
      ;;
    --output)
      OUTPUT_FILE="$2"
      shift 2
      ;;
    *)
      echo "Unknown option: $1"
      exit 1
      ;;
  esac
done

# Check required env vars
if [ -z "$MCP_URL" ]; then
    echo "ERROR: MCP_URL not set"
    exit 1
fi

if [ -z "$MCP_API_KEY" ]; then
    echo "ERROR: MCP_API_KEY not set"
    exit 1
fi

# Calculate sleep interval (in seconds)
SLEEP_INTERVAL=$(echo "scale=3; 1 / $RATE" | bc)

echo "================================================"
echo "  Test Load Injection"
echo "================================================"
echo "Target: $MCP_URL"
echo "Collection: $COLLECTION"
echo "Count: $COUNT messages"
echo "Rate: $RATE msg/sec (interval: ${SLEEP_INTERVAL}s)"
echo "Start time: $(date +%H:%M:%S)"
echo ""

# Metrics
SUCCESS_COUNT=0
FAILED_COUNT=0
START_TIME=$(date +%s)

# Inject messages
for i in $(seq 1 $COUNT); do
    TIMESTAMP=$(date +%s)

    # Generate message based on collection type
    case $COLLECTION in
        "market:data")
            MESSAGE="{
                \"schema_version\": \"v1\",
                \"timestamp\": $TIMESTAMP,
                \"pair\": \"BTC-ETH\",
                \"price_btc\": $((30000 + RANDOM % 1000)),
                \"price_eth\": $((2000 + RANDOM % 100)),
                \"volume_btc\": $((RANDOM % 200))
            }"
            ;;
        "sentiment:data")
            MESSAGE="{
                \"schema_version\": \"v1\",
                \"timestamp\": $TIMESTAMP,
                \"source\": \"Twitter\",
                \"score\": 0.$((RANDOM % 100)),
                \"summary\": \"Test sentiment message $i\"
            }"
            ;;
        "agent:signal")
            MESSAGE="{
                \"schema_version\": \"v1\",
                \"timestamp\": $TIMESTAMP,
                \"pair\": \"BTC-ETH\",
                \"action\": \"FLAT\",
                \"confidence\": 0.$((RANDOM % 100)),
                \"reason\": \"Test signal $i\"
            }"
            ;;
        *)
            echo "ERROR: Unknown collection: $COLLECTION"
            exit 1
            ;;
    esac

    # Publish message
    RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$MCP_URL/tool/publish" \
        -H "x-api-key: $MCP_API_KEY" \
        -H "Content-Type: application/json" \
        -d "{
            \"channel\": \"$COLLECTION\",
            \"message\": $MESSAGE
        }")

    HTTP_CODE=$(echo "$RESPONSE" | tail -1)

    if [ "$HTTP_CODE" = "200" ]; then
        ((SUCCESS_COUNT++))
    else
        ((FAILED_COUNT++))
        echo "ERROR: Message $i failed (HTTP $HTTP_CODE)"
    fi

    # Progress indicator (every 10%)
    if [ $((i % (COUNT / 10))) -eq 0 ]; then
        PROGRESS=$((i * 100 / COUNT))
        echo "Progress: ${PROGRESS}% ($i/$COUNT messages)"
    fi

    # Rate limiting
    if [ "$i" -lt "$COUNT" ]; then
        sleep "$SLEEP_INTERVAL"
    fi
done

END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))
ACTUAL_RATE=$(echo "scale=2; $COUNT / $DURATION" | bc)

echo ""
echo "================================================"
echo "  Results"
echo "================================================"
echo "Total messages: $COUNT"
echo "Successful: $SUCCESS_COUNT"
echo "Failed: $FAILED_COUNT"
echo "Success rate: $(echo "scale=2; $SUCCESS_COUNT * 100 / $COUNT" | bc)%"
echo "Duration: ${DURATION}s"
echo "Actual rate: ${ACTUAL_RATE} msg/sec"
echo "End time: $(date +%H:%M:%S)"
echo ""

# Output JSON if file specified
if [ -n "$OUTPUT_FILE" ]; then
    cat > "$OUTPUT_FILE" <<EOF
{
  "collection": "$COLLECTION",
  "target_count": $COUNT,
  "target_rate": $RATE,
  "success_count": $SUCCESS_COUNT,
  "failed_count": $FAILED_COUNT,
  "success_rate": $(echo "scale=4; $SUCCESS_COUNT / $COUNT" | bc),
  "duration_seconds": $DURATION,
  "actual_rate": $(echo "scale=2; $COUNT / $DURATION" | bc),
  "start_time": $START_TIME,
  "end_time": $END_TIME
}
EOF
    echo "Results saved to: $OUTPUT_FILE"
fi

# Exit code based on success rate
if [ "$FAILED_COUNT" -eq 0 ]; then
    exit 0
else
    exit 1
fi
