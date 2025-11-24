#!/usr/bin/env bash
# render_status.sh - Render CLI Integration Helper
#
# This script uses the Render CLI to check service status, view logs,
# and inspect the deployment environment for the MCP server.
#
# Prerequisites:
#   - Render CLI installed (v2.5.0+)
#   - Authenticated: render login
#
# Usage:
#   ./render_status.sh status    # Show all service statuses
#   ./render_status.sh logs      # Tail logs from all services
#   ./render_status.sh web-logs  # Tail web server logs only
#   ./render_status.sh worker-logs # Tail worker logs only
#   ./render_status.sh env       # Show environment variables (masked)
#   ./render_status.sh deploy    # Show recent deployment info

set -e

# ============================================================================
# CONFIGURATION
# ============================================================================

# Service names (update these to match your Render services)
WEB_SERVICE="${WEB_SERVICE:-mcp-server}"
WORKER_SERVICE="${WORKER_SERVICE:-mcp-archiver}"
REDIS_SERVICE="${REDIS_SERVICE:-mcp-redis}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

# Check if render CLI is installed and authenticated
RENDER_CLI=$(which render 2>/dev/null || echo "")

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

check_render_cli() {
  if [[ -z "$RENDER_CLI" ]]; then
    log_error "Render CLI not found in PATH"
    echo "  Install: https://github.com/render-oss/cli/releases"
    echo "  Or run: curl -L https://github.com/render-oss/cli/releases/download/v2.5.0/cli_2.5.0_darwin_arm64.zip -o render.zip"
    return 1
  fi

  # Check authentication
  if ! render whoami &>/dev/null; then
    log_error "Render CLI not authenticated"
    echo "  Run: render login"
    return 1
  fi

  return 0
}

# ============================================================================
# SERVICE STATUS
# ============================================================================

show_status() {
  log_info "Checking service statuses..."
  echo ""

  echo -e "${BOLD}=== WEB SERVICE ($WEB_SERVICE) ===${NC}"
  if render services get "$WEB_SERVICE" --output json 2>/dev/null | jq -r '.status' | grep -q "live\|running"; then
    log_success "Web service is running"
    render services get "$WEB_SERVICE" --output text 2>/dev/null | head -10
  else
    log_error "Web service may be down"
    render services get "$WEB_SERVICE" --output text 2>/dev/null || echo "  Could not fetch service info"
  fi

  echo ""
  echo -e "${BOLD}=== WORKER SERVICE ($WORKER_SERVICE) ===${NC}"
  if render services get "$WORKER_SERVICE" 2>/dev/null; then
    render services get "$WORKER_SERVICE" --output text 2>/dev/null | head -10
  else
    log_warn "Worker service not found or not accessible"
  fi

  echo ""
  echo -e "${BOLD}=== REDIS SERVICE ($REDIS_SERVICE) ===${NC}"
  if render services get "$REDIS_SERVICE" 2>/dev/null; then
    render services get "$REDIS_SERVICE" --output text 2>/dev/null | head -10
  else
    log_warn "Redis service not found or not accessible"
  fi

  echo ""
}

# ============================================================================
# LOGS
# ============================================================================

tail_all_logs() {
  log_info "Tailing logs from all services..."
  log_info "Press Ctrl+C to stop"
  echo ""

  echo -e "${CYAN}=== WEB SERVICE LOGS ===${NC}"
  render logs --service "$WEB_SERVICE" --tail 50

  echo ""
  echo -e "${CYAN}=== WORKER SERVICE LOGS ===${NC}"
  render logs --service "$WORKER_SERVICE" --tail 50
}

tail_web_logs() {
  log_info "Tailing web server logs..."
  log_info "Press Ctrl+C to stop"
  echo ""

  render logs --service "$WEB_SERVICE" --tail 100
}

tail_worker_logs() {
  log_info "Tailing worker logs..."
  log_info "Press Ctrl+C to stop"
  echo ""

  render logs --service "$WORKER_SERVICE" --tail 100
}

# ============================================================================
# ENVIRONMENT VARIABLES
# ============================================================================

show_env() {
  log_info "Environment variables (sensitive values masked)"
  echo ""

  echo -e "${BOLD}=== WEB SERVICE ENV ===${NC}"
  render services get "$WEB_SERVICE" --output json 2>/dev/null | \
    jq -r '.envVars[] | "\(.key)=\(if .sync == false then "[SYNCED]" else .value end)"' 2>/dev/null || \
    log_warn "Could not fetch environment variables"

  echo ""
  echo -e "${BOLD}=== WORKER SERVICE ENV ===${NC}"
  render services get "$WORKER_SERVICE" --output json 2>/dev/null | \
    jq -r '.envVars[] | "\(.key)=\(if .sync == false then "[SYNCED]" else .value end)"' 2>/dev/null || \
    log_warn "Could not fetch environment variables"

  echo ""
}

# ============================================================================
# DEPLOYMENT INFO
# ============================================================================

show_deployment_info() {
  log_info "Recent deployment information"
  echo ""

  echo -e "${BOLD}=== WEB SERVICE DEPLOYS ===${NC}"
  render deploys list --service "$WEB_SERVICE" --limit 5 2>/dev/null || \
    log_warn "Could not fetch deployment history"

  echo ""
  echo -e "${BOLD}=== WORKER SERVICE DEPLOYS ===${NC}"
  render deploys list --service "$WORKER_SERVICE" --limit 5 2>/dev/null || \
    log_warn "Could not fetch deployment history"

  echo ""
}

# ============================================================================
# MAIN
# ============================================================================

usage() {
  echo "Usage: $0 <command>"
  echo ""
  echo "Commands:"
  echo "  status       Show all service statuses"
  echo "  logs         Tail logs from all services"
  echo "  web-logs     Tail web server logs only"
  echo "  worker-logs  Tail worker logs only"
  echo "  env          Show environment variables (masked)"
  echo "  deploy       Show recent deployment info"
  echo ""
  echo "Environment Variables:"
  echo "  WEB_SERVICE     Web service name (default: mcp-server)"
  echo "  WORKER_SERVICE  Worker service name (default: mcp-archiver)"
  echo "  REDIS_SERVICE   Redis service name (default: mcp-redis)"
  echo ""
}

main() {
  # Check prerequisites
  check_render_cli || exit 1

  # Parse command
  local command="${1:-status}"

  case "$command" in
    status)
      show_status
      ;;
    logs)
      tail_all_logs
      ;;
    web-logs)
      tail_web_logs
      ;;
    worker-logs)
      tail_worker_logs
      ;;
    env)
      show_env
      ;;
    deploy)
      show_deployment_info
      ;;
    help|--help|-h)
      usage
      ;;
    *)
      log_error "Unknown command: $command"
      echo ""
      usage
      exit 1
      ;;
  esac
}

main "$@"
