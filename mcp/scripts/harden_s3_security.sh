#!/bin/bash
# S3 Security Hardening Script for MCP Server
# Applies security best practices to S3 bucket
#
# Usage:
#   ./harden_s3_security.sh
#
# Environment Variables Required:
#   S3_DATA_BUCKET - S3 bucket name (e.g., mcp-data-prod-kamesh.888)
#   AWS_REGION - AWS region (e.g., eu-north-1)
#
# Optional:
#   ENABLE_ACCESS_LOGGING - Set to "true" to enable S3 access logging
#   S3_LOGS_BUCKET - Bucket for access logs (required if ENABLE_ACCESS_LOGGING=true)

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Helper functions
info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

success() {
    echo -e "${GREEN}[✓]${NC} $1"
}

warning() {
    echo -e "${YELLOW}[⚠]${NC} $1"
}

error() {
    echo -e "${RED}[✗]${NC} $1"
}

check_command() {
    if ! command -v "$1" &> /dev/null; then
        error "Required command '$1' not found. Please install it first."
        exit 1
    fi
}

# Banner
echo "=========================================="
echo "  MCP Server S3 Security Hardening"
echo "=========================================="
echo ""

# Check prerequisites
info "Checking prerequisites..."
check_command aws
check_command jq
success "All required commands available"
echo ""

# Check environment variables
if [ -z "$S3_DATA_BUCKET" ]; then
    error "S3_DATA_BUCKET environment variable is required"
    echo "Example: export S3_DATA_BUCKET=mcp-data-prod-kamesh.888"
    exit 1
fi

if [ -z "$AWS_REGION" ]; then
    warning "AWS_REGION not set, defaulting to eu-north-1"
    AWS_REGION="eu-north-1"
fi

info "Configuration:"
echo "  Bucket: $S3_DATA_BUCKET"
echo "  Region: $AWS_REGION"
echo ""

# Verify bucket exists
info "Verifying bucket exists..."
if aws s3api head-bucket --bucket "$S3_DATA_BUCKET" --region "$AWS_REGION" 2>/dev/null; then
    success "Bucket '$S3_DATA_BUCKET' found"
else
    error "Bucket '$S3_DATA_BUCKET' not found or not accessible"
    exit 1
fi
echo ""

# Function to apply security measure
apply_security_measure() {
    local measure_name=$1
    local measure_command=$2
    local check_command=$3

    info "Applying: $measure_name"

    # Check if already applied
    if [ -n "$check_command" ]; then
        if eval "$check_command" &>/dev/null; then
            success "$measure_name already applied"
            return 0
        fi
    fi

    # Apply measure
    if eval "$measure_command" &>/dev/null; then
        success "$measure_name applied successfully"
        return 0
    else
        error "$measure_name failed to apply"
        return 1
    fi
}

# Track success/failure
TOTAL_MEASURES=0
SUCCESSFUL_MEASURES=0

# ============================================================================
# 1. Enable Bucket Versioning
# ============================================================================
TOTAL_MEASURES=$((TOTAL_MEASURES + 1))
info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
info "1/5: Enabling Bucket Versioning"
info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if apply_security_measure \
    "Bucket Versioning" \
    "aws s3api put-bucket-versioning \
        --bucket \"$S3_DATA_BUCKET\" \
        --versioning-configuration Status=Enabled \
        --region \"$AWS_REGION\"" \
    "aws s3api get-bucket-versioning --bucket \"$S3_DATA_BUCKET\" --region \"$AWS_REGION\" | jq -e '.Status == \"Enabled\"'"; then
    SUCCESSFUL_MEASURES=$((SUCCESSFUL_MEASURES + 1))
    echo "  Benefits:"
    echo "    ✓ Protects against accidental deletion"
    echo "    ✓ Enables data recovery from previous versions"
    echo "    ✓ Maintains audit trail of changes"
fi
echo ""

# ============================================================================
# 2. Enable Server-Side Encryption
# ============================================================================
TOTAL_MEASURES=$((TOTAL_MEASURES + 1))
info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
info "2/5: Enabling Server-Side Encryption (AES256)"
info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if apply_security_measure \
    "Server-Side Encryption" \
    "aws s3api put-bucket-encryption \
        --bucket \"$S3_DATA_BUCKET\" \
        --server-side-encryption-configuration '{
            \"Rules\": [{
                \"ApplyServerSideEncryptionByDefault\": {
                    \"SSEAlgorithm\": \"AES256\"
                },
                \"BucketKeyEnabled\": true
            }]
        }' \
        --region \"$AWS_REGION\"" \
    "aws s3api get-bucket-encryption --bucket \"$S3_DATA_BUCKET\" --region \"$AWS_REGION\" | jq -e '.Rules[0].ApplyServerSideEncryptionByDefault.SSEAlgorithm == \"AES256\"'"; then
    SUCCESSFUL_MEASURES=$((SUCCESSFUL_MEASURES + 1))
    echo "  Benefits:"
    echo "    ✓ Encrypts data at rest"
    echo "    ✓ No performance impact"
    echo "    ✓ Protects against physical media theft"
fi
echo ""

# ============================================================================
# 3. Block Public Access
# ============================================================================
TOTAL_MEASURES=$((TOTAL_MEASURES + 1))
info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
info "3/5: Blocking Public Access"
info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if apply_security_measure \
    "Public Access Block" \
    "aws s3api put-public-access-block \
        --bucket \"$S3_DATA_BUCKET\" \
        --public-access-block-configuration \
            BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true \
        --region \"$AWS_REGION\"" \
    "aws s3api get-public-access-block --bucket \"$S3_DATA_BUCKET\" --region \"$AWS_REGION\" | jq -e '.PublicAccessBlockConfiguration.BlockPublicAcls == true'"; then
    SUCCESSFUL_MEASURES=$((SUCCESSFUL_MEASURES + 1))
    echo "  Benefits:"
    echo "    ✓ Prevents accidental public exposure"
    echo "    ✓ Blocks ACL-based public access"
    echo "    ✓ Blocks policy-based public access"
fi
echo ""

# ============================================================================
# 4. Enable Default Encryption for New Objects
# ============================================================================
TOTAL_MEASURES=$((TOTAL_MEASURES + 1))
info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
info "4/5: Verifying Default Encryption Settings"
info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Check encryption (already set in step 2)
if aws s3api get-bucket-encryption --bucket "$S3_DATA_BUCKET" --region "$AWS_REGION" &>/dev/null; then
    SUCCESSFUL_MEASURES=$((SUCCESSFUL_MEASURES + 1))
    success "Default encryption verified"
    echo "  All new objects will be encrypted automatically"
else
    warning "Default encryption not set (should have been set in step 2)"
fi
echo ""

# ============================================================================
# 5. Enable Access Logging (Optional)
# ============================================================================
TOTAL_MEASURES=$((TOTAL_MEASURES + 1))
info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
info "5/5: S3 Access Logging (Optional)"
info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [ "$ENABLE_ACCESS_LOGGING" = "true" ]; then
    if [ -z "$S3_LOGS_BUCKET" ]; then
        error "S3_LOGS_BUCKET is required when ENABLE_ACCESS_LOGGING=true"
        warning "Skipping access logging setup"
    else
        info "Enabling access logging to: $S3_LOGS_BUCKET"

        # Check if logs bucket exists
        if ! aws s3api head-bucket --bucket "$S3_LOGS_BUCKET" --region "$AWS_REGION" 2>/dev/null; then
            warning "Logs bucket '$S3_LOGS_BUCKET' not found. Creating it..."
            aws s3 mb "s3://$S3_LOGS_BUCKET" --region "$AWS_REGION"
            success "Logs bucket created"
        fi

        if apply_security_measure \
            "Access Logging" \
            "aws s3api put-bucket-logging \
                --bucket \"$S3_DATA_BUCKET\" \
                --bucket-logging-status '{
                    \"LoggingEnabled\": {
                        \"TargetBucket\": \"$S3_LOGS_BUCKET\",
                        \"TargetPrefix\": \"s3-access-logs/\"
                    }
                }' \
                --region \"$AWS_REGION\"" \
            "aws s3api get-bucket-logging --bucket \"$S3_DATA_BUCKET\" --region \"$AWS_REGION\" | jq -e '.LoggingEnabled != null'"; then
            SUCCESSFUL_MEASURES=$((SUCCESSFUL_MEASURES + 1))
            echo "  Benefits:"
            echo "    ✓ Complete audit trail of all S3 access"
            echo "    ✓ Logs stored in: s3://$S3_LOGS_BUCKET/s3-access-logs/"
            warning "Note: Access logging adds cost (~\$0.01/GB of logs)"
        fi
    fi
else
    warning "Access logging not enabled (ENABLE_ACCESS_LOGGING != true)"
    echo "  To enable: export ENABLE_ACCESS_LOGGING=true"
    echo "           export S3_LOGS_BUCKET=mcp-logs-bucket-name"
    SUCCESSFUL_MEASURES=$((SUCCESSFUL_MEASURES + 1))  # Count as success (intentionally skipped)
fi
echo ""

# ============================================================================
# Summary
# ============================================================================
echo "=========================================="
echo "  Security Hardening Summary"
echo "=========================================="
echo ""

if [ $SUCCESSFUL_MEASURES -eq $TOTAL_MEASURES ]; then
    success "All security measures applied successfully! ($SUCCESSFUL_MEASURES/$TOTAL_MEASURES)"
    echo ""
    echo "✅ Your S3 bucket is now hardened with:"
    echo "   • Versioning enabled (data recovery)"
    echo "   • Server-side encryption (data at rest)"
    echo "   • Public access blocked (privacy)"
    echo "   • Default encryption enforced (all new objects)"
    if [ "$ENABLE_ACCESS_LOGGING" = "true" ]; then
        echo "   • Access logging enabled (audit trail)"
    fi
    echo ""
    success "Security Status: EXCELLENT"
    exit 0
else
    warning "Some security measures failed: $SUCCESSFUL_MEASURES/$TOTAL_MEASURES successful"
    echo ""
    echo "⚠️  Please review errors above and fix manually"
    echo ""
    exit 1
fi
