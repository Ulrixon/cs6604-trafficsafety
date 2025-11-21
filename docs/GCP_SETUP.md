# GCP Cloud Storage Setup Guide

This guide walks you through setting up Google Cloud Storage for archiving Parquet files.

---

## Prerequisites

- Google Cloud Platform account
- `gcloud` CLI installed (optional, but recommended)
- Billing enabled on your GCP project

---

## Step 1: Create GCP Project

### Option A: Using GCP Console (Web)

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click **Select a Project** → **New Project**
3. Enter project details:
   - **Project Name**: `Traffic Safety Production`
   - **Project ID**: `trafficsafety-prod` (or auto-generated)
   - **Location**: Your organization (or No organization)
4. Click **Create**

### Option B: Using gcloud CLI

```bash
gcloud projects create trafficsafety-prod --name="Traffic Safety Production"
gcloud config set project trafficsafety-prod
```

---

## Step 2: Enable Required APIs

### Using GCP Console

1. Go to **APIs & Services** → **Library**
2. Search for and enable:
   - **Cloud Storage API**
   - **Cloud Storage JSON API**

### Using gcloud CLI

```bash
gcloud services enable storage-api.googleapis.com
gcloud services enable storage-component.googleapis.com
```

---

## Step 3: Create Cloud Storage Bucket

### Using GCP Console

1. Go to **Cloud Storage** → **Buckets**
2. Click **Create Bucket**
3. Configure bucket:
   - **Name**: `trafficsafety-prod-parquet` (must be globally unique)
   - **Location type**: Region
   - **Location**: `us-east4` (or your preferred region)
   - **Storage class**: Standard
   - **Access control**: Uniform (recommended)
   - **Public access**: Prevent public access
   - **Data protection**: Enable object versioning
4. Click **Create**

### Using gcloud CLI

```bash
gsutil mb -p trafficsafety-prod -c STANDARD -l us-east4 gs://trafficsafety-prod-parquet/
gsutil versioning set on gs://trafficsafety-prod-parquet/
```

---

## Step 4: Set Up Lifecycle Policy

This automatically moves old data to cheaper storage classes and deletes very old data.

### Create lifecycle configuration file

Create `lifecycle.json`:

```json
{
  "lifecycle": {
    "rule": [
      {
        "action": {
          "type": "SetStorageClass",
          "storageClass": "NEARLINE"
        },
        "condition": {
          "age": 30,
          "matchesPrefix": ["raw/"]
        }
      },
      {
        "action": {
          "type": "SetStorageClass",
          "storageClass": "COLDLINE"
        },
        "condition": {
          "age": 365,
          "matchesPrefix": ["raw/"]
        }
      },
      {
        "action": {
          "type": "Delete"
        },
        "condition": {
          "age": 730,
          "matchesPrefix": ["processed/"]
        }
      }
    ]
  }
}
```

### Apply lifecycle policy

```bash
gsutil lifecycle set lifecycle.json gs://trafficsafety-prod-parquet/
```

### Verify lifecycle policy

```bash
gsutil lifecycle get gs://trafficsafety-prod-parquet/
```

---

## Step 5: Create Service Account

### Using GCP Console

1. Go to **IAM & Admin** → **Service Accounts**
2. Click **Create Service Account**
3. Enter service account details:
   - **Name**: `trafficsafety-data-collector`
   - **ID**: `trafficsafety-data-collector` (auto-filled)
   - **Description**: Data collector service for uploading Parquet files
4. Click **Create and Continue**
5. Grant roles:
   - **Storage Object Creator** (allows uploads)
   - **Storage Object Viewer** (allows downloads)
6. Click **Continue** → **Done**

### Using gcloud CLI

```bash
gcloud iam service-accounts create trafficsafety-data-collector \
    --display-name="Traffic Safety Data Collector"

gcloud projects add-iam-policy-binding trafficsafety-prod \
    --member="serviceAccount:trafficsafety-data-collector@trafficsafety-prod.iam.gserviceaccount.com" \
    --role="roles/storage.objectCreator"

gcloud projects add-iam-policy-binding trafficsafety-prod \
    --member="serviceAccount:trafficsafety-data-collector@trafficsafety-prod.iam.gserviceaccount.com" \
    --role="roles/storage.objectViewer"
```

---

## Step 6: Generate Service Account Key

### Using GCP Console

1. Go to **IAM & Admin** → **Service Accounts**
2. Find `trafficsafety-data-collector`
3. Click **Actions** (⋮) → **Manage Keys**
4. Click **Add Key** → **Create New Key**
5. Select **JSON** format
6. Click **Create**
7. Save the downloaded JSON file

### Using gcloud CLI

```bash
gcloud iam service-accounts keys create ./gcp-service-account.json \
    --iam-account=trafficsafety-data-collector@trafficsafety-prod.iam.gserviceaccount.com
```

---

## Step 7: Secure the Service Account Key

**⚠️ IMPORTANT: This file contains credentials - never commit to Git!**

### Create secrets directory

```bash
mkdir -p secrets
```

### Move the key file

```bash
mv ~/Downloads/trafficsafety-prod-*.json ./secrets/gcp-service-account.json
```

### Add to .gitignore

Edit `.gitignore`:

```
# GCP credentials
secrets/
*.json
!package.json
!package-lock.json
```

### Set permissions (Linux/Mac)

```bash
chmod 600 secrets/gcp-service-account.json
```

---

## Step 8: Configure Environment Variables

Edit `backend/.env`:

```bash
# GCP Cloud Storage Configuration
GCS_BUCKET_NAME=trafficsafety-prod-parquet
GCS_PROJECT_ID=trafficsafety-prod
GOOGLE_APPLICATION_CREDENTIALS=/app/secrets/gcp-service-account.json
ENABLE_GCS_UPLOAD=true
```

---

## Step 9: Update Docker Compose

Edit `docker-compose.yml` to mount the secrets directory:

```yaml
data-collector:
  # ... existing config
  volumes:
    - ./backend/app:/app/app
    - parquet_data:/app/data/parquet
    - ./secrets:/app/secrets:ro  # ADD THIS LINE - read-only mount
  environment:
    # ... existing environment variables
    - GOOGLE_APPLICATION_CREDENTIALS=/app/secrets/gcp-service-account.json
```

---

## Step 10: Verify Setup

### Test bucket access

```bash
gsutil ls gs://trafficsafety-prod-parquet/
```

### Test service account permissions

```bash
gcloud auth activate-service-account \
    --key-file=./secrets/gcp-service-account.json

gsutil ls gs://trafficsafety-prod-parquet/
```

### Test from Docker

```bash
docker-compose exec data-collector python -c "
from google.cloud import storage
client = storage.Client()
bucket = client.bucket('trafficsafety-prod-parquet')
print(f'✓ Successfully connected to bucket: {bucket.name}')
"
```

---

## Cost Estimation

### Storage Costs (per GB/month)

| Age | Storage Class | Cost | Access Time |
|-----|---------------|------|-------------|
| 0-30 days | Standard | $0.020 | Immediate |
| 31-365 days | Nearline | $0.010 | ~1 second |
| 366-730 days | Coldline | $0.004 | ~1-2 seconds |
| >730 days | Deleted | $0 | N/A |

### Example Monthly Cost

**Assumptions:**
- 100 GB/month new data
- Retention: 2 years with lifecycle policy

**Month 1:**
- 100 GB Standard = $2.00

**Month 6:**
- 100 GB Standard + 500 GB Nearline = $7.00

**Month 12:**
- 100 GB Standard + 500 GB Nearline + 1000 GB Coldline = $11.00

**Steady state (24 months):**
- 100 GB Standard + 500 GB Nearline + ~7300 GB Coldline = ~$35/month

### Additional Costs

- **Operations**: ~$0.005/1000 operations (negligible)
- **Network egress**: First 1 GB/month free, then $0.12/GB (only if downloading from GCS)
- **Early deletion**: Nearline (<30 days), Coldline (<90 days) - avoid by using lifecycle policy

---

## Monitoring

### View storage usage

```bash
gsutil du -s gs://trafficsafety-prod-parquet/
```

### View lifecycle transitions

```bash
gsutil logging get gs://trafficsafety-prod-parquet/
```

### Check costs

1. Go to **Billing** → **Reports**
2. Filter by **Cloud Storage**
3. Group by **SKU** to see breakdown by storage class

---

## Troubleshooting

### "Permission denied" errors

```bash
# Verify service account has correct roles
gcloud projects get-iam-policy trafficsafety-prod \
    --flatten="bindings[].members" \
    --filter="bindings.members:trafficsafety-data-collector"
```

### "Bucket not found" errors

```bash
# Verify bucket exists and is in correct project
gsutil ls -p trafficsafety-prod
```

### Authentication errors in Docker

```bash
# Verify credentials file is mounted correctly
docker-compose exec data-collector ls -la /app/secrets/

# Verify environment variable is set
docker-compose exec data-collector env | grep GOOGLE_APPLICATION_CREDENTIALS
```

---

## Security Best Practices

1. **Never commit credentials to Git**
   - Add `secrets/` to `.gitignore`
   - Use environment variables

2. **Use least privilege**
   - Service account only has Storage Object Creator/Viewer
   - No admin or owner permissions

3. **Rotate keys regularly**
   - Delete old keys after creating new ones
   - Rotate every 90 days

4. **Enable versioning**
   - Protects against accidental deletion
   - Allows recovery of overwritten files

5. **Monitor access logs**
   - Enable audit logging
   - Review access patterns

---

## Testing GCS Upload in Data Collector

After completing the GCP setup, restart the data collector to enable GCS uploads:

### Step 1: Restart Data Collector

```bash
docker-compose restart data-collector
```

### Step 2: Monitor Logs

Watch for GCS upload confirmations:

```bash
docker logs trafficsafety-collector --tail 100 -f
```

Expected output:

```
VCC DATA COLLECTOR SERVICE
================================================================================
Collection Interval: 60 seconds
Realtime Mode: False
Storage Path: /app/data/parquet
VCC Base URL: https://vcc.vtti.vt.edu

PostgreSQL Dual-Write: ✓ ENABLED
  Database URL: postgresql://trafficsafety:trafficsafety_dev@db:5432/trafficsafety
  Fallback to Parquet: True

GCS Cloud Archive: ✓ ENABLED
  Bucket: gs://trafficsafety-prod-parquet
  Project ID: trafficsafety-prod
================================================================================

[2/3] Saving data to Parquet storage...
✓ Saved 150 BSM messages
  ✓ GCS: Uploaded BSM to gs://trafficsafety-prod-parquet/raw/bsm/2025/11/21/bsm_20251121_143000.parquet
✓ Saved 45 PSM messages
  ✓ GCS: Uploaded PSM to gs://trafficsafety-prod-parquet/raw/psm/2025/11/21/psm_20251121_143000.parquet
✓ Saved 2 MapData messages
  ✓ GCS: Uploaded MapData to gs://trafficsafety-prod-parquet/raw/mapdata/2025/11/21/mapdata_20251121_143000.parquet

Saving 5 computed safety indices...
  ✓ Parquet: Saved 5 records
  ✓ PostgreSQL: Saved 5/5 records
  ✓ GCS: Uploaded to gs://trafficsafety-prod-parquet/processed/indices/2025/11/21/indices_20251121_143000.parquet
✓ Triple-write successful (Parquet + PostgreSQL + GCS)

COLLECTION STATISTICS
================================================================================
Total Collections: 15
Total BSM Messages: 2,250
Total PSM Messages: 675
Total MapData: 30
Errors: 0

Storage Statistics:
  Parquet Writes: 15
  PostgreSQL Writes: 15
  Dual-Write Errors: 0
  GCS Uploads: 60
  GCS Errors: 0

Last Collection: 2025-11-21 14:30:00
================================================================================
```

### Step 3: Verify Files in GCS

List uploaded files:

```bash
# List recent BSM files
gsutil ls -l gs://trafficsafety-prod-parquet/raw/bsm/2025/11/21/

# List recent indices files
gsutil ls -l gs://trafficsafety-prod-parquet/processed/indices/2025/11/21/

# Count total files uploaded
gsutil ls -r gs://trafficsafety-prod-parquet/** | wc -l
```

### Step 4: Download and Verify a File

```bash
# Download a test file
gsutil cp gs://trafficsafety-prod-parquet/processed/indices/2025/11/21/indices_20251121_143000.parquet /tmp/

# Verify it's a valid Parquet file
python -c "
import pandas as pd
df = pd.read_parquet('/tmp/indices_20251121_143000.parquet')
print(f'✓ Valid Parquet file with {len(df)} rows and {len(df.columns)} columns')
print(df.head())
"
```

---

## Migrating Existing Parquet Files

After GCS upload is working in the data collector, migrate existing local Parquet files to GCS:

### Step 1: Run Migration Script (Dry Run)

```bash
# Preview what would be uploaded
docker-compose exec data-collector python scripts/migrate_parquet_to_gcs.py --dry-run
```

### Step 2: Run Actual Migration

```bash
# Upload all existing Parquet files
docker-compose exec data-collector python scripts/migrate_parquet_to_gcs.py --type all

# Or upload specific types
docker-compose exec data-collector python scripts/migrate_parquet_to_gcs.py --type bsm
docker-compose exec data-collector python scripts/migrate_parquet_to_gcs.py --type indices
```

### Step 3: Monitor Migration Progress

The script saves progress to `migration_state.json` and can be resumed if interrupted:

```bash
# Check migration state
docker-compose exec data-collector cat migration_state.json | jq
```

---

## Next Steps

After completing GCP setup:

1. ✅ Verify bucket is accessible
2. ✅ Service account credentials are secured
3. ✅ Environment variables are configured
4. ✅ GCS upload enabled in data collector
5. ➡️ Run migration script to upload existing Parquet files
6. ➡️ Monitor storage costs and lifecycle transitions

See also: [DUAL_WRITE_MIGRATION.md](./DUAL_WRITE_MIGRATION.md)

---

**Last Updated:** 2025-11-21
**Maintainer:** Traffic Safety Index Team
