#!/bin/bash
# S3 Inspection Helper for Phase 1.1 - Archiver Stability & S3 Behaviour
# Generated: 2025-11-28
#
# Purpose: Inspect S3 bucket structure and verify partition integrity
# Usage: ./scripts/inspect_s3.sh

set -e  # Exit on error

# Configuration
BUCKET="${S3_DATA_BUCKET:-}"
PROFILE="${AWS_PROFILE:-production}"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo "==========================================="
echo "S3 BUCKET INSPECTION - Phase 1.1"
echo "==========================================="
echo ""
echo "Bucket: ${BUCKET}"
echo "Profile: ${PROFILE}"
echo "Date: $(date)"
echo ""

# Check if AWS CLI is installed
if ! command -v aws &> /dev/null; then
    echo -e "${RED}ERROR: AWS CLI not found${NC}"
    echo "Please install AWS CLI first:"
    echo "  sudo installer -pkg /tmp/AWSCLIV2.pkg -target /"
    exit 1
fi

# Check if bucket is set
if [ -z "$BUCKET" ]; then
    echo -e "${RED}ERROR: S3_DATA_BUCKET not set${NC}"
    echo "Please export S3_DATA_BUCKET first:"
    echo "  export S3_DATA_BUCKET=<your-bucket-name>"
    exit 1
fi

# Check AWS credentials
if ! aws sts get-caller-identity --profile "$PROFILE" &> /dev/null; then
    echo -e "${RED}ERROR: AWS credentials not configured or invalid${NC}"
    echo "Please configure credentials in ~/.aws/credentials"
    exit 1
fi

echo -e "${GREEN}✓ AWS CLI installed and configured${NC}"
echo ""

# Task 1.1.2: Inspect S3 Object Layout
echo "==========================================="
echo "1. Market Data Objects (Task 1.1.2)"
echo "==========================================="
echo "Listing first 50 objects in mcp/market:data/..."
echo ""
aws s3 ls "s3://$BUCKET/mcp/market:data/" --recursive --profile "$PROFILE" 2>/dev/null | head -50 || {
    echo -e "${YELLOW}⚠ No objects found or access denied${NC}"
}
echo ""

# Task 1.1.3: Verify Partition Structure
echo "==========================================="
echo "2. Partition Structure Validation (Task 1.1.3)"
echo "==========================================="
echo "Checking for Hive-style partitions: year=YYYY/month=MM/day=DD/hour=HH/minute=MM/"
echo ""
PARTITION_COUNT=$(aws s3 ls "s3://$BUCKET/mcp/" --recursive --profile "$PROFILE" 2>/dev/null | \
  grep -E "year=[0-9]{4}/month=[0-9]{2}/day=[0-9]{2}/hour=[0-9]{2}/minute=[0-9]{2}" | wc -l | tr -d ' ')

if [ "$PARTITION_COUNT" -gt 0 ]; then
    echo -e "${GREEN}✓ Found $PARTITION_COUNT files with correct partition structure${NC}"
    echo ""
    echo "Sample partitions:"
    aws s3 ls "s3://$BUCKET/mcp/" --recursive --profile "$PROFILE" 2>/dev/null | \
      grep -E "year=[0-9]{4}/month=[0-9]{2}/day=[0-9]{2}/hour=[0-9]{2}/minute=[0-9]{2}" | head -10
else
    echo -e "${YELLOW}⚠ No files found with expected partition structure${NC}"
    echo "Expected format: year=YYYY/month=MM/day=DD/hour=HH/minute=MM/part-*.jsonl.gz"
fi
echo ""

# Task 1.1.4: Check for Duplicates (prepare data for analysis)
echo "==========================================="
echo "3. Object Counts by Collection (Task 1.1.4 prep)"
echo "==========================================="
for collection in "market:data" "sentiment:data" "agent:control" "agent:signal"; do
  count=$(aws s3 ls "s3://$BUCKET/mcp/$collection/" --recursive --profile "$PROFILE" 2>/dev/null | wc -l | tr -d ' ')
  echo "  $collection: $count objects"
done
echo ""

# Task 1.1.5: Check for Gaps (recent objects)
echo "==========================================="
echo "4. Recent Objects (Gap Detection - Task 1.1.5)"
echo "==========================================="
echo "Last 20 objects (most recent first):"
aws s3 ls "s3://$BUCKET/mcp/market:data/" --recursive --profile "$PROFILE" 2>/dev/null | \
  sort -r | head -20 || {
    echo -e "${YELLOW}⚠ No recent objects found${NC}"
}
echo ""

# Save full object list for offline analysis
OUTPUT_FILE="docs/test-results/s3-objects-$(date +%Y-%m-%d).txt"
mkdir -p docs/test-results
echo "==========================================="
echo "5. Saving Full Object List"
echo "==========================================="
echo "Output file: $OUTPUT_FILE"
aws s3 ls "s3://$BUCKET/mcp/" --recursive --profile "$PROFILE" > "$OUTPUT_FILE" 2>/dev/null || {
    echo -e "${YELLOW}⚠ Could not save object list${NC}"
}
echo ""

echo "==========================================="
echo "INSPECTION COMPLETE"
echo "==========================================="
echo ""
echo "Next steps:"
echo "1. Review $OUTPUT_FILE for duplicates/gaps"
echo "2. Run this script daily for 3-5 days"
echo "3. Compare results across days for consistency"
echo "4. Document findings in WORK_LOG.md"
echo ""
