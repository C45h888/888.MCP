#!/usr/bin/env bash
# verify_imports.sh - Verify all import fixes are correct
# Run this after fixing import issues to ensure no regressions

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MCP_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "=========================================="
echo "MCP Import Verification"
echo "=========================================="
echo ""

ERRORS=0

# Test 1: No sys.path manipulations
echo "✓ Test 1: Check for sys.path manipulations"
if grep -r "sys.path.insert\|sys.path.append" "$MCP_DIR" --include="*.py" 2>/dev/null; then
    echo "  ✗ FAIL: Found sys.path manipulations (should use relative/package imports)"
    ERRORS=$((ERRORS + 1))
else
    echo "  ✓ PASS: No sys.path manipulations found"
fi
echo ""

# Test 2: No direct imports of local modules
echo "✓ Test 2: Check for direct imports of local modules"
PROBLEM_IMPORTS=$(grep -rn "^from redis_client\|^from retrieval\|^from server\|^import redis_client\|^import retrieval" "$MCP_DIR" --include="*.py" 2>/dev/null | grep -v "test_" || true)
if [ -n "$PROBLEM_IMPORTS" ]; then
    echo "  ✗ FAIL: Found direct imports (should use relative or mcp. prefix):"
    echo "$PROBLEM_IMPORTS"
    ERRORS=$((ERRORS + 1))
else
    echo "  ✓ PASS: No problematic direct imports found"
fi
echo ""

# Test 3: server.py uses relative imports
echo "✓ Test 3: Verify server.py uses relative imports"
if grep -q "^from \.redis_client import RedisClient" "$MCP_DIR/server.py" && \
   grep -q "^from \.retrieval import" "$MCP_DIR/server.py"; then
    echo "  ✓ PASS: server.py uses relative imports"
else
    echo "  ✗ FAIL: server.py does not use relative imports"
    ERRORS=$((ERRORS + 1))
fi
echo ""

# Test 4: archiver_runner.py uses relative imports
echo "✓ Test 4: Verify archiver_runner.py uses relative imports"
if grep -q "^from \.archiver import Archiver" "$MCP_DIR/uploader/archiver_runner.py"; then
    echo "  ✓ PASS: archiver_runner.py uses relative imports"
else
    echo "  ✗ FAIL: archiver_runner.py does not use relative imports"
    ERRORS=$((ERRORS + 1))
fi
echo ""

# Test 5: test_endpoints.py uses package imports
echo "✓ Test 5: Verify test_endpoints.py uses package imports"
if grep -q "^from mcp import server" "$MCP_DIR/tests/test_endpoints.py" && \
   grep -q "^from mcp\.redis_client import RedisClient" "$MCP_DIR/tests/test_endpoints.py"; then
    echo "  ✓ PASS: test_endpoints.py uses package imports"
else
    echo "  ✗ FAIL: test_endpoints.py does not use package imports"
    ERRORS=$((ERRORS + 1))
fi
echo ""

# Test 6: __main__ block in server.py uses mcp.server:app
echo "✓ Test 6: Verify server.py __main__ uses mcp.server:app"
if grep -q '"mcp\.server:app"' "$MCP_DIR/server.py"; then
    echo "  ✓ PASS: server.py __main__ uses correct module path"
else
    echo "  ✗ FAIL: server.py __main__ does not use mcp.server:app"
    ERRORS=$((ERRORS + 1))
fi
echo ""

# Test 7: Python syntax check (if Python available)
if command -v python3 &> /dev/null; then
    echo "✓ Test 7: Python syntax validation"

    SYNTAX_ERRORS=0
    for py_file in $(find "$MCP_DIR" -name "*.py" -type f | grep -v __pycache__); do
        if ! python3 -m py_compile "$py_file" 2>/dev/null; then
            echo "  ✗ Syntax error in: $py_file"
            SYNTAX_ERRORS=$((SYNTAX_ERRORS + 1))
        fi
    done

    if [ $SYNTAX_ERRORS -eq 0 ]; then
        echo "  ✓ PASS: All Python files have valid syntax"
    else
        echo "  ✗ FAIL: Found $SYNTAX_ERRORS files with syntax errors"
        ERRORS=$((ERRORS + 1))
    fi
    echo ""
else
    echo "  ⚠ SKIP: Python not available for syntax check"
    echo ""
fi

# Summary
echo "=========================================="
if [ $ERRORS -eq 0 ]; then
    echo "✅ ALL TESTS PASSED"
    echo "=========================================="
    echo ""
    echo "Import fixes verified successfully!"
    echo "Ready to commit and deploy."
    exit 0
else
    echo "❌ $ERRORS TEST(S) FAILED"
    echo "=========================================="
    echo ""
    echo "Please fix the issues above before deploying."
    exit 1
fi
