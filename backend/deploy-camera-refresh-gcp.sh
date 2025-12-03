#!/bin/bash
#
# Deploy Camera Refresh to GCP Cloud Run Jobs + Cloud Scheduler
#
# Usage:
#   ./deploy-camera-refresh-gcp.sh PROJECT_ID SERVICE_ACCOUNT_EMAIL DATABASE_URL VDOT_API_KEY
#
# Example:
#   ./deploy-camera-refresh-gcp.sh \
#     my-project-123 \
#     camera-refresh@my-project-123.iam.gserviceaccount.com \
#     "postgresql://user:pass@host/db" \
#     "your-vdot-api-key"

set -e  # Exit on error

# Parse arguments
if [ "$#" -ne 4 ]; then
    echo "Usage: $0 PROJECT_ID SERVICE_ACCOUNT_EMAIL DATABASE_URL VDOT_API_KEY"
    exit 1
fi

PROJECT_ID=$1
SERVICE_ACCOUNT=$2
DATABASE_URL=$3
VDOT_API_KEY=$4

REGION="us-central1"
JOB_NAME="camera-refresh"
SCHEDULER_NAME="camera-refresh-daily"
SECRET_NAME="vdot-api-key"

echo "🚀 Deploying Camera Refresh to GCP"
echo "   Project: $PROJECT_ID"
echo "   Region: $REGION"
echo "   Service Account: $SERVICE_ACCOUNT"
echo ""

# Step 1: Enable required APIs
echo "📦 Enabling required GCP APIs..."
gcloud services enable \
  run.googleapis.com \
  cloudscheduler.googleapis.com \
  secretmanager.googleapis.com \
  cloudbuild.googleapis.com \
  --project=$PROJECT_ID

# Step 2: Create/Update secret in Secret Manager
echo "🔐 Storing VDOT API key in Secret Manager..."
if gcloud secrets describe $SECRET_NAME --project=$PROJECT_ID &>/dev/null; then
    echo "   Secret already exists, updating..."
    echo -n "$VDOT_API_KEY" | gcloud secrets versions add $SECRET_NAME \
      --data-file=- \
      --project=$PROJECT_ID
else
    echo "   Creating new secret..."
    echo -n "$VDOT_API_KEY" | gcloud secrets create $SECRET_NAME \
      --data-file=- \
      --replication-policy="automatic" \
      --project=$PROJECT_ID
fi

# Grant service account access to secret
echo "   Granting service account access to secret..."
gcloud secrets add-iam-policy-binding $SECRET_NAME \
  --member="serviceAccount:$SERVICE_ACCOUNT" \
  --role="roles/secretmanager.secretAccessor" \
  --project=$PROJECT_ID

# Step 3: Build and push container image
echo "🔨 Building container image..."
cd "$(dirname "$0")"
gcloud builds submit \
  --config=cloudbuild.camera-refresh.yaml \
  --project=$PROJECT_ID

# Step 4: Create or update Cloud Run Job
echo "☁️  Deploying Cloud Run Job..."
if gcloud run jobs describe $JOB_NAME --region=$REGION --project=$PROJECT_ID &>/dev/null; then
    echo "   Job exists, updating..."
    gcloud run jobs update $JOB_NAME \
      --image=gcr.io/$PROJECT_ID/camera-refresh:latest \
      --region=$REGION \
      --set-env-vars DATABASE_URL="$DATABASE_URL" \
      --set-secrets VDOT_API_KEY=$SECRET_NAME:latest \
      --max-retries 2 \
      --task-timeout 30m \
      --memory 512Mi \
      --cpu 1 \
      --service-account=$SERVICE_ACCOUNT \
      --project=$PROJECT_ID
else
    echo "   Creating new job..."
    gcloud run jobs create $JOB_NAME \
      --image=gcr.io/$PROJECT_ID/camera-refresh:latest \
      --region=$REGION \
      --set-env-vars DATABASE_URL="$DATABASE_URL" \
      --set-secrets VDOT_API_KEY=$SECRET_NAME:latest \
      --max-retries 2 \
      --task-timeout 30m \
      --memory 512Mi \
      --cpu 1 \
      --service-account=$SERVICE_ACCOUNT \
      --project=$PROJECT_ID
fi

# Step 5: Create or update Cloud Scheduler job
echo "⏰ Setting up Cloud Scheduler..."
SCHEDULER_URI="https://$REGION-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/$PROJECT_ID/jobs/$JOB_NAME:run"

if gcloud scheduler jobs describe $SCHEDULER_NAME --location=$REGION --project=$PROJECT_ID &>/dev/null; then
    echo "   Scheduler job exists, updating..."
    gcloud scheduler jobs update http $SCHEDULER_NAME \
      --location=$REGION \
      --schedule="0 2 * * *" \
      --uri="$SCHEDULER_URI" \
      --http-method=POST \
      --oauth-service-account-email=$SERVICE_ACCOUNT \
      --project=$PROJECT_ID
else
    echo "   Creating new scheduler job..."
    gcloud scheduler jobs create http $SCHEDULER_NAME \
      --location=$REGION \
      --schedule="0 2 * * *" \
      --uri="$SCHEDULER_URI" \
      --http-method=POST \
      --oauth-service-account-email=$SERVICE_ACCOUNT \
      --project=$PROJECT_ID
fi

echo ""
echo "✅ Deployment complete!"
echo ""
echo "📊 Summary:"
echo "   Cloud Run Job: $JOB_NAME"
echo "   Image: gcr.io/$PROJECT_ID/camera-refresh:latest"
echo "   Schedule: Daily at 2:00 AM (0 2 * * *)"
echo "   Region: $REGION"
echo ""
echo "🧪 Test the job manually:"
echo "   gcloud run jobs execute $JOB_NAME --region=$REGION --project=$PROJECT_ID"
echo ""
echo "📝 View logs:"
echo "   gcloud logging read \"resource.type=cloud_run_job AND resource.labels.job_name=$JOB_NAME\" --limit 50 --project=$PROJECT_ID"
echo ""
echo "💰 Estimated monthly cost: ~\$0.06"
echo ""
