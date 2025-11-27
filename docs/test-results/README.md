# Test Results Directory

This directory stores evidence and documentation from test runs during Phase A stabilization and beyond.

## Purpose

- **Document test executions** - Save outputs from smoke tests and other validation
- **Track failures** - Preserve error logs and diagnostics for debugging
- **Enable auditing** - Provide evidence of testing thoroughness
- **Support rollback decisions** - Historical record of system stability

## File Naming Convention

### Successful Test Runs
```
YYYY-MM-DD-smoke-tests.txt         # Standard smoke test output
YYYY-MM-DD-HH-MM-smoke-tests.txt   # Multiple runs same day
YYYY-MM-DD-phase-a-complete.txt    # Phase completion evidence
```

### Failure Documentation
```
YYYY-MM-DD-FAILURE.txt              # Failed smoke test output
YYYY-MM-DD-server-logs.txt          # Server logs during failure
YYYY-MM-DD-worker-logs.txt          # Archiver logs during failure
YYYY-MM-DD-redis-logs.txt           # Redis logs during failure
```

### Incident Reports
```
INCIDENT-YYYY-MM-DD.md              # Root cause analysis
INCIDENT-YYYY-MM-DD-resolution.md   # How issue was resolved
```

## What to Document

### For Each Test Run

Save the following when running smoke tests:

```bash
# 1. Smoke test output
./scripts/run_smoke_tests.sh | tee docs/test-results/$(date +%Y-%m-%d)-smoke-tests.txt

# 2. If tests fail, capture full diagnostics
./scripts/run_smoke_tests.sh | tee docs/test-results/$(date +%Y-%m-%d)-FAILURE.txt
./scripts/render_status.sh web-logs > docs/test-results/$(date +%Y-%m-%d)-server-logs.txt
./scripts/render_status.sh worker-logs > docs/test-results/$(date +%Y-%m-%d)-worker-logs.txt
./scripts/render_status.sh status > docs/test-results/$(date +%Y-%m-%d)-system-status.txt
```

### For Phase Completion

Document evidence when completing major phases:

```bash
# Phase A completion evidence
{
  echo "# Phase A Completion Evidence"
  echo "Date: $(date)"
  echo ""
  echo "## Final Smoke Test Run"
  ./scripts/run_smoke_tests.sh
  echo ""
  echo "## System Health"
  curl -H "x-api-key: $MCP_API_KEY" "$MCP_URL/tool/get_status"
  echo ""
  echo "## Service Status"
  ./scripts/render_status.sh status
} | tee docs/test-results/$(date +%Y-%m-%d)-phase-a-complete.txt
```

## Retention Policy

- **Successful runs:** Keep last 10 runs, archive older
- **Failures:** Keep indefinitely for historical analysis
- **Incidents:** Keep indefinitely with resolution docs
- **Phase completions:** Keep indefinitely as project milestones

## Directory Structure Example

```
test-results/
├── README.md                          # This file
├── 2024-11-26-smoke-tests.txt        # Successful run #1
├── 2024-11-26-14-30-smoke-tests.txt  # Successful run #2
├── 2024-11-27-FAILURE.txt            # Failed test output
├── 2024-11-27-server-logs.txt        # Logs from failure
├── 2024-11-27-resolution.md          # How failure was fixed
├── 2024-11-28-phase-a-complete.txt   # Phase A evidence
└── INCIDENT-2024-11-27.md            # Incident report
```

## Git Policy

**Commit test results selectively:**

- ✅ **Commit:** Phase completion evidence, incident reports
- ✅ **Commit:** First successful run after major changes
- ❌ **Don't commit:** Every single test run (too noisy)
- ❌ **Don't commit:** Logs with secrets/credentials

Add to `.gitignore` if needed:
```
# In .gitignore
docs/test-results/*-smoke-tests.txt
docs/test-results/*-logs.txt
```

But explicitly commit important files:
```bash
git add -f docs/test-results/2024-11-26-phase-a-complete.txt
git add docs/test-results/INCIDENT-*.md
```

## Quick Commands

```bash
# List all test results
ls -lh docs/test-results/

# View latest test
cat docs/test-results/$(ls -t docs/test-results/*.txt | head -1)

# Count failures
ls docs/test-results/*FAILURE* | wc -l

# Archive old successful tests (keep last 10)
cd docs/test-results
mkdir -p archive
ls -t *-smoke-tests.txt | tail -n +11 | xargs -I {} mv {} archive/
```

## Related Documentation

- [current-work.md](../../.claude/resources/current-work.md) - Current phase and tasks
- [SMOKE_TESTING.md](../../mcp/SMOKE_TESTING.md) - Test suite details
- [CLAUDE.md](../../.claude/CLAUDE.md) - System architecture

---

**Created:** 2024-11-26
**Purpose:** Track Phase A stabilization testing
