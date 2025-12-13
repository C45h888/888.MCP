#!/bin/bash
# Phase 4 Test Runner Script
#
# Runs comprehensive Phase 4 security tests
#
# Usage:
#   ./mcp/scripts/run_phase4_tests.sh [options]
#
# Options:
#   --unit          Run only unit tests (auth, rate limiting)
#   --integration   Run only integration tests
#   --security      Run only security attack tests
#   --performance   Run only performance tests
#   --quick         Run quick smoke tests only
#   --verbose       Verbose output
#   --coverage      Run with coverage report

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

# Banner
echo "=========================================="
echo "  Phase 4 Security Test Suite"
echo "=========================================="
echo ""

# Check if we're in the correct directory
if [ ! -f "mcp/tests/test_phase4_comprehensive.py" ]; then
    error "Must be run from repository root (888.MCP/)"
    error "Current directory: $(pwd)"
    exit 1
fi

# Check if pytest is installed
if ! command -v pytest &> /dev/null; then
    error "pytest is not installed"
    info "Install with: pip install pytest pytest-cov pytest-asyncio"
    exit 1
fi

# Parse options
RUN_TYPE="all"
VERBOSE=""
COVERAGE=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --unit)
            RUN_TYPE="unit"
            shift
            ;;
        --integration)
            RUN_TYPE="integration"
            shift
            ;;
        --security)
            RUN_TYPE="security"
            shift
            ;;
        --performance)
            RUN_TYPE="performance"
            shift
            ;;
        --quick)
            RUN_TYPE="quick"
            shift
            ;;
        --verbose|-v)
            VERBOSE="-v -s"
            shift
            ;;
        --coverage)
            COVERAGE="--cov=mcp --cov-report=term-missing --cov-report=html"
            shift
            ;;
        *)
            error "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Set pytest options based on run type
case $RUN_TYPE in
    unit)
        info "Running unit tests only..."
        PYTEST_ARGS="-k 'TestAPIKey or TestRateLimit or TestPermission'"
        ;;
    integration)
        info "Running integration tests only..."
        PYTEST_ARGS="-k 'Integration'"
        ;;
    security)
        info "Running security attack tests only..."
        PYTEST_ARGS="-k 'TestSecurityAttacks'"
        ;;
    performance)
        info "Running performance tests only..."
        PYTEST_ARGS="-k 'TestPerformance'"
        ;;
    quick)
        info "Running quick smoke tests..."
        PYTEST_ARGS="-k 'test_generate_key_format or test_admin_has_all_permissions or test_default_rate_limits'"
        ;;
    all)
        info "Running all Phase 4 tests..."
        PYTEST_ARGS=""
        ;;
esac

# Run tests
echo ""
info "Test command: pytest mcp/tests/test_phase4_comprehensive.py $PYTEST_ARGS $VERBOSE $COVERAGE"
echo ""

# Execute pytest
if pytest mcp/tests/test_phase4_comprehensive.py $PYTEST_ARGS $VERBOSE $COVERAGE --tb=short; then
    echo ""
    success "All tests passed!"
    echo ""

    # Summary
    echo "=========================================="
    echo "  Test Summary"
    echo "=========================================="
    echo ""

    if [ "$RUN_TYPE" = "all" ]; then
        echo "✅ Authentication Tests: PASSED"
        echo "✅ Rate Limiting Tests: PASSED"
        echo "✅ Permission Tests: PASSED"
        echo "✅ Integration Tests: PASSED"
        echo "✅ Security Tests: PASSED"
        echo ""
        success "Phase 4 security implementation is ready for deployment"
    else
        success "$RUN_TYPE tests completed successfully"
    fi

    if [ -n "$COVERAGE" ]; then
        echo ""
        info "Coverage report generated: htmlcov/index.html"
        info "Open with: open htmlcov/index.html (macOS) or xdg-open htmlcov/index.html (Linux)"
    fi

    exit 0
else
    echo ""
    error "Some tests failed!"
    echo ""
    echo "=========================================="
    echo "  Troubleshooting"
    echo "=========================================="
    echo ""
    echo "Common issues:"
    echo ""
    echo "1. Redis not running:"
    echo "   docker-compose up -d redis"
    echo ""
    echo "2. Missing dependencies:"
    echo "   pip install -r mcp/requirements.txt"
    echo ""
    echo "3. Import errors:"
    echo "   Make sure PYTHONPATH includes mcp directory"
    echo "   export PYTHONPATH=\$PYTHONPATH:$(pwd)"
    echo ""
    echo "4. Run with verbose output:"
    echo "   ./mcp/scripts/run_phase4_tests.sh --verbose"
    echo ""

    exit 1
fi
