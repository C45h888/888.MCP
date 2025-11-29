# AWS CLI Setup Guide for MCP Server

**Generated:** 2025-11-28
**Purpose:** Configure AWS CLI for Phase 1.1 S3 inspection tasks
**Status:** ⏳ In Progress (requires user action)

---

## 📋 Setup Checklist

- [x] AWS CLI installer downloaded to `/tmp/AWSCLIV2.pkg`
- [x] AWS configuration directory created (`~/.aws/`)
- [x] Configuration files created with templates
- [x] S3 inspection script created (`scripts/inspect_s3.sh`)
- [ ] AWS CLI installed system-wide (requires sudo)
- [ ] Production credentials configured
- [ ] Connection tested

---

## 🚀 Step 1: Install AWS CLI (ACTION REQUIRED)

Run this command in your terminal:

```bash
sudo installer -pkg /tmp/AWSCLIV2.pkg -target /
```

**Verify installation:**
```bash
aws --version
# Expected output: aws-cli/2.x.x Python/3.x.x Darwin/24.6.0
```

---

## 🔑 Step 2: Configure Production Credentials (ACTION REQUIRED)

### Get Credentials from Render Dashboard:

1. Go to: https://dashboard.render.com
2. Select service: **`mcp-server`**
3. Click **"Environment"** tab
4. Copy the following values:
   - `AWS_ACCESS_KEY_ID`
   - `AWS_SECRET_ACCESS_KEY`
   - `S3_DATA_BUCKET` (note the bucket name)

### Edit Credentials File:

```bash
nano ~/.aws/credentials
```

Replace the placeholders in the `[production]` section:
```ini
[production]
aws_access_key_id = <PASTE-AWS_ACCESS_KEY_ID-HERE>
aws_secret_access_key = <PASTE-AWS_SECRET_ACCESS_KEY-HERE>
```

**Save and exit:** `Ctrl+X`, then `Y`, then `Enter`

### Set Environment Variables:

Add to your shell profile (`~/.zshrc` or `~/.bash_profile`):

```bash
# AWS CLI Configuration for MCP Server
export AWS_PROFILE=production
export AWS_DEFAULT_REGION=us-east-1
export S3_DATA_BUCKET="<your-bucket-name-from-render>"
```

**Reload shell:**
```bash
source ~/.zshrc  # or source ~/.bash_profile
```

---

## ✅ Step 3: Test Connection

### Test AWS Credentials:
```bash
aws sts get-caller-identity --profile production
```

**Expected output:**
```json
{
    "UserId": "AIDAXXXXXXXXXXXXXXXXX",
    "Account": "123456789012",
    "Arn": "arn:aws:iam::123456789012:user/mcp-server"
}
```

### Test S3 Bucket Access:
```bash
aws s3 ls --profile production
```

**Expected:** List of S3 buckets (should include your `S3_DATA_BUCKET`)

### Test Specific Bucket:
```bash
aws s3 ls s3://$S3_DATA_BUCKET/mcp/ --profile production
```

**Expected:** List of collections (`market:data/`, `sentiment:data/`, etc.)

---

## 🔍 Step 4: Run S3 Inspection Script

Once configured, test the inspection script:

```bash
cd /Users/kamii/888.mcp/888.MCP
./scripts/inspect_s3.sh
```

**Expected output:**
```
===========================================
S3 BUCKET INSPECTION - Phase 1.1
===========================================

Bucket: your-bucket-name
Profile: production
Date: Thu Nov 28 09:22:00 IST 2025

✓ AWS CLI installed and configured

===========================================
1. Market Data Objects (Task 1.1.2)
===========================================
Listing first 50 objects in mcp/market:data/...
...
```

---

## 🛠️ Alternative: MinIO Local Testing

If you want to test with MinIO locally (optional):

### Start MinIO:
```bash
docker-compose -f docker-compose.ci.yml up -d minio
```

### Test MinIO Connection:
```bash
aws s3 ls --profile minio-local --endpoint-url http://localhost:9000
```

### Seed Test Data:
```bash
python scripts/seed_minio.py
```

---

## 📝 Troubleshooting

### Issue: "Unable to locate credentials"
**Solution:** Verify `~/.aws/credentials` has correct format and permissions (600)

### Issue: "Access Denied" on S3
**Solution:**
1. Check credentials are from correct Render environment (production)
2. Verify IAM permissions include `s3:ListBucket` and `s3:GetObject`

### Issue: "aws: command not found"
**Solution:** Install AWS CLI using the command in Step 1

### Issue: Wrong bucket name
**Solution:** Check `S3_DATA_BUCKET` value in Render environment variables

---

## 🎯 Ready for Phase 1.1!

Once all steps are complete, you can proceed with Phase 1.1 tasks:

1. **Task 1.1.1:** Run daily smoke tests
   ```bash
   ./scripts/run_smoke_tests.sh | tee docs/test-results/phase-1.1-day1-$(date +%Y-%m-%d).txt
   ```

2. **Task 1.1.2-1.1.5:** Inspect S3 structure
   ```bash
   ./scripts/inspect_s3.sh
   ```

3. **Task 1.1.6:** Test S3 failure fallback
   ```bash
   # Unset credentials temporarily
   unset AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY
   # Publish test messages
   # Verify local writes to /tmp/mcp_archive
   ```

---

## 📚 References

**AWS CLI Documentation:**
- [Installing AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)
- [Configuring credentials](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-envvars.html)
- [Custom endpoints (MinIO)](https://min.io/docs/minio/linux/integrations/aws-cli-with-minio.html)

**Project Documentation:**
- [current-work.md](.claude/resources/current-work.md) - Phase 1.1 tasks
- [WORK_LOG.md](../WORK_LOG.md) - Progress tracking
- [master-plan.md](.claude/resources/master-plan.md) - Production roadmap

---

**Last Updated:** 2025-11-28
**Next Update:** After AWS CLI installation complete
