#!/bin/bash
# Deploy Frontend to Google Cloud Run

set -e

PROJECT_ID="symbolic-cinema-305010"
REGION="europe-west1"
SERVICE_NAME="safety-index-frontend"
AR_HOSTNAME="${REGION}-docker.pkg.dev"
REPOSITORY="cloud-run-source-deploy"
IMAGE_NAME="${AR_HOSTNAME}/${PROJECT_ID}/${REPOSITORY}/${SERVICE_NAME}"

# Backend Cloud Run service URL (no trailing slash, no path)
BACKEND_URL="https://cs6604-trafficsafety-6mb53achqa-ew.a.run.app"

echo "=== Deploying Traffic Safety Frontend to Cloud Run ==="
echo "Project: ${PROJECT_ID}"
echo "Region: ${REGION}"
echo "Service: ${SERVICE_NAME}"
echo ""

# Build and push Docker image
echo "0. Configuring Docker authentication..."
gcloud auth configure-docker ${AR_HOSTNAME} --quiet
if ! gcloud artifacts repositories describe ${REPOSITORY} \
  --location ${REGION} \
  --project ${PROJECT_ID} >/dev/null 2>&1; then
  gcloud artifacts repositories create ${REPOSITORY} \
    --repository-format=docker \
    --location ${REGION} \
    --project ${PROJECT_ID} \
    --description="Cloud Run deployment images"
fi

echo ""
echo "1. Building Docker image..."
docker build \
  --build-arg VITE_API_URL="${BACKEND_URL}/api/v1" \
  -t ${IMAGE_NAME}:latest .

echo ""
echo "2. Pushing image to Artifact Registry..."
docker push ${IMAGE_NAME}:latest

echo ""
echo "3. Deploying to Cloud Run..."
gcloud run deploy ${SERVICE_NAME} \
  --image ${IMAGE_NAME}:latest \
  --platform managed \
  --region ${REGION} \
  --project ${PROJECT_ID} \
  --allow-unauthenticated \
  --port 8080 \
  --memory 1Gi \
  --cpu 1 \
  --timeout 300 \
  --max-instances 5 \
  --min-instances 0 \
  --set-env-vars "PORT=8080"

echo ""
echo "✅ Frontend deployment complete!"
echo ""
echo "Get the service URL with:"
echo "  gcloud run services describe ${SERVICE_NAME} --region ${REGION} --project ${PROJECT_ID} --format 'value(status.url)'"
