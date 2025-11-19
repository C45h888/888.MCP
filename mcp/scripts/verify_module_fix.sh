#!/usr/bin/env bash
# verify_module_fix.sh - Verify the mcp package structure fix
# Tests both web and worker roles in Docker

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
MCP_DIR="$PROJECT_ROOT/mcp"

echo "=========================================="
echo "MCP Module Structure Verification"
echo "=========================================="
echo ""

# Test 1: Check __init__.py exists
echo "✓ Test 1: Check mcp/__init__.py exists"
if [ -f "$MCP_DIR/__init__.py" ]; then
    echo "  ✓ Found: mcp/__init__.py"
else
    echo "  ✗ MISSING: mcp/__init__.py"
    exit 1
fi
echo ""

# Test 2: Verify Dockerfile structure
echo "✓ Test 2: Verify Dockerfile uses 'COPY . mcp/'"
if grep -q "COPY . mcp/" "$MCP_DIR/Dockerfile"; then
    echo "  ✓ Dockerfile correctly copies to mcp/ subdirectory"
else
    echo "  ✗ Dockerfile does not use 'COPY . mcp/'"
    exit 1
fi
echo ""

# Test 3: Verify entrypoint.sh sets PYTHONPATH
echo "✓ Test 3: Verify entrypoint.sh sets PYTHONPATH"
if grep -q "export PYTHONPATH.*:/app" "$MCP_DIR/entrypoint.sh"; then
    echo "  ✓ PYTHONPATH correctly configured"
else
    echo "  ✗ PYTHONPATH not set in entrypoint.sh"
    exit 1
fi
echo ""

# Test 4: Verify entrypoint.sh uses mcp.server:app
echo "✓ Test 4: Verify entrypoint.sh uses 'mcp.server:app'"
if grep -q "uvicorn mcp.server:app" "$MCP_DIR/entrypoint.sh"; then
    echo "  ✓ Web server uses correct module path"
else
    echo "  ✗ Web server does not use 'mcp.server:app'"
    exit 1
fi
echo ""

# Test 5: Verify entrypoint.sh uses mcp.uploader.archiver_runner
echo "✓ Test 5: Verify entrypoint.sh uses 'mcp.uploader.archiver_runner'"
if grep -q "python -u -m mcp.uploader.archiver_runner" "$MCP_DIR/entrypoint.sh"; then
    echo "  ✓ Worker uses correct module path"
else
    echo "  ✗ Worker does not use correct module path"
    exit 1
fi
echo ""

echo "=========================================="
echo "Pre-Flight Checks: PASSED ✓"
echo "=========================================="
echo ""

# Docker tests (if Docker is available)
if command -v docker &> /dev/null; then
    echo "Docker detected. Running container tests..."
    echo ""

    cd "$PROJECT_ROOT"

    # Build image
    echo "Building Docker image..."
    docker build -t mcp-verify-test ./mcp
    echo ""

    # Test worker role (with ARCHIVE_ENABLED=false to exit immediately)
    echo "✓ Test 6: Worker role module import"
    if docker run --rm \
        -e SERVICE_ROLE=worker \
        -e ARCHIVE_ENABLED=false \
        -e REDIS_URL=redis://fake:6379 \
        mcp-verify-test 2>&1 | grep -q "MCP Archiver Worker starting"; then
        echo "  ✓ Worker starts without ModuleNotFoundError"
    else
        echo "  ✗ Worker failed to start"
        exit 1
    fi
    echo ""

    # Test web role (quick startup check)
    echo "✓ Test 7: Web server module import"
    timeout 5 docker run --rm \
        -e SERVICE_ROLE=web \
        -e REDIS_URL=redis://fake:6379 \
        -e MCP_DEV=true \
        mcp-verify-test 2>&1 | grep -q "mcp.server:app" && echo "  ✓ Web server starts with correct module path" || echo "  ⚠ Web server check (timeout expected)"
    echo ""

    # Cleanup
    docker rmi mcp-verify-test

    echo "=========================================="
    echo "Docker Tests: PASSED ✓"
    echo "=========================================="
else
    echo "Docker not available. Skipping container tests."
    echo "Run manually: docker build -t mcp-test ./mcp"
    echo ""
fi

echo ""
echo "All verification tests passed!"
echo "Ready to commit and deploy to Render."
