#!/bin/bash
# Deploy Backend to Google Cloud Run with Secret Manager integration

set -e

PROJECT_ID="180117512369"
REGION="europe-west1"
SERVICE_NAME="cs6604-trafficsafety-backend"
IMAGE_NAME="gcr.io/${PROJECT_ID}/${SERVICE_NAME}"

echo "=== Deploying Traffic Safety Backend API to Cloud Run ==="
echo "Project: ${PROJECT_ID}"
echo "Region: ${REGION}"
echo "Service: ${SERVICE_NAME}"
echo ""

# Build and push Docker image
echo "1. Building Docker image..."
docker build -t ${IMAGE_NAME}:latest .

echo ""
echo "2. Pushing image to Google Container Registry..."
docker push ${IMAGE_NAME}:latest

echo ""
echo "3. Deploying to Cloud Run with Secret Manager integration..."
# Note: Using Cloud SQL instance connection name for Unix socket connection
# Format: PROJECT_ID:REGION:INSTANCE_NAME
CLOUD_SQL_INSTANCE="symbolic-cinema-305010:europe-west1:vtsi-postgres"

gcloud run deploy ${SERVICE_NAME} \
  --image ${IMAGE_NAME}:latest \
  --platform managed \
  --region ${REGION} \
  --project ${PROJECT_ID} \
  --allow-unauthenticated \
  --port 8080 \
  --memory 2Gi \
  --cpu 2 \
  --timeout 300 \
  --max-instances 10 \
  --min-instances 0 \
  --add-cloudsql-instances ${CLOUD_SQL_INSTANCE} \
  --set-env-vars "\
VTTI_DB_INSTANCE_CONNECTION_NAME=${CLOUD_SQL_INSTANCE},\
VTTI_DB_NAME=vtsi,\
MCDM_BIN_MINUTES=15,\
MCDM_LOOKBACK_HOURS=24,\
GCS_BUCKET_NAME=cs6604-trafficsafety-parquet,\
GCS_PROJECT_ID=${PROJECT_ID},\
ENABLE_GCS_UPLOAD=false,\
PARQUET_STORAGE_PATH=/gcs/cs6604-trafficsafety-parquet,\
USE_POSTGRESQL=false,\
FALLBACK_TO_PARQUET=true" \
  --set-secrets "VTTI_DB_USER=db_user:1,VTTI_DB_PASSWORD=db_password:1"

echo ""
echo "✅ Backend deployment complete!"
echo "Service URL: https://cs6604-trafficsafety-180117512369.europe-west1.run.app"
echo ""
echo "Test with:"
echo "  curl https://cs6604-trafficsafety-180117512369.europe-west1.run.app/health"
