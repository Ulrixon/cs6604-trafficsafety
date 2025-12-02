#!/bin/bash
# Deploy Data Collector to Google Cloud Run with Secret Manager integration

set -e

PROJECT_ID="symbolic-cinema-305010"
PROJECT_NUMBER="180117512369"
REGION="europe-west1"
SERVICE_NAME="cs6604-trafficsafety-collector"
AR_HOSTNAME="europe-west1-docker.pkg.dev"
REPOSITORY="cloud-run-source-deploy"
IMAGE_NAME="${AR_HOSTNAME}/${PROJECT_ID}/${REPOSITORY}/${SERVICE_NAME}"

echo "=== Deploying Traffic Safety Data Collector to Cloud Run ==="
echo "Project: ${PROJECT_ID}"
echo "Region: ${REGION}"
echo "Service: ${SERVICE_NAME}"
echo ""

# Build and push Docker image using Dockerfile.collector
echo "1. Building Docker image from Dockerfile.collector..."
docker build -f Dockerfile.collector -t ${IMAGE_NAME}:latest .

echo ""
echo "2. Pushing image to Google Container Registry..."
docker push ${IMAGE_NAME}:latest

echo ""
echo "3. Deploying to Cloud Run with Secret Manager integration..."
# Note: Using Cloud SQL instance connection name for database connection
CLOUD_SQL_INSTANCE="symbolic-cinema-305010:europe-west1:vtsi-postgres"

gcloud run deploy ${SERVICE_NAME} \
  --image ${IMAGE_NAME}:latest \
  --platform managed \
  --region ${REGION} \
  --project ${PROJECT_ID} \
  --no-allow-unauthenticated \
  --port 8080 \
  --memory 1Gi \
  --cpu 1 \
  --timeout 600 \
  --max-instances 1 \
  --min-instances 1 \
  --add-cloudsql-instances ${CLOUD_SQL_INSTANCE} \
  --set-env-vars "\
VCC_BASE_URL=https://vcc.vtti.vt.edu,\
COLLECTION_INTERVAL=60,\
PARQUET_STORAGE_PATH=/app/data/parquet,\
REALTIME_ENABLED=true,\
EMPIRICAL_BAYES_K=50,\
DEFAULT_LOOKBACK_DAYS=7,\
USE_POSTGRESQL=false,\
FALLBACK_TO_PARQUET=true,\
ENABLE_DUAL_WRITE=false,\
GCS_BUCKET_NAME=cs6604-trafficsafety-parquet,\
GCS_PROJECT_ID=${PROJECT_NUMBER},\
ENABLE_GCS_UPLOAD=true,\
DATA_SOURCE=vcc" \
  --set-secrets "\
VCC_CLIENT_ID=vcc_client_id:latest,\
VCC_CLIENT_SECRET=vcc_client_secret:latest"

echo ""
echo "✅ Data Collector deployment complete!"
echo "Service URL: https://${SERVICE_NAME}-${PROJECT_ID}.${REGION}.run.app"
echo ""
echo "Monitor logs with:"
echo "  gcloud run services logs read ${SERVICE_NAME} --region=${REGION} --limit=50"
