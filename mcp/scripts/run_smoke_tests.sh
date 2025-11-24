#!/usr/bin/env bash
# run_smoke_tests.sh - Wrapper Script for MCP Smoke Tests
#
# This script:
#   1. Validates prerequisites (curl, jq, render CLI)
#   2. Checks authentication
#   3. Sources configuration (if provided)
#   4. Runs the smoke test suite
#   5. Optionally shows Render service status and logs
#
# Usage:
#   ./run_smoke_tests.sh                    # Use env vars
#   ./run_smoke_tests.sh --config smoke_test.local.config
#   ./run_smoke_tests.sh --with-logs        # Show logs after tests
#   ./run_smoke_tests.sh --status-only      # Just show service status

set -e

# ============================================================================
# CONFIGURATION
# ============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

CONFIG_FILE=""
SHOW_LOGS=false
STATUS_ONLY=false

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

# ============================================================================
# PARSE ARGUMENTS
# ============================================================================

while [[ $# -gt 0 ]]; do
  case $1 in
    --config)
      CONFIG_FILE="$2"
      shift 2
      ;;
    --with-logs)
      SHOW_LOGS=true
      shift
      ;;
    --status-only)
      STATUS_ONLY=true
      shift
      ;;
    --help|-h)
      echo "Usage: $0 [OPTIONS]"
      echo ""
      echo "Options:"
      echo "  --config FILE      Source configuration from FILE"
      echo "  --with-logs        Show Render logs after tests"
      echo "  --status-only      Only show service status (no tests)"
      echo "  --help             Show this help message"
      echo ""
      echo "Environment Variables:"
      echo "  MCP_URL            MCP server URL (required)"
      echo "  MCP_API_KEY        MCP API key (required)"
      echo "  S3_BUCKET          S3 bucket name (optional)"
      echo "  AWS_REGION         AWS region (optional)"
      echo ""
      exit 0
      ;;
    *)
      echo "Unknown option: $1"
      echo "Use --help for usage information"
      exit 1
      ;;
  esac
done

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

log_info() {
  echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
  echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_error() {
  echo -e "${RED}[ERROR]${NC} $1"
}

log_warn() {
  echo -e "${YELLOW}[WARN]${NC} $1"
}

check_command() {
  local cmd=$1
  local install_hint=$2

  if ! command -v "$cmd" &> /dev/null; then
    log_error "$cmd not found"
    if [[ -n "$install_hint" ]]; then
      echo "  Install: $install_hint"
    fi
    return 1
  fi
  return 0
}

# ============================================================================
# PREREQUISITES CHECK
# ============================================================================

check_prerequisites() {
  log_info "Checking prerequisites..."

  local missing=0

  # Check curl
  if ! check_command "curl" "brew install curl (macOS) or apt install curl (Linux)"; then
    ((missing++))
  else
    log_success "curl found"
  fi

  # Check jq (optional but recommended)
  if ! check_command "jq" "brew install jq (macOS) or apt install jq (Linux)"; then
    log_warn "jq not found (optional but recommended for better test output)"
  else
    log_success "jq found"
  fi

  # Check render CLI (optional but recommended)
  if ! check_command "render" "See: https://github.com/render-oss/cli/releases"; then
    log_warn "render CLI not found (optional - needed for log analysis)"
  else
    log_success "render CLI found"

    # Check render authentication
    if ! render whoami &>/dev/null; then
      log_warn "render CLI not authenticated (run: render login)"
    else
      log_success "render CLI authenticated"
    fi
  fi

  if [[ $missing -gt 0 ]]; then
    log_error "$missing required tool(s) missing"
    return 1
  fi

  log_success "All required prerequisites found"
  return 0
}

# ============================================================================
# CONFIGURATION
# ============================================================================

load_configuration() {
  # Source config file if provided
  if [[ -n "$CONFIG_FILE" ]]; then
    if [[ -f "$CONFIG_FILE" ]]; then
      log_info "Loading configuration from $CONFIG_FILE"
      # shellcheck disable=SC1090
      source "$CONFIG_FILE"
    else
      log_error "Config file not found: $CONFIG_FILE"
      return 1
    fi
  fi

  # Check required variables
  if [[ -z "$MCP_URL" ]]; then
    log_error "MCP_URL not set"
    echo "  Export it: export MCP_URL=\"https://your-server.onrender.com\""
    echo "  Or use: --config smoke_test.local.config"
    return 1
  fi

  if [[ -z "$MCP_API_KEY" ]]; then
    log_error "MCP_API_KEY not set"
    echo "  Export it: export MCP_API_KEY=\"your-api-key\""
    echo "  Or use: --config smoke_test.local.config"
    return 1
  fi

  log_success "Configuration loaded"
  log_info "  MCP_URL: $MCP_URL"
  log_info "  API Key: ${MCP_API_KEY:0:8}..."

  return 0
}

# ============================================================================
# MAIN
# ============================================================================

main() {
  echo ""
  echo -e "${BOLD}========================================${NC}"
  echo -e "${BOLD}  MCP Smoke Test Runner${NC}"
  echo -e "${BOLD}========================================${NC}"
  echo ""

  # Check prerequisites
  check_prerequisites || exit 1
  echo ""

  # Load configuration
  load_configuration || exit 1
  echo ""

  # Status only mode
  if [[ "$STATUS_ONLY" == "true" ]]; then
    log_info "Status-only mode: Checking Render services..."
    echo ""
    if command -v render &> /dev/null && render whoami &>/dev/null; then
      "$SCRIPT_DIR/render_status.sh" status
    else
      log_warn "Render CLI not available or not authenticated"
      echo "  Run: render login"
    fi
    exit 0
  fi

  # Run smoke tests
  log_info "Starting smoke test suite..."
  echo ""

  if "$SCRIPT_DIR/smoke_test.sh"; then
    TEST_EXIT_CODE=0
    log_success "Smoke tests completed successfully"
  else
    TEST_EXIT_CODE=$?
    log_error "Smoke tests failed with exit code $TEST_EXIT_CODE"
  fi

  # Show logs if requested
  if [[ "$SHOW_LOGS" == "true" ]]; then
    echo ""
    echo -e "${BOLD}========================================${NC}"
    echo -e "${BOLD}  RENDER SERVICE LOGS${NC}"
    echo -e "${BOLD}========================================${NC}"
    echo ""

    if command -v render &> /dev/null && render whoami &>/dev/null; then
      "$SCRIPT_DIR/render_status.sh" logs
    else
      log_warn "Render CLI not available - cannot show logs"
      echo "  To install: https://github.com/render-oss/cli/releases"
      echo "  To authenticate: render login"
    fi
  fi

  # Summary
  echo ""
  echo -e "${BOLD}========================================${NC}"
  echo -e "${BOLD}  SUMMARY${NC}"
  echo -e "${BOLD}========================================${NC}"

  if [[ $TEST_EXIT_CODE -eq 0 ]]; then
    echo -e "${GREEN}✅ All tests passed${NC}"
    echo ""
    echo "Next steps:"
    echo "  - Review logs: ./scripts/render_status.sh logs"
    echo "  - Check status: ./scripts/render_status.sh status"
    echo "  - View deployments: ./scripts/render_status.sh deploy"
  else
    echo -e "${RED}❌ Tests failed${NC}"
    echo ""
    echo "Troubleshooting:"
    echo "  1. Check service status: ./scripts/render_status.sh status"
    echo "  2. View web logs: ./scripts/render_status.sh web-logs"
    echo "  3. View worker logs: ./scripts/render_status.sh worker-logs"
    echo "  4. Verify environment: ./scripts/render_status.sh env"
    echo ""
    echo "Common issues:"
    echo "  - Redis connection failure (check mcp-redis service)"
    echo "  - Invalid API key (check MCP_API_KEY in Render)"
    echo "  - MCP_DEV=true in production (check env vars)"
  fi

  echo ""
  exit $TEST_EXIT_CODE
}

main "$@"
