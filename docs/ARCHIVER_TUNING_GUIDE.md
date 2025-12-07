# Archiver Tuning Guide

**Version:** 1.0
**Last Updated:** 2025-12-03
**Audience:** Operations, DevOps, Future Developers

---

## Purpose

This guide helps you tune the MCP archiver for different workloads, troubleshoot performance issues, and optimize costs.

---

## Current Production Configuration

### Recommended Defaults (Phase 2.2 Optimized)

```bash
ARCHIVE_ENABLED=true
ARCHIVE_BATCH_SIZE=200        # Messages per batch
ARCHIVE_FLUSH_INTERVAL=60     # Seconds between time-based flushes
S3_DATA_BUCKET=mcp-data-prod-kamesh.888
AWS_DEFAULT_REGION=eu-north-1
Storage Format: JSONL.gz
```

### Why These Values?

- **Batch Size 200:** Optimal balance between cost (49% savings vs 100) and freshness (~40s latency)
- **Flush Interval 60s:** Safety net for low-traffic periods, prevents unbounded staleness
- **JSONL.gz:** Simple, proven, universally compatible, cheap enough at current scale

---

## Understanding Archiver Behavior

### Flush Triggers

The archiver flushes (uploads to S3) when **EITHER** condition is met:

1. **Batch Full:** Queue reaches `ARCHIVE_BATCH_SIZE` messages
2. **Time Expired:** `ARCHIVE_FLUSH_INTERVAL` seconds since last flush

### Example Behavior

**Scenario 1: High Traffic (10 msg/sec, batch=200)**
- Time to fill batch: 200 msgs / 10 msg/sec = **20 seconds**
- Trigger: **Batch full** (before 60s timer expires)
- Flush frequency: Every ~20 seconds
- Files per hour: ~180 files

**Scenario 2: Low Traffic (1 msg/sec, batch=200)**
- Messages in 60s: 1 msg/sec × 60s = **60 messages**
- Trigger: **Time expired** (batch not full)
- Flush frequency: Every 60 seconds
- Files per hour: 60 files

**Scenario 3: No Traffic**
- Trigger: None (no flushes if no messages)
- Files: 0

---

## Tuning Parameters

### 1. ARCHIVE_BATCH_SIZE

**Controls:** Messages per S3 file

**Valid Range:** 10 - 10,000

| Value | Use Case | Trade-offs |
|-------|----------|------------|
| **50** | Real-time systems, low latency required | High S3 costs, many small files |
| **100** | Balanced (previous default) | Moderate costs, good freshness |
| **200** | **Production recommended** | Optimal cost/performance, 40s freshness |
| **500** | High-volume, cost-sensitive | Low costs, acceptable staleness (90s) |
| **1000** | Batch processing, non-real-time | Minimal costs, 2-3 min staleness |

### 2. ARCHIVE_FLUSH_INTERVAL

**Controls:** Maximum time before forced flush

**Valid Range:** 10 - 600 seconds

| Value | Use Case | Trade-offs |
|-------|----------|------------|
| **30s** | Very time-sensitive data | More frequent uploads |
| **60s** | **Production recommended** | Good balance, safety net |
| **120s** | Cost optimization | Acceptable for most use cases |
| **300s** (5 min) | Batch processing | Only for non-time-sensitive data |

---

## How to Tune for Your Workload

### Step 1: Understand Your Load Pattern

**Measure your message rate:**

```bash
# Count messages published in last hour
curl -s -H "x-api-key: $MCP_API_KEY" "$MCP_URL/tool/get_status" | \
  jq '.channels'

# Estimate from S3 files
aws s3 ls s3://mcp-data-prod-kamesh.888/mcp/market_data/ --recursive | \
  grep "$(date +%Y-%m-%d)" | \
  wc -l
```

**Calculate average rate:**
```
Messages per second = (Total messages) / (Time period in seconds)
```

### Step 2: Calculate Optimal Batch Size

**Formula:**
```
Optimal Batch Size = Message Rate × Target Freshness (seconds)
```

**Examples:**

| Message Rate | Target Freshness | Optimal Batch |
|--------------|------------------|---------------|
| 5 msg/sec | 30 seconds | 150 |
| 5 msg/sec | 60 seconds | 300 |
| 10 msg/sec | 30 seconds | 300 |
| 10 msg/sec | 60 seconds | 600 |

### Step 3: Set Flush Interval

**Rule of Thumb:**
```
Flush Interval = 2 × (Batch Size / Average Message Rate)
```

This ensures time-based flushing only happens during low-traffic periods.

**Example:**
- Batch Size: 200
- Avg Rate: 5 msg/sec
- Flush Interval: 2 × (200 / 5) = 2 × 40 = **80 seconds** → Round to **60-90s**

### Step 4: Test & Validate

```bash
# 1. Update configuration
export ARCHIVE_BATCH_SIZE=200
export ARCHIVE_FLUSH_INTERVAL=60

# 2. Restart services (if local)
docker-compose restart mcp-server

# 3. Inject test load
cd /Users/kamii/888.mcp/888.MCP/mcp
./scripts/inject_test_load.sh --count 1000 --rate 10

# 4. Wait for flushes
sleep 120

# 5. Check S3 results
aws s3 ls s3://mcp-data-prod-kamesh.888/mcp/market_data/ --recursive | \
  grep "$(date +%Y-%m-%d)" | \
  tail -10
```

---

## Cost Optimization

### S3 Cost Breakdown

**PUT Requests:** $0.005 per 1,000 requests (eu-north-1)
**Storage:** $0.023 per GB/month (eu-north-1)

### Cost Calculator

**Daily S3 PUTs:**
```
PUTs/day = (Daily Messages) / (Batch Size)
```

**Monthly PUT Cost:**
```
Cost/month = (PUTs/day × 30) × ($0.005 / 1000)
```

**Example (475,000 msgs/day):**

| Batch Size | PUTs/day | Monthly Cost |
|------------|----------|--------------|
| 100 | 4,750 | $0.71 |
| 200 | 2,375 | $0.36 |
| 500 | 950 | $0.14 |

### When to Optimize for Cost

**Threshold:** Monthly S3 costs > $5

**Actions:**
1. Increase `ARCHIVE_BATCH_SIZE` to 500-1000
2. Consider Parquet format (2x compression)
3. Implement lifecycle policies (archive to Glacier after 30 days)

---

## Performance Monitoring

### Key Metrics to Track

**1. Queue Depth:**
```bash
# Check current queue depth
curl -s -H "x-api-key: $MCP_API_KEY" "$MCP_URL/tool/get_status" | \
  jq '.archiver.queue_depth'
```

**Healthy:** 0-10
**Warning:** 50-100
**Critical:** >100 (increase batch size or fix S3 issues)

**2. Upload Frequency:**
```bash
# Count S3 uploads in last hour
aws s3 ls s3://mcp-data-prod-kamesh.888/mcp/ --recursive | \
  awk -v since="$(date -u -v-1H +%Y-%m-%d)" '$1 >= since' | \
  wc -l
```

**3. Average File Size:**
```bash
aws s3 ls s3://mcp-data-prod-kamesh.888/mcp/ --recursive | \
  grep "$(date +%Y-%m-%d)" | \
  awk '{sum+=$3; count++} END {print sum/count/1024 "KB"}'
```

**Optimal:** 10 KB - 1 MB
**Too Small:** < 10 KB (increase batch size)
**Too Large:** > 10 MB (decrease batch size)

### Troubleshooting

**Problem:** Queue depth growing unbounded

**Causes:**
- S3 upload failures (check credentials, bucket permissions)
- Batch size too large for traffic rate
- Network issues

**Solutions:**
1. Check S3 credentials and bucket access
2. Reduce batch size temporarily
3. Check server logs for errors

**Problem:** Too many small files in S3

**Cause:** Batch size too small for traffic rate

**Solution:** Increase `ARCHIVE_BATCH_SIZE` to 200-500

**Problem:** Data freshness > 5 minutes

**Cause:** Batch size too large or flush interval too long

**Solution:**
1. Decrease `ARCHIVE_BATCH_SIZE` to 100-150
2. Decrease `ARCHIVE_FLUSH_INTERVAL` to 30-45s

---

## Format Migration: JSONL.gz → Parquet

### When to Migrate

**Triggers:**
- Monthly storage costs > $5
- Storage > 10 GB/month
- Brain agent needs complex analytics
- After Phase 7 (production stable)

### Migration Steps

**Phase 1: Implement Parquet Writer**

1. Add dependency:
```bash
# requirements.txt
pyarrow>=10.0.0
```

2. Modify `mcp/uploader/archiver.py`:
```python
import pyarrow as pa
import pyarrow.parquet as pq

def _write_parquet(self, batch, s3_path):
    # Convert batch to PyArrow table
    data = [msg['message'] for msg in batch]
    table = pa.Table.from_pylist(data)

    # Write to BytesIO buffer
    buffer = io.BytesIO()
    pq.write_table(table, buffer, compression='snappy')

    # Upload to S3
    self.s3_client.put_object(
        Bucket=self.bucket_name,
        Key=s3_path,
        Body=buffer.getvalue()
    )
```

**Phase 2: Test Parquet Format**

```bash
# 1. Enable Parquet (add env var)
ARCHIVE_FORMAT=parquet

# 2. Test locally
docker-compose up -d
./scripts/inject_test_load.sh --count 1000

# 3. Verify Parquet files in S3
aws s3 ls s3://mcp-data-prod-kamesh.888/mcp/market_data/ --recursive | \
  grep ".parquet"

# 4. Test reading Parquet
python3 -c "
import pyarrow.parquet as pq
table = pq.read_table('s3://bucket/path/file.parquet')
print(table.to_pandas())
"
```

**Phase 3: Gradual Rollout**

1. Write both JSONL.gz and Parquet for 1 week
2. Verify Brain agent can read Parquet
3. Switch to Parquet-only
4. Archive old JSONL.gz files

---

## Configuration Reference

### Environment Variables

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `ARCHIVE_ENABLED` | boolean | `false` | Enable/disable archiving |
| `ARCHIVE_BATCH_SIZE` | integer | `100` | Messages per batch |
| `ARCHIVE_FLUSH_INTERVAL` | integer | `60` | Flush interval (seconds) |
| `S3_DATA_BUCKET` | string | - | S3 bucket name (required) |
| `AWS_DEFAULT_REGION` | string | `eu-north-1` | AWS region |
| `AWS_ACCESS_KEY_ID` | string | - | AWS credentials |
| `AWS_SECRET_ACCESS_KEY` | string | - | AWS credentials |

### Quick Reference

**Production (Recommended):**
```bash
ARCHIVE_ENABLED=true
ARCHIVE_BATCH_SIZE=200
ARCHIVE_FLUSH_INTERVAL=60
```

**Real-Time (Low Latency):**
```bash
ARCHIVE_BATCH_SIZE=100
ARCHIVE_FLUSH_INTERVAL=30
```

**Cost-Optimized:**
```bash
ARCHIVE_BATCH_SIZE=500
ARCHIVE_FLUSH_INTERVAL=120
```

**Batch Processing (Non-Real-Time):**
```bash
ARCHIVE_BATCH_SIZE=1000
ARCHIVE_FLUSH_INTERVAL=300
```

---

## Scaling Guidelines

### Current Capacity (Batch=200, Interval=60s)

**Can Handle:**
- Sustained load: up to 20 msg/sec
- Peak load: up to 50 msg/sec (short bursts)
- Daily volume: up to 1.7M messages

### When to Scale Up

**Symptoms:**
- Queue depth consistently > 50
- Data freshness > 2 minutes
- S3 upload backlog growing

**Actions:**
1. Increase `ARCHIVE_BATCH_SIZE` to 500-1000
2. Add more archiver workers (if using background service)
3. Consider sharding by collection type

### When to Scale Down

**Symptoms:**
- Very low traffic (< 1 msg/sec)
- Many small files (< 10 KB)
- Cost concerns

**Actions:**
1. Decrease `ARCHIVE_BATCH_SIZE` to 50-100
2. Increase `ARCHIVE_FLUSH_INTERVAL` to 120-300s

---

## Related Documentation

- [PHASE_2_2_ANALYSIS_AND_RECOMMENDATIONS.md](PHASE_2_2_ANALYSIS_AND_RECOMMENDATIONS.md) - Full optimization analysis
- [ARCHIVER_BASELINE_CONFIG.md](ARCHIVER_BASELINE_CONFIG.md) - Original baseline documentation
- [CLAUDE.md](../.claude/CLAUDE.md) - System architecture rules
- [WORK_LOG.md](../WORK_LOG.md) - Phase 2.2 completion details

---

**Maintained By:** MCP Development Team
**Review Frequency:** Quarterly or after major load pattern changes
**Next Review:** After Brain agent deployment
