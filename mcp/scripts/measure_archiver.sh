#!/bin/bash
#
# Archiver Metrics Collection Script
#
# Measures current archiver performance and S3 upload statistics
#
# Usage:
#   export MCP_URL="https://your-server.com"
#   export MCP_API_KEY="your-key"
#   ./measure_archiver.sh [--output FILE]

set -e

OUTPUT_FILE=""

# Parse arguments
while [[ $# -gt 0 ]]; do
  case $1 in
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

# Check env vars
if [ -z "$MCP_URL" ]; then
    echo "ERROR: MCP_URL not set"
    exit 1
fi

if [ -z "$MCP_API_KEY" ]; then
    echo "ERROR: MCP_API_KEY not set"
    exit 1
fi

TIMESTAMP=$(date +%s)

echo "================================================"
echo "  Archiver Metrics Collection"
echo "================================================"
echo "Time: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

# Get server status
echo "Fetching server status..."
STATUS_RESPONSE=$(curl -s -H "x-api-key: $MCP_API_KEY" "$MCP_URL/tool/get_status" 2>&1)

if [ $? -ne 0 ]; then
    echo "ERROR: Failed to fetch status"
    echo "$STATUS_RESPONSE"
    exit 1
fi

# Parse status (if it's valid JSON)
echo "$STATUS_RESPONSE" | python3 -m json.tool > /dev/null 2>&1
if [ $? -eq 0 ]; then
    REDIS_CONNECTED=$(echo "$STATUS_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('redis_connected', 'unknown'))" 2>/dev/null || echo "unknown")
    echo "Redis connected: $REDIS_CONNECTED"
else
    echo "WARNING: Invalid JSON response from server"
    REDIS_CONNECTED="unknown"
fi

# Count recent S3 uploads (today)
echo ""
echo "Checking S3 uploads (today)..."

if command -v aws &> /dev/null; then
    TODAY=$(date +%Y-%m-%d)

    # List today's uploads
    S3_FILES=$(aws s3 ls s3://mcp-data-prod-kamesh.888/mcp/ --recursive 2>/dev/null | grep "$TODAY" || echo "")

    if [ -n "$S3_FILES" ]; then
        FILE_COUNT=$(echo "$S3_FILES" | wc -l)
        TOTAL_SIZE=$(echo "$S3_FILES" | awk '{sum+=$3} END {print sum}')
        AVG_SIZE=$(echo "scale=2; $TOTAL_SIZE / $FILE_COUNT" | bc)

        echo "Files uploaded today: $FILE_COUNT"
        echo "Total size: $(echo "scale=2; $TOTAL_SIZE / 1024" | bc) KB"
        echo "Average file size: $(echo "scale=2; $AVG_SIZE / 1024" | bc) KB"
    else
        echo "No S3 uploads found for today"
        FILE_COUNT=0
        TOTAL_SIZE=0
        AVG_SIZE=0
    fi
else
    echo "AWS CLI not available, skipping S3 check"
    FILE_COUNT="N/A"
    TOTAL_SIZE="N/A"
    AVG_SIZE="N/A"
fi

echo ""
echo "================================================"

# Output JSON if file specified
if [ -n "$OUTPUT_FILE" ]; then
    cat > "$OUTPUT_FILE" <<EOF
{
  "timestamp": $TIMESTAMP,
  "time": "$(date '+%Y-%m-%d %H:%M:%S')",
  "redis_connected": "$REDIS_CONNECTED",
  "s3_files_today": "$FILE_COUNT",
  "s3_total_size_bytes": "$TOTAL_SIZE",
  "s3_avg_file_size_bytes": "$AVG_SIZE"
}
EOF
    echo "Metrics saved to: $OUTPUT_FILE"
fi
