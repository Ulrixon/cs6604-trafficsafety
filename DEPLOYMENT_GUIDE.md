# GCP Cloud Run Deployment Guide

This guide explains how to deploy the Traffic Safety application (backend API and frontend dashboard) to Google Cloud Run.

## Prerequisites

1. **Google Cloud SDK** installed and configured

   ```bash
   gcloud --version
   gcloud auth login
   gcloud config set project 180117512369
   ```

2. **Docker** installed

   ```bash
   docker --version
   ```

3. **Required GCP APIs enabled**

   ```bash
   gcloud services enable \
     run.googleapis.com \
     containerregistry.googleapis.com \
     secretmanager.googleapis.com
   ```

4. **Secret Manager secrets configured**
   - `projects/180117512369/secrets/db_user/versions/1` - Database username
   - `projects/180117512369/secrets/db_password/versions/1` - Database password

## Architecture

```
┌─────────────────┐         ┌──────────────────┐         ┌─────────────────┐
│                 │         │                  │         │                 │
│   Frontend      │────────▶│   Backend API    │────────▶│  PostgreSQL DB  │
│   (Streamlit)   │         │   (FastAPI)      │         │  (GCP VM)       │
│                 │         │                  │         │                 │
└─────────────────┘         └──────────────────┘         └─────────────────┘
   Cloud Run                   Cloud Run                   34.140.49.230
   Port: 8080                  Port: 8080                  Port: 5432
```

## Backend Deployment

### 1. Navigate to backend directory

```bash
cd backend
```

### 2. Update configuration (if needed)

Edit `docker-entrypoint.sh` to adjust:

- Database host: `VTTI_DB_HOST=34.140.49.230`
- MCDM settings: `MCDM_BIN_MINUTES`, `MCDM_LOOKBACK_HOURS`

### 3. Deploy using script

```bash
chmod +x deploy-gcp.sh
./deploy-gcp.sh
```

### 4. Manual deployment (alternative)

```bash
# Build image
docker build -t gcr.io/180117512369/cs6604-trafficsafety-backend:latest .

# Push to GCR
docker push gcr.io/180117512369/cs6604-trafficsafety-backend:latest

# Deploy to Cloud Run
gcloud run deploy cs6604-trafficsafety-backend \
  --image gcr.io/180117512369/cs6604-trafficsafety-backend:latest \
  --platform managed \
  --region europe-west1 \
  --allow-unauthenticated \
  --port 8080 \
  --memory 2Gi \
  --cpu 2 \
  --set-env-vars "VTTI_DB_HOST=34.140.49.230,VTTI_DB_PORT=5432,VTTI_DB_NAME=vtti_db" \
  --set-secrets "VTTI_DB_USER=db_user:1,VTTI_DB_PASSWORD=db_password:1"
```

### 5. Verify backend deployment

```bash
# Health check
curl https://cs6604-trafficsafety-180117512369.europe-west1.run.app/health

# API docs
open https://cs6604-trafficsafety-180117512369.europe-west1.run.app/docs

# Test endpoint
curl https://cs6604-trafficsafety-180117512369.europe-west1.run.app/api/v1/safety/index/
```

## Frontend Deployment

### 1. Navigate to frontend directory

```bash
cd frontend
```

### 2. Verify backend URL in Dockerfile

The Dockerfile creates a `.env` file with:

```
API_URL=https://cs6604-trafficsafety-180117512369.europe-west1.run.app/api/v1/safety/index/
```

If the backend URL changes, update line 24 in `frontend/Dockerfile`.

### 3. Deploy using script

```bash
chmod +x deploy-gcp.sh
./deploy-gcp.sh
```

### 4. Manual deployment (alternative)

```bash
# Build image
docker build -t gcr.io/180117512369/cs6604-trafficsafety-frontend:latest .

# Push to GCR
docker push gcr.io/180117512369/cs6604-trafficsafety-frontend:latest

# Deploy to Cloud Run
gcloud run deploy cs6604-trafficsafety-frontend \
  --image gcr.io/180117512369/cs6604-trafficsafety-frontend:latest \
  --platform managed \
  --region europe-west1 \
  --allow-unauthenticated \
  --port 8080 \
  --memory 1Gi \
  --cpu 1
```

### 5. Get frontend URL

```bash
gcloud run services describe cs6604-trafficsafety-frontend \
  --region europe-west1 \
  --format 'value(status.url)'
```

## Environment Variables

### Backend (.env)

```bash
# Database (production)
VTTI_DB_HOST=34.140.49.230
VTTI_DB_PORT=5432
VTTI_DB_NAME=vtti_db
VTTI_DB_USER=<from_secret_manager>
VTTI_DB_PASSWORD=<from_secret_manager>

# MCDM Configuration
MCDM_BIN_MINUTES=15
MCDM_LOOKBACK_HOURS=24
```

### Frontend (.env)

```bash
# API Configuration
API_URL=https://cs6604-trafficsafety-180117512369.europe-west1.run.app/api/v1/safety/index/
API_TIMEOUT=30
API_MAX_RETRIES=3
API_CACHE_TTL=300

# Map defaults
DEFAULT_LATITUDE=38.86
DEFAULT_LONGITUDE=-77.055
DEFAULT_ZOOM=13
MAP_HEIGHT=650
```

## Secret Manager Setup

### Create secrets (if not already created)

```bash
# Create db_user secret
echo -n "your_db_username" | gcloud secrets create db_user \
  --data-file=- \
  --replication-policy="automatic"

# Create db_password secret
echo -n "your_db_password" | gcloud secrets create db_password \
  --data-file=- \
  --replication-policy="automatic"
```

### Grant Cloud Run access to secrets

```bash
# Get the service account email
gcloud run services describe cs6604-trafficsafety-backend \
  --region europe-west1 \
  --format 'value(spec.template.spec.serviceAccountName)'

# Grant access (replace SERVICE_ACCOUNT with actual email)
gcloud secrets add-iam-policy-binding db_user \
  --member="serviceAccount:SERVICE_ACCOUNT" \
  --role="roles/secretmanager.secretAccessor"

gcloud secrets add-iam-policy-binding db_password \
  --member="serviceAccount:SERVICE_ACCOUNT" \
  --role="roles/secretmanager.secretAccessor"
```

## Database Connectivity

The backend connects to PostgreSQL at:

- **Host**: `34.140.49.230` (GCP VM external IP)
- **Port**: `5432`
- **Database**: `vtti_db`
- **User**: From Secret Manager (`db_user`)
- **Password**: From Secret Manager (`db_password`)

### Firewall rules

Ensure the PostgreSQL server allows connections from Cloud Run:

1. Cloud Run services get dynamic IPs
2. Options:
   - Allow all Cloud Run IPs (not recommended for production)
   - Use Cloud SQL Proxy
   - Set up VPC connector for Cloud Run

## Monitoring & Logs

### View backend logs

```bash
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=cs6604-trafficsafety-backend" --limit 50
```

### View frontend logs

```bash
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=cs6604-trafficsafety-frontend" --limit 50
```

### Monitor in Console

- Backend: https://console.cloud.google.com/run/detail/europe-west1/cs6604-trafficsafety-backend
- Frontend: https://console.cloud.google.com/run/detail/europe-west1/cs6604-trafficsafety-frontend

## Troubleshooting

### Backend returns 500 errors

```bash
# Check logs
gcloud logging tail "resource.type=cloud_run_revision AND resource.labels.service_name=cs6604-trafficsafety-backend"

# Common issues:
# 1. Database connection failed - check firewall rules
# 2. Secret Manager access denied - check IAM permissions
# 3. Out of memory - increase memory allocation
```

### Frontend can't reach backend

```bash
# Verify backend is accessible
curl https://cs6604-trafficsafety-180117512369.europe-west1.run.app/health

# Check frontend env vars
gcloud run services describe cs6604-trafficsafety-frontend \
  --region europe-west1 \
  --format yaml
```

### Database connection timeout

```bash
# Test connection from Cloud Shell
gcloud compute ssh <instance-name> --command "telnet 34.140.49.230 5432"

# Or use psql
psql -h 34.140.49.230 -p 5432 -U vtti_user -d vtti_db
```

## Rollback

### Rollback to previous revision

```bash
# List revisions
gcloud run revisions list --service cs6604-trafficsafety-backend --region europe-west1

# Rollback to specific revision
gcloud run services update-traffic cs6604-trafficsafety-backend \
  --to-revisions REVISION_NAME=100 \
  --region europe-west1
```

## Cost Optimization

- **Min instances**: Set to 0 to scale to zero when idle
- **Max instances**: Limit to control costs
- **Memory**: Right-size based on actual usage
- **CPU**: Use 1 CPU for frontend, 2 for backend
- **Timeout**: Set appropriate timeout (300s default)

## Security Best Practices

1. ✅ Use Secret Manager for sensitive data
2. ✅ Run as non-root user in containers
3. ✅ Enable XSRF protection in Streamlit
4. ✅ Use HTTPS (automatic with Cloud Run)
5. ⚠️ Consider adding authentication for production
6. ⚠️ Restrict API to specific origins with CORS
7. ⚠️ Use VPC connector for database access

## Automated Deployment with Cloud Build

### Cloud Build Configuration Files

The repository includes Cloud Build configuration files for automated deployment:

- **Backend**: [backend/cloudbuild.yaml](backend/cloudbuild.yaml)
- **Frontend**: [frontend/cloudbuild.yaml](frontend/cloudbuild.yaml)

These files define the build, push, and deploy steps for each service.

### Setting Up Cloud Build Triggers

**Option 1: Using GCP Console (Recommended)**

1. Go to [Cloud Build Triggers](https://console.cloud.google.com/cloud-build/triggers) in GCP Console
2. Click **Create Trigger**

**For Backend:**
- **Name**: `deploy-backend`
- **Event**: Push to a branch
- **Source**: Connect your GitHub repository (`Ulrixon/cs6604-trafficsafety`)
- **Branch**: `^main$`
- **Included files filter**: `backend/**`
- **Cloud Build configuration file**: `backend/cloudbuild.yaml`
- Click **Create**

**For Frontend:**
- **Name**: `deploy-frontend`
- **Event**: Push to a branch
- **Source**: Connect your GitHub repository (`Ulrixon/cs6604-trafficsafety`)
- **Branch**: `^main$`
- **Included files filter**: `frontend/**`
- **Cloud Build configuration file**: `frontend/cloudbuild.yaml`
- Click **Create**

**Option 2: Using gcloud CLI**

```bash
# Create backend trigger
gcloud builds triggers create github \
  --name="deploy-backend" \
  --repo-name="cs6604-trafficsafety" \
  --repo-owner="Ulrixon" \
  --branch-pattern="^main$" \
  --build-config="backend/cloudbuild.yaml" \
  --included-files="backend/**"

# Create frontend trigger
gcloud builds triggers create github \
  --name="deploy-frontend" \
  --repo-name="cs6604-trafficsafety" \
  --repo-owner="Ulrixon" \
  --branch-pattern="^main$" \
  --build-config="frontend/cloudbuild.yaml" \
  --included-files="frontend/**"
```

### How Automated Deployment Works

Once Cloud Build triggers are configured:

1. **Developer pushes changes** to `main` branch
2. **Cloud Build detects changes** in `backend/` or `frontend/` directories
3. **Builds Docker image** and tags with commit SHA + latest
4. **Pushes to Container Registry** (or Artifact Registry)
5. **Deploys to Cloud Run** with configured settings
6. **Full deployment** typically takes 5-8 minutes

### Monitoring Deployments

**View build history:**
- GCP Console: https://console.cloud.google.com/cloud-build/builds
- CLI: `gcloud builds list --limit=10`

**View build logs:**
```bash
gcloud builds log <BUILD_ID>
```

**View trigger details:**
```bash
gcloud builds triggers list
gcloud builds triggers describe deploy-backend
```

### Cost

Cloud Build provides:
- **120 free build-minutes per day**
- **$0.003 per build-minute** after free tier
- Typical deployment: ~5 minutes = ~$0.015 per deployment

Expected monthly cost: **$5-15** depending on deployment frequency
