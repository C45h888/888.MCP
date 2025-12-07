# Phase 2.2: Archiver Tuning - Execution Workflow

**Quick Reference Guide for Implementation**

---

## 🎯 Quick Start

**Goal:** Optimize archiver for production workload in 1 day

**Current Config:**
- Batch Size: 100 messages
- Flush Interval: 60 seconds
- Format: JSONL.gz
- Status: ✅ Working, needs optimization

**What We'll Do:**
1. Test different batch sizes & intervals
2. Compare JSONL.gz vs Parquet
3. Choose optimal production settings
4. Document tuning guidelines

---

## 📋 Execution Checklist

### Phase 1: Preparation (1 hour) ⏰

- [ ] **Document current baseline**
  - [ ] Capture current ARCHIVE_BATCH_SIZE (100)
  - [ ] Capture current ARCHIVE_FLUSH_INTERVAL (60s)
  - [ ] Document current S3 usage

- [ ] **Create test scripts**
  - [ ] `scripts/inject_test_load.sh` - Message injection
  - [ ] `scripts/measure_archiver.sh` - Metrics collection

- [ ] **Run baseline test**
  - [ ] Inject 1000 messages at 10 msg/sec
  - [ ] Record: queue depth, upload count, file sizes

---

### Phase 2: Batch Size Experiments (2 hours) ⏰

**Test Matrix:**
| Batch Size | Expected Behavior |
|------------|-------------------|
| 50 | More frequent, smaller files |
| 100 | Current baseline |
| 200 | Half the uploads |
| 500 | Large batches, rare uploads |
| 1000 | Maximum batch size |

**For Each Configuration:**

```bash
# 1. Update configuration
export ARCHIVE_BATCH_SIZE={size}

# 2. Restart server (or update Render config)
# Render: Dashboard → mcp-server → Environment → Update → Redeploy

# 3. Inject test load
./scripts/inject_test_load.sh --rate 10 --duration 120 --collection "market:data"

# 4. Wait for final flush
sleep 120

# 5. Collect metrics
./scripts/measure_archiver.sh > results/batch-${size}.json

# 6. Inspect S3 files
aws s3 ls s3://mcp-data-prod-kamesh.888/mcp/market_data/ --recursive | \
  grep "$(date +%Y-%m-%d)" | \
  awk '{sum+=$3; count++} END {print "Files:", count, "Avg size:", sum/count/1024 "KB"}'
```

**Metrics to Collect:**
- Total S3 uploads
- Avg file size (KB)
- Max queue depth
- Upload latency (P95)
- Total test duration

**Record in:** `results/batch_size_comparison.csv`

---

### Phase 3: Flush Interval Experiments (2 hours) ⏰

**Test Matrix:**
| Interval | Expected Behavior |
|----------|-------------------|
| 30s | More frequent, fresher data |
| 60s | Current baseline |
| 120s | Half the frequency |
| 300s | 5-minute batching |

**For Each Configuration:**

```bash
# 1. Update configuration
export ARCHIVE_FLUSH_INTERVAL={interval}

# 2. Restart server
# (Same as above)

# 3. Inject test load (slower, longer duration)
./scripts/inject_test_load.sh --rate 5 --duration 600 --collection "market:data"

# 4. Wait for final flush
sleep $((interval * 2))

# 5. Collect metrics
./scripts/measure_archiver.sh > results/interval-${interval}.json
```

**Key Metric:** Data freshness = (current_time - last_upload_time)

**Record in:** `results/flush_interval_comparison.csv`

---

### Phase 4: Combined Optimization (1 hour) ⏰

**Promising Configurations:**

| Config | Batch | Interval | Use Case |
|--------|-------|----------|----------|
| A | 50 | 30s | Low-latency, real-time |
| B | 100 | 60s | Balanced (current) |
| C | 200 | 60s | Larger batches |
| D | 500 | 120s | Cost-optimized |

**Test Best Candidates:**

```bash
# Test each configuration
for config in "50:30" "100:60" "200:60" "500:120"; do
  batch=$(echo $config | cut -d: -f1)
  interval=$(echo $config | cut -d: -f2)

  echo "Testing config: batch=$batch, interval=$interval"

  export ARCHIVE_BATCH_SIZE=$batch
  export ARCHIVE_FLUSH_INTERVAL=$interval

  # Restart & test
  # ... (same procedure as above)
done
```

**Decision Matrix:**

| Priority | Metric | Weight |
|----------|--------|--------|
| 1 | Queue stability (no overflow) | HIGH |
| 2 | Data freshness (< 5min) | MEDIUM |
| 3 | S3 cost (PUTs/day) | MEDIUM |
| 4 | File size (10KB-1MB optimal) | LOW |

---

### Phase 5: Format Comparison (2-3 hours) ⏰

#### Option A: JSONL.gz (Current)

**Pros:**
- ✅ Simple implementation (already working)
- ✅ Universal compatibility
- ✅ Fast writes
- ✅ No additional dependencies

**Cons:**
- ❌ Less compression
- ❌ Must read entire file for queries
- ❌ No column-level access

#### Option B: Parquet

**Pros:**
- ✅ Better compression (5-10x vs 3-5x)
- ✅ Columnar format (faster analytics)
- ✅ Predicate pushdown
- ✅ Industry standard for data lakes

**Cons:**
- ❌ Requires pyarrow library
- ❌ More complex implementation
- ❌ Slower writes
- ❌ Need schema management

**Test Procedure:**

```bash
# 1. Generate test dataset
./scripts/generate_test_data.sh --count 10000 --output test_data.json

# 2. Benchmark JSONL.gz
time python3 -c "
import json, gzip
with open('test_data.json') as f:
    data = json.load(f)
with gzip.open('test.jsonl.gz', 'wt') as f:
    for msg in data:
        f.write(json.dumps(msg) + '\n')
"
ls -lh test.jsonl.gz

# 3. Benchmark Parquet
time python3 -c "
import json, pyarrow as pa, pyarrow.parquet as pq
with open('test_data.json') as f:
    data = json.load(f)
table = pa.Table.from_pylist(data)
pq.write_table(table, 'test.parquet', compression='snappy')
"
ls -lh test.parquet

# 4. Compare sizes
echo "JSONL.gz size: $(ls -lh test.jsonl.gz | awk '{print $5}')"
echo "Parquet size: $(ls -lh test.parquet | awk '{print $5}')"
echo "Compression ratio: $(echo "scale=2; $(stat -f%z test.jsonl) / $(stat -f%z test.parquet)" | bc)"
```

**Decision Criteria:**

**Choose JSONL.gz if:**
- Simplicity is critical ✅
- Write performance matters most ✅
- Storage costs are negligible ✅

**Choose Parquet if:**
- Storage costs > $10/month ❌ (unlikely)
- Complex analytics queries needed ❌ (not yet)
- Compression ratio critical ❌ (storage cheap)

**Recommendation:** **STICK WITH JSONL.gz**
- Reason: Simplicity wins, costs are low, Brain agent not built yet
- Future: Can migrate to Parquet when storage costs become significant

---

### Phase 6: Cost Analysis (30 min) ⏰

**Cost Calculator:**

```python
# S3 Pricing (us-east-1, adjust for eu-north-1)
PUT_COST = 0.005 / 1000  # $0.005 per 1000 PUTs
STORAGE_COST = 0.023  # $0.023 per GB per month

# Example calculation
daily_messages = 100000  # Projected
batch_size = 100
flush_interval = 60

# Calculate daily PUTs
if batch_size > daily_messages:
    daily_puts = 1  # Only time-based flushes
else:
    daily_puts = daily_messages / batch_size

# Calculate costs
daily_put_cost = daily_puts * PUT_COST
monthly_put_cost = daily_put_cost * 30
annual_put_cost = monthly_put_cost * 12

print(f"Daily PUTs: {daily_puts:,.0f}")
print(f"Daily cost: ${daily_put_cost:.4f}")
print(f"Monthly cost: ${monthly_put_cost:.2f}")
print(f"Annual cost: ${annual_put_cost:.2f}")
```

**Run for all configurations:**

```bash
python3 scripts/calculate_costs.py \
  --daily-messages 100000 \
  --configurations "50:30,100:60,200:60,500:120" \
  --output results/cost_analysis.csv
```

**Target:** < $1/month for S3 PUTs (easily achievable)

---

### Phase 7: Final Decision & Documentation (1 hour) ⏰

**Decision Template:**

```markdown
## Production Configuration Decision

**Chosen Configuration:**
- ARCHIVE_BATCH_SIZE: {value}
- ARCHIVE_FLUSH_INTERVAL: {value}s
- Storage Format: JSONL.gz

**Performance Metrics:**
- Queue depth: {max_observed}
- Upload latency (P95): {value}s
- Data freshness: {value}min
- Files per day: {count}

**Cost Metrics:**
- Daily S3 PUTs: {count}
- Monthly S3 cost: ${amount}
- Storage growth: {MB}/day

**Justification:**
{2-3 sentences explaining why this configuration was chosen}

**Trade-offs Accepted:**
{List any compromises made}

**Scaling Headroom:**
{How much can load increase before reconfiguration needed}
```

**Create Documentation:**

1. **`docs/ARCHIVER_TUNING_GUIDE.md`**
   - How to tune parameters
   - When to scale up/down
   - Cost optimization tips

2. **Update `render.yaml`**
   ```yaml
   envVars:
     - key: ARCHIVE_BATCH_SIZE
       value: {chosen_value}
     - key: ARCHIVE_FLUSH_INTERVAL
       value: {chosen_value}
   ```

3. **Update `docker-compose.yml`**
   ```yaml
   environment:
     - ARCHIVE_BATCH_SIZE={chosen_value}
     - ARCHIVE_FLUSH_INTERVAL={chosen_value}
   ```

4. **Commit & Deploy**
   ```bash
   git add render.yaml docker-compose.yml docs/
   git commit -m "Phase 2.2: Optimize archiver parameters (batch={value}, interval={value}s)"
   git push origin main
   ```

---

## 📊 Results Template

**Fill this out as you go:**

### Batch Size Results

| Size | Uploads | Avg File Size | Max Queue | Latency | Cost/day |
|------|---------|---------------|-----------|---------|----------|
| 50   |         |               |           |         |          |
| 100  |         |               |           |         |          |
| 200  |         |               |           |         |          |
| 500  |         |               |           |         |          |
| 1000 |         |               |           |         |          |

**Winner:** _____ (Reason: _____________)

### Flush Interval Results

| Interval | Freshness | Uploads | Max Queue | Cost/day |
|----------|-----------|---------|-----------|----------|
| 30s      |           |         |           |          |
| 60s      |           |         |           |          |
| 120s     |           |         |           |          |
| 300s     |           |         |           |          |

**Winner:** _____ (Reason: _____________)

### Format Comparison

| Format | Write Time | File Size | Read Time | Complexity |
|--------|------------|-----------|-----------|------------|
| JSONL.gz |          |           |           | Simple     |
| Parquet  |          |           |           | Complex    |

**Winner:** _____ (Reason: _____________)

### Final Configuration

**Production Settings:**
```bash
ARCHIVE_BATCH_SIZE=_____
ARCHIVE_FLUSH_INTERVAL=_____
Storage Format: _____
```

**Expected Performance:**
- Queue depth: < _____
- Data freshness: < _____ minutes
- Daily S3 cost: $_____
- Monthly S3 cost: $_____

---

## 🚀 Quick Commands

### Test Current Configuration
```bash
cd /Users/kamii/888.mcp/888.MCP/mcp
export MCP_URL="https://mcp-server-7h8i.onrender.com"
export MCP_API_KEY="your-key"

# Inject 1000 messages
for i in {1..1000}; do
  curl -s -X POST "$MCP_URL/tool/publish" \
    -H "x-api-key: $MCP_API_KEY" \
    -H "Content-Type: application/json" \
    -d "{
      \"channel\": \"market:data\",
      \"message\": {
        \"schema_version\": \"v1\",
        \"timestamp\": $(date +%s),
        \"pair\": \"BTC-ETH\",
        \"price_btc\": $((30000 + RANDOM % 1000)),
        \"price_eth\": $((2000 + RANDOM % 100)),
        \"volume_btc\": $((RANDOM % 200))
      }
    }" > /dev/null

  # Rate limit: 10 msg/sec
  sleep 0.1
done

echo "✅ Injected 1000 messages"
```

### Check S3 Upload Results
```bash
# List recent uploads
aws s3 ls s3://mcp-data-prod-kamesh.888/mcp/market_data/ --recursive | \
  grep "$(date +%Y-%m-%d)" | tail -20

# Count today's files
aws s3 ls s3://mcp-data-prod-kamesh.888/mcp/market_data/ --recursive | \
  grep "$(date +%Y-%m-%d)" | wc -l

# Calculate total size
aws s3 ls s3://mcp-data-prod-kamesh.888/mcp/market_data/ --recursive | \
  grep "$(date +%Y-%m-%d)" | \
  awk '{sum+=$3} END {print "Total:", sum/1024/1024 "MB"}'
```

### Monitor Queue Depth
```bash
# Check queue depth in real-time
watch -n 1 "curl -s -H 'x-api-key: $MCP_API_KEY' '$MCP_URL/tool/get_status' | jq '.archiver.queue_depth'"
```

---

## ✅ Completion Checklist

Phase 2.2 is complete when:

- [ ] All batch size experiments run
- [ ] All flush interval experiments run
- [ ] Format comparison complete
- [ ] Cost analysis done
- [ ] Production configuration chosen
- [ ] Documentation created:
  - [ ] ARCHIVER_TUNING_GUIDE.md
  - [ ] render.yaml updated
  - [ ] docker-compose.yml updated
- [ ] Configuration deployed to production
- [ ] Validation tests pass
- [ ] WORK_LOG.md updated

---

**Ready to Start?** Begin with Phase 1 (Preparation) ⬆️
