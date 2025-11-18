#!/bin/bash
# sanity_start_test.sh - Docker multi-role startup validation
#
# Tests that the Docker image builds correctly and both SERVICE_ROLE modes start.
# This does NOT test full functionality - only that processes start without error.
#
# Usage:
#   cd /path/to/888.MCP/mcp
#   bash scripts/sanity_start_test.sh

set -e

echo "======================================"
echo "MCP Docker Multi-Role Sanity Test"
echo "======================================"
echo ""

IMAGE_NAME="mcp-server-test:latest"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MCP_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$MCP_DIR"

echo "[1/5] Building Docker image..."
docker build -t "$IMAGE_NAME" .
echo "✓ Image built successfully"
echo ""

echo "[2/5] Testing web role startup (SERVICE_ROLE=web)..."
CONTAINER_WEB=$(docker run -d \
  -e SERVICE_ROLE=web \
  -e PORT=8080 \
  -e REDIS_URL=redis://fake-redis:6379 \
  -e MCP_DEV=true \
  "$IMAGE_NAME")

echo "   Container started: $CONTAINER_WEB"
sleep 3

# Check logs for startup message
docker logs "$CONTAINER_WEB" 2>&1 | grep -q "Starting MCP web server" && \
  echo "✓ Web role started correctly" || \
  (echo "✗ Web role failed to start"; docker logs "$CONTAINER_WEB"; exit 1)

docker stop "$CONTAINER_WEB" >/dev/null 2>&1 || true
docker rm "$CONTAINER_WEB" >/dev/null 2>&1 || true
echo ""

echo "[3/5] Testing worker role startup (SERVICE_ROLE=worker)..."
CONTAINER_WORKER=$(docker run -d \
  -e SERVICE_ROLE=worker \
  -e ARCHIVE_ENABLED=true \
  -e ARCHIVE_DIR=/tmp/test_archive \
  -e REDIS_URL=redis://fake-redis:6379 \
  "$IMAGE_NAME")

echo "   Container started: $CONTAINER_WORKER"
sleep 3

# Check logs for archiver startup
docker logs "$CONTAINER_WORKER" 2>&1 | grep -q "MCP Archiver Worker starting" && \
  echo "✓ Worker role started correctly" || \
  (echo "✗ Worker role failed to start"; docker logs "$CONTAINER_WORKER"; exit 1)

docker stop "$CONTAINER_WORKER" >/dev/null 2>&1 || true
docker rm "$CONTAINER_WORKER" >/dev/null 2>&1 || true
echo ""

echo "[4/5] Testing invalid role rejection (SERVICE_ROLE=invalid)..."
CONTAINER_INVALID=$(docker run -d \
  -e SERVICE_ROLE=invalid \
  "$IMAGE_NAME") || true

sleep 2
docker logs "$CONTAINER_INVALID" 2>&1 | grep -q "Unknown SERVICE_ROLE" && \
  echo "✓ Invalid role correctly rejected" || \
  echo "⚠ Warning: Invalid role detection may not be working"

docker rm "$CONTAINER_INVALID" >/dev/null 2>&1 || true
echo ""

echo "[5/5] Testing default role (no SERVICE_ROLE env, should default to web)..."
CONTAINER_DEFAULT=$(docker run -d \
  -e PORT=8080 \
  -e REDIS_URL=redis://fake-redis:6379 \
  -e MCP_DEV=true \
  "$IMAGE_NAME")

sleep 3
docker logs "$CONTAINER_DEFAULT" 2>&1 | grep -q "Starting MCP web server" && \
  echo "✓ Default role (web) works correctly" || \
  (echo "✗ Default role failed"; docker logs "$CONTAINER_DEFAULT"; exit 1)

docker stop "$CONTAINER_DEFAULT" >/dev/null 2>&1 || true
docker rm "$CONTAINER_DEFAULT" >/dev/null 2>&1 || true
echo ""

echo "======================================"
echo "✓ All sanity tests passed!"
echo "======================================"
echo ""
echo "Next steps:"
echo "  1. Commit changes: git add . && git commit -m 'fix: implement entrypoint-based multi-role Docker startup'"
echo "  2. Push to Render: git push"
echo "  3. Verify Render deployment validates successfully"
echo ""
