#!/bin/bash
# Deploy Frontend to Google Cloud Run

set -e

PROJECT_ID="180117512369"
REGION="europe-west1"
SERVICE_NAME="cs6604-trafficsafety-frontend"
IMAGE_NAME="gcr.io/${PROJECT_ID}/${SERVICE_NAME}"

echo "=== Deploying Traffic Safety Frontend to Cloud Run ==="
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
  --min-instances 0

echo ""
echo "✅ Frontend deployment complete!"
echo ""
echo "Get the service URL with:"
echo "  gcloud run services describe ${SERVICE_NAME} --region ${REGION} --format 'value(status.url)'"
