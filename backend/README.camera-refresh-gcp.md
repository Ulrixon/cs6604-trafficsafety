# Camera Refresh - GCP Cloud Run Jobs Deployment

Automated daily camera refresh using GCP Cloud Scheduler + Cloud Run Jobs.

**Cost:** ~$0.06/month 💰

---

## Quick Deploy

```bash
cd backend

# Make script executable (Linux/Mac)
chmod +x deploy-camera-refresh-gcp.sh

# Run deployment
./deploy-camera-refresh-gcp.sh \
  YOUR_PROJECT_ID \
  camera-refresh@YOUR_PROJECT_ID.iam.gserviceaccount.com \
  "postgresql://user:pass@host/db" \
  "your-vdot-api-key"
```

---

## What This Does

1. **Builds container image** with camera refresh script
2. **Deploys Cloud Run Job** with environment variables and secrets
3. **Creates Cloud Scheduler** to run daily at 2:00 AM
4. **Stores VDOT API key** in Secret Manager
5. **Refreshes ALL cameras** daily to catch:
   - Camera location changes
   - New cameras near existing intersections
   - Broken/outdated links

---

## Prerequisites

1. **GCP Project** with billing enabled
2. **Service Account** with permissions:
   ```bash
   gcloud iam service-accounts create camera-refresh \
     --display-name="Camera Refresh Service Account"

   # Grant required roles
   gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
     --member="serviceAccount:camera-refresh@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
     --role="roles/run.admin"

   gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
     --member="serviceAccount:camera-refresh@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
     --role="roles/secretmanager.secretAccessor"

   gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
     --member="serviceAccount:camera-refresh@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
     --role="roles/cloudsql.client"
   ```

3. **gcloud CLI** installed and authenticated:
   ```bash
   gcloud auth login
   gcloud config set project YOUR_PROJECT_ID
   ```

4. **Required APIs** enabled (script does this automatically):
   - Cloud Run API
   - Cloud Scheduler API
   - Secret Manager API
   - Cloud Build API

---

## Files

- **Dockerfile.camera-refresh**: Container image definition
  - Based on Python 3.11-slim
  - Installs requirements and copies app code
  - Runs `populate_camera_urls.py --auto-all`

- **cloudbuild.camera-refresh.yaml**: Cloud Build configuration
  - Builds and pushes container to GCR
  - Tags with commit SHA and `latest`
  - Automatically updates Cloud Run Job

- **deploy-camera-refresh-gcp.sh**: Automated deployment script
  - Enables required APIs
  - Stores VDOT API key in Secret Manager
  - Builds and deploys Cloud Run Job
  - Creates Cloud Scheduler trigger

---

## Manual Testing

```bash
# Execute job manually (doesn't wait for schedule)
gcloud run jobs execute camera-refresh \
  --region us-central1 \
  --project YOUR_PROJECT_ID

# View logs
gcloud logging read \
  "resource.type=cloud_run_job AND resource.labels.job_name=camera-refresh" \
  --limit 50 \
  --project YOUR_PROJECT_ID
```

---

## Configuration

### Change Schedule

```bash
# Update to run every 6 hours
gcloud scheduler jobs update http camera-refresh-daily \
  --location us-central1 \
  --schedule "0 */6 * * *" \
  --project YOUR_PROJECT_ID
```

### Update VDOT API Key

```bash
# Add new version to Secret Manager
echo -n "new-vdot-api-key" | gcloud secrets versions add vdot-api-key \
  --data-file=- \
  --project YOUR_PROJECT_ID

# Job will automatically use latest version on next run
```

### Update Database URL

```bash
# Update environment variable
gcloud run jobs update camera-refresh \
  --region us-central1 \
  --set-env-vars DATABASE_URL="postgresql://new-connection-string" \
  --project YOUR_PROJECT_ID
```

### Adjust Resources

```bash
# Increase memory/CPU if needed
gcloud run jobs update camera-refresh \
  --region us-central1 \
  --memory 1Gi \
  --cpu 2 \
  --project YOUR_PROJECT_ID
```

---

## Monitoring

### View Recent Executions

```bash
gcloud run jobs executions list \
  --job camera-refresh \
  --region us-central1 \
  --limit 10 \
  --project YOUR_PROJECT_ID
```

### Check Scheduler Status

```bash
gcloud scheduler jobs describe camera-refresh-daily \
  --location us-central1 \
  --project YOUR_PROJECT_ID
```

### Set Up Alerts

Create alert for job failures:

```bash
# Create notification channel (email)
gcloud alpha monitoring channels create \
  --display-name="Camera Refresh Alerts" \
  --type=email \
  --channel-labels=email_address=your-email@example.com

# Create alert policy
gcloud alpha monitoring policies create \
  --notification-channels=CHANNEL_ID \
  --display-name="Camera Refresh Job Failures" \
  --condition-display-name="Job Failed" \
  --condition-threshold-value=1 \
  --condition-threshold-duration=60s \
  --condition-filter='resource.type="cloud_run_job" AND resource.labels.job_name="camera-refresh" AND metric.type="run.googleapis.com/job/completed_execution_count" AND metric.labels.result="failed"'
```

---

## Debugging

### Job Failing?

1. **Check logs**:
   ```bash
   gcloud logging read \
     "resource.type=cloud_run_job AND resource.labels.job_name=camera-refresh AND severity>=ERROR" \
     --limit 50
   ```

2. **Verify database connection**:
   ```bash
   # Test from Cloud Shell
   gcloud sql connect YOUR_INSTANCE --user=YOUR_USER
   ```

3. **Check VDOT API key**:
   ```bash
   # View secret (not the value)
   gcloud secrets describe vdot-api-key

   # Verify access
   gcloud secrets get-iam-policy vdot-api-key
   ```

4. **Test locally**:
   ```bash
   # Build and run container locally
   docker build -f Dockerfile.camera-refresh -t camera-refresh .
   docker run --rm \
     -e DATABASE_URL="postgresql://..." \
     -e VDOT_API_KEY="..." \
     camera-refresh
   ```

### Scheduler Not Triggering?

```bash
# Force trigger manually
gcloud scheduler jobs run camera-refresh-daily \
  --location us-central1

# Check last run time
gcloud scheduler jobs describe camera-refresh-daily \
  --location us-central1 \
  | grep lastAttemptTime
```

---

## Cost Optimization

Current configuration is already optimized for cost:

- **512Mi memory**: Sufficient for ~200 intersections
- **1 CPU**: Adequate for VDOT API calls
- **30-minute timeout**: Prevents runaway costs
- **2 retries**: Handles transient failures
- **Daily schedule**: Balances freshness vs. cost

**Estimated monthly cost:**
- Cloud Scheduler: $0 (3 free jobs)
- Cloud Run Jobs: $0.001 (30 daily executions @ 5 min each)
- Secret Manager: $0.06
- **Total: ~$0.06/month**

To reduce costs further:
- Run weekly instead of daily: Change schedule to `0 2 * * 0`
- Reduce timeout: `--task-timeout 15m` (if intersections < 100)

---

## CI/CD Integration

### GitHub Actions

```yaml
name: Deploy Camera Refresh

on:
  push:
    branches: [main]
    paths:
      - 'backend/scripts/populate_camera_urls.py'
      - 'backend/Dockerfile.camera-refresh'

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - uses: google-github-actions/auth@v1
        with:
          credentials_json: ${{ secrets.GCP_CREDENTIALS }}

      - name: Build and deploy
        run: |
          cd backend
          gcloud builds submit --config=cloudbuild.camera-refresh.yaml
```

### Cloud Build Trigger

```bash
gcloud builds triggers create github \
  --repo-name=YOUR_REPO \
  --repo-owner=YOUR_OWNER \
  --branch-pattern="^main$" \
  --build-config=backend/cloudbuild.camera-refresh.yaml \
  --included-files="backend/scripts/populate_camera_urls.py,backend/Dockerfile.camera-refresh"
```

---

## Cleanup

To remove all resources:

```bash
# Delete Cloud Scheduler job
gcloud scheduler jobs delete camera-refresh-daily \
  --location us-central1 \
  --quiet

# Delete Cloud Run Job
gcloud run jobs delete camera-refresh \
  --region us-central1 \
  --quiet

# Delete secret
gcloud secrets delete vdot-api-key --quiet

# Delete container images
gcloud container images delete gcr.io/YOUR_PROJECT_ID/camera-refresh:latest --quiet
```

---

## Support

For issues:
1. Check logs (see Debugging section)
2. Review [camera-auto-initialization-guide.md](../docs/camera-auto-initialization-guide.md)
3. Verify [camera-management.md](../docs/camera-management.md)

---

**Last Updated:** 2025-12-03
**Version:** 1.0
