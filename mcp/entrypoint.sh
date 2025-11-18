#!/bin/bash
# entrypoint.sh - Multi-role Docker entrypoint for MCP server
# Reads SERVICE_ROLE env var to determine which component to start
#
# Roles:
#   - web: Start FastAPI uvicorn server (default)
#   - worker: Start background archiver worker
#
# Usage:
#   docker run -e SERVICE_ROLE=web ...
#   docker run -e SERVICE_ROLE=worker ...

set -e

ROLE="${SERVICE_ROLE:-web}"
PORT="${PORT:-8080}"

case "$ROLE" in
  web)
    echo "[entrypoint] Starting MCP web server on port $PORT"
    exec uvicorn server:app --host 0.0.0.0 --port "$PORT"
    ;;
  worker)
    echo "[entrypoint] Starting MCP archiver worker"
    exec python -u -m mcp.uploader.archiver_runner
    ;;
  *)
    echo "[entrypoint] ERROR: Unknown SERVICE_ROLE='$ROLE'. Must be 'web' or 'worker'."
    exit 1
    ;;
esac
