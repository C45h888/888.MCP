# Archiver Baseline Configuration

**Date:** 2025-12-03
**Phase:** 2.2 - Archiver Parameter Tuning
**Purpose:** Document current configuration before optimization

---

## Current Configuration

### Environment Variables (Production)

| Variable | Current Value | Source |
|----------|---------------|--------|
| `ARCHIVE_ENABLED` | `true` | Render environment |
| `ARCHIVE_BATCH_SIZE` | `100` | Default (hardcoded) |
| `ARCHIVE_FLUSH_INTERVAL` | `60` seconds | Default (hardcoded) |
| `S3_DATA_BUCKET` | `mcp-data-prod-kamesh.888` | Render environment |
| `AWS_DEFAULT_REGION` | `eu-north-1` | Render environment |
| Storage Format | `JSONL.gz` | Hardcoded in archiver.py |

### Code Configuration

**File:** `mcp/uploader/archiver.py`

```python
# Line 44-45
self.batch_size = int(os.getenv("ARCHIVE_BATCH_SIZE", "100"))
self.flush_interval = int(os.getenv("ARCHIVE_FLUSH_INTERVAL", "60"))
```

### Archiver Behavior

**Flush Triggers:**
1. **Batch Full:** When queue reaches `ARCHIVE_BATCH_SIZE` messages
2. **Time Expired:** When `ARCHIVE_FLUSH_INTERVAL` seconds elapse since last flush

**S3 Upload Path Format:**
```
s3://{bucket}/mcp/{collection}/year=YYYY/month=MM/day=DD/hour=HH/minute=MM/part-{ts}-{count}.jsonl.gz
```

**Compression:** gzip (default compression level)

---

## Historical Performance

### From Phase B (Nov 2025)

**Load Test Results:**
- Messages sent: 100
- Success rate: 100%
- Throughput: 2.63 msg/sec
- Avg response time: 0.352s
- Queue depth: 0 (stable)

**Archiver Observations:**
- Queue remained at 0 throughout test
- No backpressure detected
- System handled load comfortably
- Current defaults sufficient for test load

### From Phase 1.1 (Multi-Day)

**Stability:**
- ✅ Archiver stable over multiple days
- ✅ No memory leaks
- ✅ S3 uploads successful
- ✅ Hive partitioning correct
- ✅ Local fallback working

---

## Projected Production Load

### Message Rate Estimates

| Channel | Estimated Rate | Peak Rate |
|---------|----------------|-----------|
| `market:data` | 3-5 msg/sec | 10 msg/sec |
| `sentiment:data` | 0.1-0.5 msg/sec | 1 msg/sec |
| `agent:signal` | 0.01-0.05 msg/sec | 0.1 msg/sec |
| **Total** | **3-6 msg/sec** | **~11 msg/sec** |

### Daily Volume Projections

**Average Load:**
- 3-6 msg/sec × 86,400 sec/day = **259,200 - 518,400 messages/day**

**Peak Load:**
- 11 msg/sec × 86,400 sec/day = **950,400 messages/day**

### Storage Projections

**Message Size Estimates:**
- market:data: ~200-300 bytes (JSON)
- sentiment:data: ~400-600 bytes (includes summary text)
- agent:signal: ~250-350 bytes

**Average:** ~300 bytes/message

**Daily Storage (uncompressed):**
- Average: 259,200 × 300 bytes = 77.76 MB/day
- Peak: 950,400 × 300 bytes = 285.12 MB/day

**With gzip compression (3-5x):**
- Average: 15-26 MB/day
- Peak: 57-95 MB/day

**Monthly Storage:**
- Average: 450-780 MB/month
- Peak: 1.7-2.85 GB/month

---

## Current S3 Usage

**Bucket:** `mcp-data-prod-kamesh.888`
**Region:** `eu-north-1`

**To be measured:** Actual file count and sizes from recent activity

---

## Optimization Targets

### Performance

| Metric | Current | Target | Max Acceptable |
|--------|---------|--------|----------------|
| Queue Depth | 0 | 0-10 | < 50 |
| Upload Latency | Unknown | < 2s | < 5s |
| Data Freshness | ~60s | < 120s | < 300s |

### Cost

| Metric | Projected (current) | Target | Max |
|--------|---------------------|--------|-----|
| Daily S3 PUTs | ~2,600-5,200 | < 5,000 | < 20,000 |
| Monthly S3 Cost | < $0.50 | < $1.00 | < $5.00 |

---

## Next Steps

1. ✅ Baseline documented
2. ⏳ Create test injection scripts
3. ⏳ Run baseline performance test
4. ⏳ Begin parameter experiments

---

**Document Version:** 1.0
**Last Updated:** 2025-12-03
