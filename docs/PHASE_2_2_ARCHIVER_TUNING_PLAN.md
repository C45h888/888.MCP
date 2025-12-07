# Phase 2.2: Archiver Parameter Tuning - Implementation Plan

**Date Created:** 2025-12-03
**Status:** PLANNING
**Priority:** P1-HIGH (Performance Optimization)
**Estimated Duration:** 1 day

---

## 📋 Table of Contents

1. [Objectives](#objectives)
2. [Current Configuration](#current-configuration)
3. [Baseline Performance](#baseline-performance)
4. [Testing Workflow](#testing-workflow)
5. [Parameter Testing Matrix](#parameter-testing-matrix)
6. [Format Comparison](#format-comparison)
7. [Success Criteria](#success-criteria)
8. [Implementation Steps](#implementation-steps)

---

## 🎯 Objectives

**Primary Goals:**
1. Optimize archiver parameters for production workload
2. Compare JSONL.gz vs Parquet format (performance, cost, size)
3. Determine optimal batch size and flush interval
4. Document tuning guidelines for future scaling
5. Choose production-ready defaults

**Non-Goals:**
- Change core archiver architecture
- Add new storage formats beyond Parquet/JSONL
- Modify S3 bucket structure (Hive partitioning stays)

---

## 🔧 Current Configuration

### Archiver Parameters (Default)

| Parameter | Current Value | Source | Adjustable |
|-----------|---------------|--------|------------|
| `ARCHIVE_ENABLED` | `true` | Environment | ✅ Yes |
| `ARCHIVE_BATCH_SIZE` | `100` | Default | ✅ Yes |
| `ARCHIVE_FLUSH_INTERVAL` | `60s` | Default | ✅ Yes |
| `S3_DATA_BUCKET` | `mcp-data-prod-kamesh.888` | Environment | ❌ No |
| `AWS_DEFAULT_REGION` | `eu-north-1` | Environment | ❌ No |
| Storage Format | `JSONL.gz` | Hardcoded | ⚠️ Requires code change |

### File Output Format

**Current:** Hive-style partitioned JSONL.gz
```
s3://bucket/mcp/{collection}/year=YYYY/month=MM/day=DD/hour=HH/minute=MM/part-{ts}.jsonl.gz
```

**Compression:** gzip (level 6 default)

---

## 📊 Baseline Performance

### From Phase B (Load Testing - Nov 2025)

**Test Configuration:**
- Messages sent: 100
- Success rate: 100%
- Throughput: 2.63 msg/sec
- Avg response time: 0.352s
- Queue depth: 0 (stable)

**Key Observations:**
- ✅ Archiver kept up with incoming load (queue never grew)
- ✅ No message loss or backpressure
- ✅ Current defaults (100 msgs, 60s) sufficient for test load
- ⚠️ Real production load unknown (need projections)

### From Phase 1.1 (Archiver Stability)

**Multi-Day Observations:**
- Archiver stable over multiple days
- No memory leaks detected
- S3 uploads successful
- Hive partitioning correct
- Local fallback working

### Current Production Characteristics

**Expected Message Rates (Projection):**
- `market:data`: 1-10 msg/sec (price ticks from exchanges)
- `sentiment:data`: 0.1-1 msg/sec (news, social media)
- `agent:signal`: 0.01-0.1 msg/sec (Brain agent trades)

**Total Projected:** ~1-11 msg/sec peak, ~3-5 msg/sec average

**Daily Volume Estimate:**
- Peak: ~950,400 messages/day
- Average: ~259,200-432,000 messages/day

---

## 🔬 Testing Workflow

### Workflow Overview

```
1. BASELINE MEASUREMENT
   ↓
2. PARAMETER EXPERIMENTS (JSONL.gz)
   ↓
3. FORMAT COMPARISON (JSONL.gz vs Parquet)
   ↓
4. COST ANALYSIS
   ↓
5. OPTIMAL CONFIGURATION SELECTION
   ↓
6. DOCUMENTATION & DEPLOYMENT
```

### Testing Approach

**Method:** Controlled load tests with varying configurations

**Test Environment:**
- Production server (Render.com)
- Real S3 bucket (mcp-data-prod-kamesh.888)
- Real Redis instance
- Controlled message injection

**Test Duration:** 5-10 minutes per configuration
**Metrics Collection:** Queue depth, upload latency, file size, S3 costs

---

## 🧪 Parameter Testing Matrix

### Experiment 1: Batch Size Impact

**Goal:** Determine optimal messages per batch

**Variables:**
- Batch sizes: 50, 100, 200, 500, 1000
- Flush interval: Fixed at 60s
- Format: JSONL.gz

**Test Procedure:**
```bash
# For each batch size:
1. Set ARCHIVE_BATCH_SIZE={size}
2. Restart MCP server
3. Inject 1000 messages at 10 msg/sec
4. Measure:
   - Upload frequency (uploads/min)
   - File size (bytes/file)
   - Queue depth (max)
   - Upload latency (seconds)
   - S3 PUT request count
```

**Expected Results:**
- Smaller batches = More frequent uploads = More PUT requests = Higher S3 cost
- Larger batches = Fewer uploads = Larger files = Lower S3 cost
- Optimal: Balance between latency and cost

**Success Metrics:**
- Queue depth stays near 0
- Upload latency < 5s
- File size: 10KB - 1MB range (optimal for S3)

---

### Experiment 2: Flush Interval Impact

**Goal:** Determine optimal time between flushes

**Variables:**
- Flush intervals: 30s, 60s, 120s, 300s (5min)
- Batch size: Fixed at 100
- Format: JSONL.gz

**Test Procedure:**
```bash
# For each flush interval:
1. Set ARCHIVE_FLUSH_INTERVAL={interval}
2. Restart MCP server
3. Inject messages at 5 msg/sec for 10 minutes
4. Measure:
   - Time to first upload
   - Max queue depth
   - Average upload frequency
   - Data freshness (time from publish to S3)
```

**Expected Results:**
- Shorter intervals = More frequent uploads = Fresher data = Higher cost
- Longer intervals = Fewer uploads = Stale data = Lower cost
- Optimal: Balance between freshness and cost

**Success Metrics:**
- Queue growth rate < batch size / interval
- Data freshness < 5 minutes acceptable
- No queue overflow

---

### Experiment 3: Combined Optimization

**Goal:** Find optimal batch size + flush interval combination

**Approach:** Grid search over promising candidates

**Candidates (batch_size, flush_interval):**
1. `(50, 30s)` - Low latency, high frequency
2. `(100, 60s)` - Current defaults (baseline)
3. `(200, 60s)` - Larger batches, same interval
4. `(100, 120s)` - Same batches, longer interval
5. `(500, 120s)` - Large batches, long interval

**Test Procedure:**
```bash
# For each configuration:
1. Set ARCHIVE_BATCH_SIZE and ARCHIVE_FLUSH_INTERVAL
2. Restart MCP server
3. Inject 2000 messages at 10 msg/sec (200 seconds)
4. Wait 5 minutes for final flushes
5. Measure:
   - Total S3 uploads
   - Total S3 storage used (MB)
   - Max queue depth
   - P95 upload latency
   - Estimated daily S3 PUT cost
```

**Cost Estimation Formula:**
```
Daily PUT requests = (Daily messages) / (Batch size)
Daily PUT cost = Daily PUT requests × $0.005 per 1000 PUTs

Example (100k msgs/day, batch=100):
  PUTs/day = 100,000 / 100 = 1,000
  Cost/day = 1,000 × $0.005 / 1000 = $0.005/day = $1.83/year
```

---

## 📦 Format Comparison: JSONL.gz vs Parquet

### Experiment 4: Storage Format Evaluation

**Goal:** Compare JSONL.gz vs Parquet for archival storage

#### Test Setup

**Test Data:**
- 10,000 market:data messages
- 1,000 sentiment:data messages
- Realistic message sizes (~200-500 bytes)

#### Comparison Dimensions

| Dimension | JSONL.gz | Parquet | Winner |
|-----------|----------|---------|--------|
| **Write Performance** | ⏱️ Fast (stream) | ⏱️ Slower (columnar) | ? |
| **Compression Ratio** | 📦 Good (3-5x) | 📦 Excellent (5-10x) | ? |
| **Read Performance** | 📖 Sequential | 📖 Columnar (faster for analytics) | ? |
| **Partial Reads** | ❌ Must decompress all | ✅ Read specific columns | ? |
| **Compatibility** | ✅ Universal | ⚠️ Needs libraries | ? |
| **Query Performance** | ⏱️ Scan all | ⏱️ Predicate pushdown | ? |
| **Simplicity** | ✅ Very simple | ⚠️ More complex | ? |

#### Test Procedure

**Part A: Write Performance**
```bash
# JSONL.gz
1. Write 10,000 messages to JSONL.gz
2. Measure: Write time, CPU usage, file size

# Parquet
1. Write same 10,000 messages to Parquet
2. Measure: Write time, CPU usage, file size
```

**Part B: Read Performance**
```bash
# JSONL.gz
1. Read all messages (full scan)
2. Read messages for specific pair (filter after load)
3. Read 1-hour time window
4. Measure: Read time, memory usage

# Parquet
1. Read all messages
2. Read specific pair (predicate pushdown)
3. Read 1-hour time window
4. Measure: Read time, memory usage
```

**Part C: Compression Analysis**
```bash
# For both formats:
1. Calculate compression ratio
2. Measure S3 storage cost ($/GB/month)
3. Calculate cost for 1TB of data
```

#### Decision Matrix

**Choose JSONL.gz if:**
- ✅ Simplicity is critical
- ✅ Write performance is bottleneck
- ✅ Sequential reads are primary use case
- ✅ Universal compatibility required

**Choose Parquet if:**
- ✅ Storage costs are significant concern
- ✅ Analytical queries are common
- ✅ Column-level access needed
- ✅ Brain agent does complex filtering

**Recommendation Pending:** Test results required

---

## 📈 Success Criteria

### Performance Targets

| Metric | Target | Acceptable | Critical |
|--------|--------|------------|----------|
| Queue Depth | 0-10 | < 50 | < 100 |
| Upload Latency (P95) | < 2s | < 5s | < 10s |
| Data Freshness | < 2min | < 5min | < 10min |
| Memory Usage | < 200MB | < 500MB | < 1GB |
| CPU Usage | < 10% | < 25% | < 50% |

### Cost Targets

| Resource | Target | Acceptable | Max |
|----------|--------|------------|-----|
| S3 PUT Requests | < 5K/day | < 20K/day | < 50K/day |
| S3 Storage | < 1GB/month | < 10GB/month | < 50GB/month |
| Daily S3 Cost | < $0.01 | < $0.05 | < $0.10 |

### Quality Targets

- ✅ Zero message loss
- ✅ No queue overflows
- ✅ Correct Hive partitioning
- ✅ All uploads succeed (or retry)
- ✅ Graceful degradation on S3 failure

---

## 🚀 Implementation Steps

### Step 1: Document Current State (30 min)

**Task 1.1:** Capture current configuration
```bash
# Export current settings
echo "ARCHIVE_BATCH_SIZE=$(grep ARCHIVE_BATCH_SIZE mcp/uploader/archiver.py)"
echo "ARCHIVE_FLUSH_INTERVAL=$(grep ARCHIVE_FLUSH_INTERVAL mcp/uploader/archiver.py)"
```

**Task 1.2:** Measure baseline performance
```bash
# Run baseline test with current defaults
cd /Users/kamii/888.mcp/888.MCP/mcp
./scripts/test_archiver_baseline.sh  # To be created
```

**Deliverable:**
- `docs/ARCHIVER_BASELINE_CONFIG.md` - Current state documentation

---

### Step 2: Parameter Experiments (2-3 hours)

**Task 2.1:** Batch size experiments
```bash
# Test batch sizes: 50, 100, 200, 500, 1000
for size in 50 100 200 500 1000; do
  export ARCHIVE_BATCH_SIZE=$size
  ./scripts/test_archiver_batch_size.sh $size
done
```

**Task 2.2:** Flush interval experiments
```bash
# Test intervals: 30, 60, 120, 300
for interval in 30 60 120 300; do
  export ARCHIVE_FLUSH_INTERVAL=$interval
  ./scripts/test_archiver_flush_interval.sh $interval
done
```

**Task 2.3:** Combined optimization
```bash
# Test optimal combinations
./scripts/test_archiver_combined.sh
```

**Deliverables:**
- Test results CSV with all metrics
- Graphs showing batch size vs cost, latency vs freshness
- Optimal configuration recommendation

---

### Step 3: Format Comparison (2-3 hours)

**Task 3.1:** Implement Parquet support (if needed)
```python
# Add Parquet writer to archiver.py
# Use pyarrow library
```

**Task 3.2:** Run format comparison tests
```bash
# Compare JSONL.gz vs Parquet
./scripts/test_format_comparison.sh
```

**Task 3.3:** Analyze results
```bash
# Compare:
# - File sizes
# - Write performance
# - Read performance
# - Query performance
# - S3 costs
```

**Deliverables:**
- Format comparison report
- Size/performance/cost analysis
- Recommendation with justification

---

### Step 4: Cost Analysis (1 hour)

**Task 4.1:** Calculate projected costs
```python
# For each configuration:
# - Daily PUT requests
# - Daily storage growth
# - Monthly S3 costs
# - Annual projections
```

**Task 4.2:** Create cost comparison table
```markdown
| Configuration | PUTs/day | Storage/mo | Cost/mo | Cost/year |
|---------------|----------|------------|---------|-----------|
| (50, 30s)     | 20,000   | 5GB        | $0.12   | $1.44     |
| (100, 60s)    | 10,000   | 5GB        | $0.06   | $0.72     |
| (500, 120s)   | 2,000    | 5GB        | $0.02   | $0.24     |
```

**Deliverable:**
- Cost analysis spreadsheet
- Break-even analysis

---

### Step 5: Choose Production Defaults (30 min)

**Decision Factors:**
1. Performance (latency, queue depth)
2. Cost (S3 PUTs, storage)
3. Data freshness requirements
4. Simplicity (operational overhead)
5. Scalability (headroom for growth)

**Recommendation Template:**
```markdown
## Production Configuration Recommendation

**Chosen Configuration:**
- ARCHIVE_BATCH_SIZE: {value}
- ARCHIVE_FLUSH_INTERVAL: {value}
- Storage Format: {JSONL.gz or Parquet}

**Justification:**
- Performance: {analysis}
- Cost: {analysis}
- Trade-offs: {analysis}

**Expected Metrics:**
- Daily S3 PUTs: {count}
- Daily storage growth: {MB}
- Monthly cost: ${amount}
- Data freshness: {minutes}
```

---

### Step 6: Documentation (1 hour)

**Task 6.1:** Create tuning guide
```bash
# Create docs/ARCHIVER_TUNING_GUIDE.md
# - Current configuration
# - How to tune parameters
# - When to scale up/down
# - Cost optimization tips
```

**Task 6.2:** Update DEVELOPMENT.md
```markdown
# Add section on archiver tuning
# - Environment variables
# - Performance considerations
# - Cost implications
```

**Task 6.3:** Update deployment docs
```markdown
# Add production defaults to:
# - render.yaml
# - docker-compose.yml
# - Environment setup guide
```

**Deliverables:**
- `docs/ARCHIVER_TUNING_GUIDE.md`
- Updated `docs/DEVELOPMENT.md`
- Deployment configuration files

---

## 📊 Testing Scripts to Create

### 1. `scripts/test_archiver_baseline.sh`
- Measure current performance with default settings
- Output: baseline metrics JSON

### 2. `scripts/test_archiver_batch_size.sh`
- Test specific batch size configuration
- Args: batch_size
- Output: performance metrics

### 3. `scripts/test_archiver_flush_interval.sh`
- Test specific flush interval configuration
- Args: flush_interval
- Output: performance metrics

### 4. `scripts/test_archiver_combined.sh`
- Grid search over promising configurations
- Output: comparison table

### 5. `scripts/test_format_comparison.sh`
- Compare JSONL.gz vs Parquet
- Output: format comparison report

### 6. `scripts/inject_test_load.sh`
- Inject controlled test load
- Args: rate (msg/sec), duration (seconds), collection
- Output: injection statistics

### 7. `scripts/analyze_archiver_results.py`
- Parse test results
- Generate visualizations
- Output: graphs and recommendations

---

## 🎯 Expected Outcomes

### Primary Deliverables

1. **Optimal Configuration File**
   - Production-ready archiver settings
   - Documented rationale

2. **Tuning Guide**
   - How to adjust parameters for different workloads
   - Cost optimization strategies

3. **Format Recommendation**
   - JSONL.gz vs Parquet decision
   - Migration plan (if changing format)

4. **Cost Projections**
   - Daily/monthly/annual S3 costs
   - Scaling cost models

5. **Performance Benchmarks**
   - Baseline vs optimized metrics
   - Headroom analysis

### Success Definition

**Phase 2.2 is complete when:**
- ✅ All experiments executed
- ✅ Data analyzed and documented
- ✅ Production defaults chosen
- ✅ Tuning guide published
- ✅ Configuration deployed and validated
- ✅ Performance improvements measured

---

## 📝 Notes

### Key Considerations

1. **Don't Over-Optimize Early:** Current load is low, optimize for projected production load
2. **Cost is Secondary:** Performance and reliability > minor cost savings
3. **Keep it Simple:** Prefer simpler solutions (JSONL.gz) unless Parquet provides compelling benefits
4. **Measure Twice, Cut Once:** Thorough testing before changing production defaults
5. **Document Everything:** Future team members need to understand tuning rationale

### Risks

- **Risk:** Changing parameters without sufficient testing
  - **Mitigation:** Comprehensive test suite before production changes

- **Risk:** Optimizing for wrong workload patterns
  - **Mitigation:** Use realistic projections, build in headroom

- **Risk:** Parquet implementation bugs
  - **Mitigation:** Extensive testing, phased rollout

---

## 🔗 Related Documents

- [CLAUDE.md](../.claude/CLAUDE.md) - Architecture rules
- [WORK_LOG.md](../WORK_LOG.md) - Phase tracking
- [current-work.md](../.claude/resources/current-work.md) - Task details
- Phase B results: Load testing metrics
- Phase 1.1 results: Archiver stability validation

---

**Document Version:** 1.0
**Last Updated:** 2025-12-03
**Next Review:** After Phase 2.2 completion
