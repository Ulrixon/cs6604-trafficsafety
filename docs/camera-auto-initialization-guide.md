# Camera Auto-Initialization Guide

**Feature:** Hybrid Camera Initialization for New Intersections
**Implementation:** Option 4 - Collector Integration + Periodic Refresh
**Date:** 2025-12-03

---

## Overview

This guide explains how to automatically initialize camera URLs when new intersections are added to the database by the data collector. We use a **hybrid approach** that combines:

1. **Immediate population** when collector inserts new intersection
2. **Periodic batch refresh** to catch missed intersections and update existing cameras

This ensures:
- ✅ New intersections get cameras immediately
- ✅ No API latency during user browsing
- ✅ Automatic refresh keeps camera data current
- ✅ Resilient to collector failures

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Data Collector Process                        │
│  1. Fetches new intersection data from VTTI                     │
│  2. Inserts into database                                       │
│  3. Calls populate_camera_urls.py --auto --intersection-id X    │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                  Camera Population Service                       │
│  - Queries VDOT API for nearest cameras                         │
│  - Updates database with camera_urls                            │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                    PostgreSQL Database                           │
│  - Stores camera_urls in JSONB column                           │
└─────────────────────────────────────────────────────────────────┘

                            +

┌─────────────────────────────────────────────────────────────────┐
│                   Periodic Cron Job (Daily)                      │
│  - Runs: python populate_camera_urls.py --auto-new-only         │
│  - Catches any intersections missed by collector                │
│  - Runs at 2:00 AM daily                                        │
└─────────────────────────────────────────────────────────────────┘
```

---

## Part 1: Collector Integration

### Method 1: Python Subprocess Call

If your collector is written in Python, add this after inserting a new intersection:

```python
import subprocess
import os

def add_intersection_to_db(intersection_data):
    """Add new intersection and populate cameras"""

    # 1. Insert intersection into database
    cursor.execute("""
        INSERT INTO intersections (name, latitude, longitude, ...)
        VALUES (%s, %s, %s, ...)
        RETURNING id
    """, (intersection_data['name'], intersection_data['lat'], ...))

    intersection_id = cursor.fetchone()[0]
    connection.commit()

    print(f"✓ Inserted intersection {intersection_id}: {intersection_data['name']}")

    # 2. Populate cameras for new intersection
    try:
        result = subprocess.run([
            'python',
            'backend/scripts/populate_camera_urls.py',
            '--auto',
            '--intersection-id', str(intersection_id),
            '--radius', '0.5',
            '--max-cameras', '3'
        ],
        capture_output=True,
        text=True,
        timeout=30,
        env={**os.environ, 'VDOT_API_KEY': os.getenv('VDOT_API_KEY')}
        )

        if result.returncode == 0:
            print(f"✓ Cameras populated for intersection {intersection_id}")
        else:
            print(f"⚠️  Camera population failed: {result.stderr}")
            # Don't fail the whole process - periodic job will catch it

    except subprocess.TimeoutExpired:
        print(f"⚠️  Camera population timed out for {intersection_id}")
        # Continue - periodic job will retry

    except Exception as e:
        print(f"⚠️  Camera population error: {e}")
        # Continue - periodic job will retry

    return intersection_id
```

### Method 2: Direct Python Import

For tighter integration, import the CameraURLPopulator class:

```python
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.abspath('backend'))

from scripts.populate_camera_urls import CameraURLPopulator

def add_intersection_to_db(intersection_data):
    """Add new intersection and populate cameras"""

    # 1. Insert intersection
    cursor.execute("""
        INSERT INTO intersections (name, latitude, longitude, ...)
        VALUES (%s, %s, %s, ...)
        RETURNING id
    """, (intersection_data['name'], intersection_data['lat'], ...))

    intersection_id = cursor.fetchone()[0]
    connection.commit()

    print(f"✓ Inserted intersection {intersection_id}")

    # 2. Populate cameras
    try:
        populator = CameraURLPopulator()
        success = populator.auto_populate_intersection(
            intersection_id,
            radius_miles=0.5,
            max_cameras=3
        )

        if success:
            print(f"✓ Cameras populated for intersection {intersection_id}")
        else:
            print(f"⚠️  No cameras found for intersection {intersection_id}")

    except Exception as e:
        print(f"⚠️  Camera population error: {e}")
        # Continue - periodic job will retry

    return intersection_id
```

### Method 3: Database Trigger (Advanced)

For maximum automation, use a PostgreSQL trigger:

```sql
-- Function to populate cameras after insert
CREATE OR REPLACE FUNCTION populate_cameras_on_insert()
RETURNS TRIGGER AS $$
BEGIN
    -- Call external Python script asynchronously
    PERFORM pg_notify(
        'new_intersection',
        json_build_object(
            'id', NEW.id,
            'latitude', NEW.latitude,
            'longitude', NEW.longitude
        )::text
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger on intersection insert
CREATE TRIGGER trigger_populate_cameras
AFTER INSERT ON intersections
FOR EACH ROW
EXECUTE FUNCTION populate_cameras_on_insert();
```

Then create a listener service:

```python
import psycopg2
import subprocess
import json

def listen_for_new_intersections():
    """Listen for new intersection notifications and populate cameras"""
    conn = psycopg2.connect(os.getenv('DATABASE_URL'))
    conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)

    cur = conn.cursor()
    cur.execute("LISTEN new_intersection;")

    print("🔊 Listening for new intersections...")

    while True:
        conn.poll()
        while conn.notifies:
            notify = conn.notifies.pop(0)
            payload = json.loads(notify.payload)

            print(f"📍 New intersection detected: {payload['id']}")

            # Populate cameras
            subprocess.run([
                'python', 'backend/scripts/populate_camera_urls.py',
                '--auto', '--intersection-id', str(payload['id'])
            ])

# Run as background service
if __name__ == '__main__':
    listen_for_new_intersections()
```

---

## Part 2: Periodic Batch Job

The periodic job refreshes ALL cameras to catch:
- Cameras that have moved or been replaced
- New cameras added near existing intersections
- Broken/outdated camera links
- Changes in VDOT camera inventory

**Strategy:** Use `--auto-all` to refresh ALL cameras (not just new ones)

### Setup Cron Job (Linux/Mac)

Add to crontab:

```bash
# Edit crontab
crontab -e

# Add this line (runs daily at 2:00 AM)
0 2 * * * cd /path/to/cs6604-trafficsafety && /usr/bin/python3 backend/scripts/populate_camera_urls.py --auto-all >> /var/log/camera-refresh.log 2>&1
```

With environment variables:

```bash
# Add to crontab with env vars
0 2 * * * export DATABASE_URL="postgresql://..." && export VDOT_API_KEY="..." && cd /path/to/project && python backend/scripts/populate_camera_urls.py --auto-all
```

### Windows Task Scheduler

Create a batch file `refresh_cameras.bat`:

```batch
@echo off
cd C:\Code\Git\cs6604-trafficsafety
set DATABASE_URL=postgresql://user:pass@host/db
set VDOT_API_KEY=your-key-here
python backend\scripts\populate_camera_urls.py --auto-all
```

Schedule via Task Scheduler:
1. Open Task Scheduler
2. Create Basic Task
3. Name: "Camera Refresh - New Intersections"
4. Trigger: Daily at 2:00 AM
5. Action: Start a program
6. Program: `C:\Code\Git\cs6604-trafficsafety\refresh_cameras.bat`

### Docker Compose (Recommended for Local/Dev)

Add a cron service to `docker-compose.yml`:

```yaml
services:
  camera-refresh:
    image: python:3.11-slim
    container_name: camera-refresh-cron
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - VDOT_API_KEY=${VDOT_API_KEY}
    volumes:
      - ./backend:/app/backend
    command: >
      sh -c "
        apt-get update && apt-get install -y cron &&
        echo '0 2 * * * cd /app && python backend/scripts/populate_camera_urls.py --auto-all >> /var/log/cron.log 2>&1' > /etc/cron.d/camera-refresh &&
        chmod 0644 /etc/cron.d/camera-refresh &&
        crontab /etc/cron.d/camera-refresh &&
        cron -f
      "
    restart: unless-stopped
    depends_on:
      - db
```

**Note:** For production, use GCP Cloud Scheduler instead (see below - much cheaper and more reliable).

### GCP Cloud Scheduler + Cloud Run Jobs (Recommended for Production - CHEAPEST)

**Cost:** ~$0.30/month (3 free Cloud Scheduler jobs, Cloud Run Jobs pay-per-execution)

This is the most cost-effective option for GCP deployments.

#### Step 1: Create Cloud Run Job

```bash
# Build and push container image
cd backend
gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/camera-refresh:latest

# Create Cloud Run Job
gcloud run jobs create camera-refresh \
  --image gcr.io/YOUR_PROJECT_ID/camera-refresh:latest \
  --region us-central1 \
  --set-env-vars DATABASE_URL="postgresql://..." \
  --set-secrets VDOT_API_KEY=vdot-api-key:latest \
  --max-retries 2 \
  --task-timeout 30m \
  --memory 512Mi \
  --cpu 1
```

#### Step 2: Create Dockerfile for Job

Create `backend/Dockerfile.camera-refresh`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Run camera refresh script
CMD ["python", "scripts/populate_camera_urls.py", "--auto-all"]
```

#### Step 3: Set Up Cloud Scheduler

```bash
# Create Cloud Scheduler job (runs daily at 2 AM)
gcloud scheduler jobs create http camera-refresh-daily \
  --location us-central1 \
  --schedule "0 2 * * *" \
  --uri "https://us-central1-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/YOUR_PROJECT_ID/jobs/camera-refresh:run" \
  --http-method POST \
  --oauth-service-account-email YOUR_SERVICE_ACCOUNT@YOUR_PROJECT_ID.iam.gserviceaccount.com
```

#### Step 4: Store Secrets in Secret Manager

```bash
# Store VDOT API key in Secret Manager
echo -n "your-vdot-api-key" | gcloud secrets create vdot-api-key \
  --data-file=- \
  --replication-policy="automatic"

# Grant Cloud Run access to secret
gcloud secrets add-iam-policy-binding vdot-api-key \
  --member="serviceAccount:YOUR_SERVICE_ACCOUNT@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

#### Step 5: Test the Job

```bash
# Manually trigger the job to test
gcloud run jobs execute camera-refresh --region us-central1

# View logs
gcloud logging read "resource.type=cloud_run_job AND resource.labels.job_name=camera-refresh" \
  --limit 50 \
  --format json
```

**Pricing Breakdown:**
- Cloud Scheduler: Free (first 3 jobs)
- Cloud Run Jobs: ~$0.00002 per execution (512MB, 1 CPU, ~5 min runtime)
- Monthly cost: ~$0.001 for daily executions
- Secret Manager: $0.06 per secret per month
- **Total: ~$0.06/month**

---

### GCP Cloud Functions (Alternative - Slightly More Expensive)

**Cost:** ~$0.50/month

```bash
# Deploy Cloud Function
gcloud functions deploy camera-refresh \
  --runtime python311 \
  --trigger-http \
  --entry-point refresh_cameras \
  --set-env-vars DATABASE_URL="postgresql://..." \
  --set-secrets VDOT_API_KEY=vdot-api-key:latest \
  --timeout 540s \
  --memory 512MB \
  --region us-central1
```

Create `backend/functions/main.py`:

```python
import os
import sys

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from scripts.populate_camera_urls import CameraURLPopulator

def refresh_cameras(request):
    """HTTP Cloud Function to refresh cameras"""
    try:
        populator = CameraURLPopulator()
        populator.auto_populate_all(radius_miles=0.5, max_cameras=3)
        return {"status": "success", "message": "Cameras refreshed"}, 200
    except Exception as e:
        return {"status": "error", "message": str(e)}, 500
```

Schedule with Cloud Scheduler:

```bash
gcloud scheduler jobs create http camera-refresh-function \
  --location us-central1 \
  --schedule "0 2 * * *" \
  --uri "https://us-central1-YOUR_PROJECT_ID.cloudfunctions.net/camera-refresh" \
  --http-method GET
```

---

### Kubernetes CronJob (For K8s Deployments)

Create `camera-refresh-cronjob.yaml`:

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: camera-refresh
spec:
  schedule: "0 2 * * *"  # Daily at 2:00 AM
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: camera-refresh
            image: your-backend-image:latest
            command:
            - python
            - backend/scripts/populate_camera_urls.py
            - --auto-all
            env:
            - name: DATABASE_URL
              valueFrom:
                secretKeyRef:
                  name: database-secrets
                  key: url
            - name: VDOT_API_KEY
              valueFrom:
                secretKeyRef:
                  name: vdot-secrets
                  key: api-key
          restartPolicy: OnFailure
```

---

## Configuration

### Environment Variables

Required for both collector and cron job:

```bash
# Database connection
export DATABASE_URL="postgresql://user:password@host:5432/database"

# VDOT API key
export VDOT_API_KEY="your-vdot-api-key"

# Optional tuning
export CAMERA_SEARCH_RADIUS="0.5"  # miles
export CAMERA_MAX_RESULTS="3"
```

### Collector Configuration

Add to your collector's configuration file:

```json
{
  "camera_population": {
    "enabled": true,
    "method": "subprocess",  // or "import" or "trigger"
    "radius_miles": 0.5,
    "max_cameras": 3,
    "timeout_seconds": 30,
    "fail_silently": true  // Don't block insert on camera error
  }
}
```

---

## Testing

### Test Collector Integration

1. **Insert test intersection**:
   ```sql
   INSERT INTO intersections (name, latitude, longitude, traffic_volume)
   VALUES ('Test Intersection - Richmond', 37.5407, -77.4360, 100)
   RETURNING id;
   ```

2. **Manually trigger camera population**:
   ```bash
   python backend/scripts/populate_camera_urls.py --auto --intersection-id <id>
   ```

3. **Verify cameras added**:
   ```sql
   SELECT id, name, camera_urls FROM intersections WHERE id = <id>;
   ```

### Test Periodic Job

1. **Run manually**:
   ```bash
   python backend/scripts/populate_camera_urls.py --auto-all
   ```

2. **Expected output**:
   ```
   🔄 Auto-populating cameras for 15 intersections
      Radius: 0.5 miles
      Max cameras: 3

   📍 Processing: Test Intersection - Richmond (ID: 42)
      Location: (37.5407, -77.4360)
   ✅ Updated intersection 42 with 2 camera(s)
      - VDOT: VDOT Camera - I-95 @ Broad St
      - 511: View on 511 Map

   ... (processes all intersections)

   =============================================================
   ✅ Successfully populated: 15
   ❌ Failed: 0
   ```

**Note:** This refreshes ALL cameras, not just new ones. This ensures:
- Cameras that moved get updated coordinates
- New cameras near existing intersections are discovered
- Outdated/broken camera links are replaced

### Integration Test

Full end-to-end test:

```bash
# 1. Clear test intersection
python backend/scripts/populate_camera_urls.py --clear --intersection-id 0

# 2. Verify cleared
python backend/scripts/populate_camera_urls.py --list | grep "ID 0"

# 3. Run auto-new-only
python backend/scripts/populate_camera_urls.py --auto-new-only

# 4. Verify populated
python backend/scripts/populate_camera_urls.py --list | grep "ID 0"
```

---

## Monitoring

### Log Rotation

Configure log rotation for cron job:

```bash
# /etc/logrotate.d/camera-refresh
/var/log/camera-refresh.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
}
```

### Metrics to Track

1. **Collector Metrics**:
   - Camera population success rate
   - Average population time
   - API timeout rate

2. **Periodic Job Metrics**:
   - Intersections processed
   - Success/failure counts
   - Coverage percentage

3. **Database Metrics**:
   ```sql
   -- Daily camera coverage report
   SELECT
       COUNT(*) as total_intersections,
       COUNT(*) FILTER (WHERE camera_urls IS NOT NULL) as with_cameras,
       ROUND(100.0 * COUNT(*) FILTER (WHERE camera_urls IS NOT NULL) / COUNT(*), 1) as coverage_pct
   FROM intersections;
   ```

### Alerting

Set up alerts for:
- Coverage < 80%
- Periodic job failures
- API errors > 10%

Example alert script:

```bash
#!/bin/bash
# camera_alert.sh

COVERAGE=$(psql $DATABASE_URL -t -c "
    SELECT COUNT(*) FILTER (WHERE camera_urls IS NOT NULL) * 100 / COUNT(*)
    FROM intersections
")

if [ "$COVERAGE" -lt 80 ]; then
    echo "⚠️ Camera coverage below 80%: ${COVERAGE}%"
    # Send email/Slack notification
fi
```

---

## Troubleshooting

### Issue: Cameras not populating from collector

**Symptoms**: New intersections have no cameras despite collector integration

**Solutions**:
1. Check collector logs for errors
2. Verify VDOT_API_KEY is set in collector environment
3. Test manual population:
   ```bash
   python backend/scripts/populate_camera_urls.py --auto --intersection-id <id>
   ```
4. Check database connection from collector context
5. Verify subprocess call syntax

### Issue: Periodic job not running

**Symptoms**: No log entries, intersections stay without cameras

**Solutions**:
1. Check cron service is running: `systemctl status cron`
2. Verify crontab entry: `crontab -l`
3. Check cron logs: `grep CRON /var/log/syslog`
4. Test manual execution
5. Verify file permissions on script

### Issue: High API timeout rate

**Symptoms**: Many "No cameras found" messages

**Solutions**:
1. Increase search radius: `--radius 1.0`
2. Increase timeout in VDOT service
3. Check VDOT API status
4. Verify network connectivity
5. Review API rate limits

### Issue: Duplicate camera population

**Symptoms**: Intersections populated twice

**Solutions**:
1. Use `--auto-new-only` instead of `--auto-all` in cron
2. Check for multiple cron entries
3. Verify collector doesn't run auto-populate on existing intersections
4. Add idempotency check in collector

---

## Best Practices

### 1. Fail Gracefully

- Never block intersection insertion on camera errors
- Use try/except around camera population
- Log errors but continue processing

### 2. Optimize Timing

- **Collector**: Immediate population for UX
- **Cron**: Off-peak hours (2 AM) to avoid API load
- **Cache**: 5-minute TTL reduces redundant API calls

### 3. Monitor Coverage

- Track camera coverage percentage
- Alert if coverage drops below threshold
- Regular audits of camera link validity

### 4. Handle Failures

- Periodic job catches collector failures
- Manual tools for one-off fixes
- Database maintains state even if services fail

### 5. Environment Separation

- Dev: Mock VDOT API, don't use real key
- Staging: Real API with test intersections
- Production: Full automation with monitoring

---

## Rollback Plan

If camera auto-initialization causes issues:

```bash
# 1. Disable collector integration
# (Comment out camera population code)

# 2. Stop periodic job
crontab -r  # or comment out line

# 3. Clear all cameras (optional)
python backend/scripts/populate_camera_urls.py --clear --intersection-id <id>

# 4. Manual population as needed
python backend/scripts/populate_camera_urls.py --add \
    --intersection-id <id> \
    --source "VDOT" \
    --url "..." \
    --label "..."
```

---

## Performance Impact

### Collector Impact

- **CPU**: +5-10% during camera API call
- **Memory**: +10MB for VDOT service
- **Latency**: +0.5-2s per intersection insert
- **Mitigation**: Async/background population

### Periodic Job Impact

- **Database**: Minimal (indexed queries)
- **API**: ~12 requests/hour (with caching)
- **Runtime**: ~30s for 100 intersections

---

## Summary

**Hybrid Approach Benefits**:
- ✅ Immediate camera availability for new intersections
- ✅ Daily refresh catches camera changes and new cameras
- ✅ No user-facing latency
- ✅ Resilient to collector failures
- ✅ Automatic maintenance and link updates
- ✅ Easy to monitor and debug

**Recommended Setup**:
1. **Collector Integration**: Populate cameras immediately when inserting new intersection
2. **GCP Cloud Scheduler + Cloud Run Jobs**: Daily refresh of ALL cameras (~$0.06/month)
3. **Monitoring**: Track coverage percentage and broken links

**Implementation Checklist**:
- [ ] Add camera population to collector code (subprocess or direct import)
- [ ] Deploy Cloud Run Job with `--auto-all` command
- [ ] Set up Cloud Scheduler for daily execution (2 AM)
- [ ] Configure environment variables (DATABASE_URL, VDOT_API_KEY)
- [ ] Store VDOT_API_KEY in Secret Manager
- [ ] Test manual job execution
- [ ] Monitor coverage metrics and logs
- [ ] Set up alerting for failures

**Cost Comparison**:
- **GCP Cloud Scheduler + Cloud Run Jobs: ~$0.06/month** ← RECOMMENDED
- GCP Cloud Functions: ~$0.50/month
- Docker container on VM: $5-10/month
- Kubernetes CronJob: Varies (depends on cluster size)

**Deployment Files**:
- `backend/Dockerfile.camera-refresh` - Container image definition
- `backend/cloudbuild.camera-refresh.yaml` - Cloud Build configuration
- `backend/deploy-camera-refresh-gcp.sh` - Automated deployment script

**Quick Deploy (GCP)**:
```bash
cd backend
./deploy-camera-refresh-gcp.sh \
  YOUR_PROJECT_ID \
  camera-refresh@YOUR_PROJECT_ID.iam.gserviceaccount.com \
  "postgresql://..." \
  "your-vdot-api-key"
```

---

**Last Updated:** 2025-12-03
**Version:** 2.0
**Status:** Production Ready with GCP Support
