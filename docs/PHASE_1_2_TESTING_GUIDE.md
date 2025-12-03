# Phase 1.2 - Retrieval Accuracy & Limits Testing Guide

**Status:** Ready for Execution ✅
**Estimated Time:** 1-2 hours
**Dependencies:** Phase 1.1 Complete, S3 configured (optional for basic tests)

---

## Overview

This guide walks you through executing **Phase 1.2 - Retrieval Accuracy & Limits** testing as defined in [current-work.md](../.claude/resources/current-work.md#L786-L805).

**Test Objectives:**
- ✅ 1.2.1: Test `/tool/retrieve` with different pair values
- ✅ 1.2.2: Test edge case time ranges (1min, 7-day, 30-day windows)
- ✅ 1.2.3: Test limit parameter near max (1000) and small (10)
- ✅ 1.2.4: Verify time-ordering of returned records
- ⚠️ 1.2.5: Test cursor-based pagination (not yet implemented)
- ✅ 1.2.6: Document retrieval semantics

---

## Prerequisites

### Required

1. **MCP Server Running**
   - Production: Render.com deployment
   - Local: `docker-compose up -d`

2. **Environment Variables**
   ```bash
   export MCP_URL="https://your-mcp-server.onrender.com"
   export MCP_API_KEY="your-api-key"
   ```

3. **Tools Installed**
   - Python 3.9+ with `requests` library
   - `pytest` for Python tests
   - `curl` and `jq` for bash tests

### Optional (for full testing)

4. **S3 Configured**
   - If S3 not configured: Tests will return HTTP 501 (expected, documented as SKIP)
   - If S3 configured: Full retrieval testing enabled

5. **Test Data Seeded**
   - Use provided seeding script (see Step 1 below)
   - Or use existing production data

---

## Quick Start (5 Minutes)

```bash
# 1. Navigate to project
cd /Users/kamii/888.mcp/888.MCP/mcp

# 2. Set environment variables
export MCP_URL="https://your-mcp-server.onrender.com"
export MCP_API_KEY="your-api-key"

# 3. Seed test data (optional, recommended)
python scripts/seed_test_data.py --market-messages 200 --sentiment-messages 50

# 4. Run bash tests (quick validation)
./scripts/test_retrieval_phase_1_2.sh

# 5. Run Python tests (comprehensive)
pytest tests/integration/test_retrieval_accuracy.py -v
```

---

## Step-by-Step Execution

### Step 1: Seed Test Data

**Purpose:** Populate MCP server with known test data for retrieval testing.

**Commands:**
```bash
cd /Users/kamii/888.mcp/888.MCP/mcp

# Dry run (show what would be published)
python scripts/seed_test_data.py --dry-run

# Seed with defaults (100 market, 30 sentiment)
python scripts/seed_test_data.py

# Seed with custom amounts
python scripts/seed_test_data.py \
  --market-messages 200 \
  --sentiment-messages 50 \
  --time-spread-days 7 \
  --edge-cases

# Check output
# Should see: "✅ ALL MESSAGES PUBLISHED SUCCESSFULLY"
```

**Expected Output:**
```
══════════════════════════════════════════════════════════════════════
MCP Test Data Seeding Utility - Phase 1.2 Retrieval Testing
══════════════════════════════════════════════════════════════════════

Target server: https://your-mcp-server.onrender.com
✅ Server connection verified

📊 Seeding 200 market:data messages...
   Time spread: 7 days
   Trading pairs: ['BTC-ETH', 'BTC-USD', 'ETH-USD']
  Published 200/200... ✅

💭 Seeding 50 sentiment:data messages...
   Time spread: 7 days
   Sources: ['Twitter', 'Reddit', 'News', 'TradingView']
  Published 50/50... ✅

══════════════════════════════════════════════════════════════════════
SEEDING SUMMARY
══════════════════════════════════════════════════════════════════════
Total published: 250
Total failed:    0

✅ ALL MESSAGES PUBLISHED SUCCESSFULLY
```

**⏱️ Wait Time:**
- After seeding, wait **60-90 seconds** for archiver to flush to S3
- Check archiver logs: `./scripts/render_status.sh worker-logs | tail -20`

---

### Step 2: Run Bash Test Suite

**Purpose:** Quick validation using curl commands (manual verification).

**Commands:**
```bash
cd /Users/kamii/888.mcp/888.MCP/mcp

# Ensure environment variables are set
echo "MCP_URL: $MCP_URL"
echo "API_KEY: ${MCP_API_KEY:0:10}..."

# Run test suite
./scripts/test_retrieval_phase_1_2.sh
```

**Expected Output:**
```
════════════════════════════════════════════════════════════════
  PHASE 1.2 - RETRIEVAL ACCURACY & LIMITS TESTING
════════════════════════════════════════════════════════════════

Test Configuration:
  MCP_URL: https://mcp-server-xxx.onrender.com
  MCP_API_KEY: sk-test-ab...
  Current timestamp: 1701388800

════════════════════════════════════════════════════════════════
  1.2.1 - Pair Value Filtering
════════════════════════════════════════════════════════════════

[TEST 1] Retrieve with BTC-ETH pair filter
  Retrieved 67 messages
✅ PASS

[TEST 2] Retrieve with BTC-USD pair filter
  Retrieved 66 messages
✅ PASS

... (16 total tests)

════════════════════════════════════════════════════════════════
  TEST SUMMARY
════════════════════════════════════════════════════════════════

Total Tests Run:    16
Passed:             14
Failed:             0
Skipped:            2

✅ ALL TESTS PASSED
```

**Interpreting Results:**
- **PASS**: Test succeeded ✅
- **FAIL**: Test found a bug ❌ (investigate)
- **SKIP**: S3 not configured or pagination not implemented ⏭️ (expected)

**Exit Codes:**
- `0`: All tests passed
- `1`: Some tests failed (investigate)
- `2`: All tests skipped (S3 not configured)

---

### Step 3: Run Python Test Suite

**Purpose:** Comprehensive automated testing with detailed assertions.

**Commands:**
```bash
cd /Users/kamii/888.mcp/888.MCP/mcp

# Run all retrieval tests
pytest tests/integration/test_retrieval_accuracy.py -v

# Run specific test class
pytest tests/integration/test_retrieval_accuracy.py::TestRetrievalPairFiltering -v

# Run specific test
pytest tests/integration/test_retrieval_accuracy.py::TestRetrievalPairFiltering::test_retrieve_with_btc_eth_pair -v

# Show detailed output
pytest tests/integration/test_retrieval_accuracy.py -v -s

# Generate HTML report
pytest tests/integration/test_retrieval_accuracy.py --html=docs/test-results/phase-1.2-pytest-report.html
```

**Expected Output:**
```
================================ test session starts =================================
platform darwin -- Python 3.11.5, pytest-7.4.3, pluggy-1.3.0
collected 20 items

tests/integration/test_retrieval_accuracy.py::TestRetrievalBasics::test_retrieve_endpoint_exists PASSED     [  5%]
tests/integration/test_retrieval_accuracy.py::TestRetrievalBasics::test_retrieve_requires_valid_collection PASSED [ 10%]
tests/integration/test_retrieval_accuracy.py::TestRetrievalPairFiltering::test_retrieve_with_btc_eth_pair PASSED [ 15%]
tests/integration/test_retrieval_accuracy.py::TestRetrievalPairFiltering::test_retrieve_with_btc_usd_pair PASSED [ 20%]
... (16 more tests)

================================ 18 passed, 2 skipped in 12.34s ==================================
```

**Understanding Test Results:**
- **PASSED**: Test assertion succeeded ✅
- **FAILED**: Assertion failed (bug detected) ❌
- **SKIPPED**: S3 not configured or feature not implemented ⏭️
- **ERROR**: Test setup/teardown failed ⚠️

---

### Step 4: Verify S3 Data Integrity (If S3 Configured)

**Purpose:** Validate that archived data matches published data.

**Commands:**
```bash
# Check S3 bucket structure
aws s3 ls s3://$S3_DATA_BUCKET/mcp/market:data/ --recursive | head -20

# Verify partition structure
aws s3 ls s3://$S3_DATA_BUCKET/mcp/ --recursive | \
  grep -E "year=[0-9]{4}/month=[0-9]{2}/day=[0-9]{2}/hour=[0-9]{2}"

# Download a sample file
aws s3 cp s3://$S3_DATA_BUCKET/mcp/market:data/year=2024/month=12/day=03/hour=10/minute=30/part-abc123.jsonl.gz - | \
  gunzip | jq . | head -5
```

**Expected S3 Structure:**
```
s3://bucket/mcp/market:data/year=2024/month=12/day=03/hour=10/minute=30/part-uuid.jsonl.gz
s3://bucket/mcp/market:data/year=2024/month=12/day=03/hour=10/minute=31/part-uuid.jsonl.gz
s3://bucket/mcp/sentiment:data/year=2024/month=12/day=03/hour=10/minute=30/part-uuid.jsonl.gz
```

---

### Step 5: Document Test Results

**Purpose:** Record test execution for Phase 1.2 completion gate.

**Commands:**
```bash
cd /Users/kamii/888.mcp/888.MCP/mcp

# Create results directory
mkdir -p docs/test-results

# Save bash test results
./scripts/test_retrieval_phase_1_2.sh | tee docs/test-results/phase-1.2-bash-$(date +%Y-%m-%d).txt

# Save pytest results
pytest tests/integration/test_retrieval_accuracy.py -v | tee docs/test-results/phase-1.2-pytest-$(date +%Y-%m-%d).txt

# Save pytest HTML report
pytest tests/integration/test_retrieval_accuracy.py --html=docs/test-results/phase-1.2-report.html

# Update current-work.md
# Mark tasks 1.2.1-1.2.6 as complete ✅
```

**Document Template:**
```markdown
# Phase 1.2 Test Results - YYYY-MM-DD

## Summary

- **Date:** 2024-12-03
- **Tester:** [Your Name]
- **Environment:** Production (Render.com)
- **MCP URL:** https://mcp-server-xxx.onrender.com
- **S3 Configured:** Yes/No

## Test Results

### Bash Tests
- Total: 16
- Passed: 14
- Failed: 0
- Skipped: 2 (pagination not implemented)

### Python Tests
- Total: 20
- Passed: 18
- Failed: 0
- Skipped: 2 (S3 not configured / pagination)

## Task Completion

- [x] 1.2.1: Pair filtering tests ✅
- [x] 1.2.2: Time range tests ✅
- [x] 1.2.3: Limit tests ✅
- [x] 1.2.4: Time ordering tests ✅
- [ ] 1.2.5: Pagination tests ⏭️ (not implemented)
- [x] 1.2.6: Documentation ✅

## Notes

- All tests passed successfully
- Pagination will be implemented in future phase
- S3 data integrity verified (if applicable)

## Next Steps

- Proceed to Phase 1.3 (Kill-Switch Reliability)
```

---

## Troubleshooting

### Issue 1: All Tests Return 501

**Symptom:**
```
[TEST 1] Retrieve with BTC-ETH pair filter
⏭️  SKIP: S3 not configured
```

**Cause:** `S3_DATA_BUCKET` not configured in environment

**Solution:**
- **Expected:** This is OK if you're testing locally without S3
- **To Enable S3:**
  ```bash
  export S3_DATA_BUCKET="your-bucket-name"
  export AWS_ACCESS_KEY_ID="AKIA..."
  export AWS_SECRET_ACCESS_KEY="..."
  export AWS_REGION="us-east-1"
  ```

---

### Issue 2: No Test Data Found (Count = 0)

**Symptom:**
```
Retrieved 0 messages for BTC-ETH
```

**Cause:** Test data not seeded or archiver hasn't flushed yet

**Solution:**
1. Seed test data: `python scripts/seed_test_data.py`
2. Wait 60-90 seconds for archiver to flush
3. Check archiver logs: `./scripts/render_status.sh worker-logs`
4. Re-run tests

---

### Issue 3: Tests Timeout

**Symptom:**
```
requests.exceptions.ReadTimeout: HTTPSConnectionPool(...): Read timed out.
```

**Cause:** Server slow or large query

**Solution:**
1. Reduce limit: `{"limit": 100}` instead of `{"limit": 1000}`
2. Use narrower time ranges
3. Check server health: `curl $MCP_URL/health`

---

### Issue 4: Pagination Tests Skipped

**Symptom:**
```
⏭️  SKIP: Cursor-based pagination not implemented yet
```

**Cause:** Feature not yet implemented (expected)

**Solution:**
- **This is expected** - Task 1.2.5 documents current state
- Mark as documented limitation
- Implement in future phase if needed

---

## Success Criteria

Phase 1.2 is **COMPLETE** when:

- [x] **1.2.1**: Pair filtering works for BTC-ETH, BTC-USD, invalid pairs ✅
- [x] **1.2.2**: Time range filtering works for 1min, 7-day, 30-day windows ✅
- [x] **1.2.3**: Limit parameter works for 1, 10, 100, 1000, and rejects >1000 ✅
- [x] **1.2.4**: Messages sorted by timestamp (ascending) ✅
- [x] **1.2.5**: Pagination documented (not implemented, manual workaround provided) ✅
- [x] **1.2.6**: Retrieval semantics documented ([RETRIEVAL_SEMANTICS.md](RETRIEVAL_SEMANTICS.md)) ✅

---

## Files Created

| File | Purpose |
|------|---------|
| [tests/integration/test_retrieval_accuracy.py](../mcp/tests/integration/test_retrieval_accuracy.py) | Pytest test suite (20 tests) |
| [scripts/test_retrieval_phase_1_2.sh](../mcp/scripts/test_retrieval_phase_1_2.sh) | Bash test suite (16 tests) |
| [scripts/seed_test_data.py](../mcp/scripts/seed_test_data.py) | Test data seeding utility |
| [RETRIEVAL_SEMANTICS.md](RETRIEVAL_SEMANTICS.md) | Complete retrieval documentation |
| [PHASE_1_2_TESTING_GUIDE.md](PHASE_1_2_TESTING_GUIDE.md) | This guide |

---

## Next Phase

After completing Phase 1.2, proceed to:

**Phase 1.3 - Kill-Switch & Control Channel Reliability**
- [current-work.md](../.claude/resources/current-work.md#L808-L824)

---

## Related Documentation

- [RETRIEVAL_SEMANTICS.md](RETRIEVAL_SEMANTICS.md) - Detailed retrieval API docs
- [current-work.md](../.claude/resources/current-work.md) - Current task tracking
- [WORK_LOG.md](../WORK_LOG.md) - Complete work history
- [CLAUDE.md](../.claude/CLAUDE.md) - System architecture

---

**Guide Version:** 1.0
**Last Updated:** 2024-12-03
**Status:** ✅ Ready for Execution
