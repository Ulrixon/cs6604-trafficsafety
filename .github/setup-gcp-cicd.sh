#!/bin/bash
# Setup script for GitHub Actions CI/CD with GCP Cloud Run
# Run this script once to configure Workload Identity Federation and permissions

set -e

PROJECT_ID="180117512369"
SERVICE_ACCOUNT_NAME="github-actions"
SERVICE_ACCOUNT_EMAIL="${SERVICE_ACCOUNT_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
POOL_NAME="github-pool"
PROVIDER_NAME="github-provider"
REPO_OWNER="Ulrixon"
REPO_NAME="cs6604-trafficsafety"

echo "========================================"
echo "GitHub Actions CI/CD Setup for GCP"
echo "========================================"
echo "Project ID: ${PROJECT_ID}"
echo "Service Account: ${SERVICE_ACCOUNT_EMAIL}"
echo "Repository: ${REPO_OWNER}/${REPO_NAME}"
echo ""

# Step 1: Enable APIs
echo "Step 1/6: Enabling required GCP APIs..."
gcloud services enable \
  run.googleapis.com \
  containerregistry.googleapis.com \
  iamcredentials.googleapis.com \
  secretmanager.googleapis.com \
  --project=${PROJECT_ID}

echo "✓ APIs enabled"
echo ""

# Step 2: Create Workload Identity Pool
echo "Step 2/6: Creating Workload Identity Pool..."
if gcloud iam workload-identity-pools describe ${POOL_NAME} \
  --location=global \
  --project=${PROJECT_ID} &> /dev/null; then
  echo "⚠ Workload Identity Pool already exists, skipping..."
else
  gcloud iam workload-identity-pools create ${POOL_NAME} \
    --project=${PROJECT_ID} \
    --location=global \
    --display-name="GitHub Actions Pool"
  echo "✓ Workload Identity Pool created"
fi
echo ""

# Step 3: Create Workload Identity Provider
echo "Step 3/6: Creating Workload Identity Provider..."
if gcloud iam workload-identity-pools providers describe ${PROVIDER_NAME} \
  --workload-identity-pool=${POOL_NAME} \
  --location=global \
  --project=${PROJECT_ID} &> /dev/null; then
  echo "⚠ Provider already exists, skipping..."
else
  gcloud iam workload-identity-pools providers create-oidc ${PROVIDER_NAME} \
    --project=${PROJECT_ID} \
    --location=global \
    --workload-identity-pool=${POOL_NAME} \
    --display-name="GitHub Provider" \
    --attribute-mapping="google.subject=assertion.sub,attribute.actor=assertion.actor,attribute.repository=assertion.repository,attribute.repository_owner=assertion.repository_owner" \
    --attribute-condition="assertion.repository_owner=='${REPO_OWNER}'" \
    --issuer-uri="https://token.actions.githubusercontent.com"
  echo "✓ Workload Identity Provider created"
fi
echo ""

# Step 4: Create Service Account
echo "Step 4/6: Creating Service Account..."
if gcloud iam service-accounts describe ${SERVICE_ACCOUNT_EMAIL} \
  --project=${PROJECT_ID} &> /dev/null; then
  echo "⚠ Service Account already exists, skipping..."
else
  gcloud iam service-accounts create ${SERVICE_ACCOUNT_NAME} \
    --display-name="GitHub Actions Service Account" \
    --project=${PROJECT_ID}
  echo "✓ Service Account created"
fi
echo ""

# Step 5: Grant IAM Permissions
echo "Step 5/6: Granting IAM permissions..."

echo "  - Granting Cloud Run Admin..."
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
  --member="serviceAccount:${SERVICE_ACCOUNT_EMAIL}" \
  --role="roles/run.admin" \
  --condition=None \
  > /dev/null

echo "  - Granting Storage Admin..."
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
  --member="serviceAccount:${SERVICE_ACCOUNT_EMAIL}" \
  --role="roles/storage.admin" \
  --condition=None \
  > /dev/null

echo "  - Granting Service Account User..."
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
  --member="serviceAccount:${SERVICE_ACCOUNT_EMAIL}" \
  --role="roles/iam.serviceAccountUser" \
  --condition=None \
  > /dev/null

echo "  - Granting Secret Manager access to db_user..."
gcloud secrets add-iam-policy-binding db_user \
  --member="serviceAccount:${SERVICE_ACCOUNT_EMAIL}" \
  --role="roles/secretmanager.secretAccessor" \
  --project=${PROJECT_ID} \
  > /dev/null

echo "  - Granting Secret Manager access to db_password..."
gcloud secrets add-iam-policy-binding db_password \
  --member="serviceAccount:${SERVICE_ACCOUNT_EMAIL}" \
  --role="roles/secretmanager.secretAccessor" \
  --project=${PROJECT_ID} \
  > /dev/null

echo "✓ IAM permissions granted"
echo ""

# Step 6: Allow Workload Identity Federation
echo "Step 6/6: Configuring Workload Identity Federation..."
gcloud iam service-accounts add-iam-policy-binding ${SERVICE_ACCOUNT_EMAIL} \
  --project=${PROJECT_ID} \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/projects/${PROJECT_ID}/locations/global/workloadIdentityPools/${POOL_NAME}/attribute.repository/${REPO_OWNER}/${REPO_NAME}"

echo "✓ Workload Identity Federation configured"
echo ""

# Verification
echo "========================================"
echo "Setup Complete! Verifying configuration..."
echo "========================================"
echo ""

echo "Workload Identity Pool:"
gcloud iam workload-identity-pools describe ${POOL_NAME} \
  --location=global \
  --project=${PROJECT_ID} \
  --format="value(name, state)"
echo ""

echo "Service Account:"
gcloud iam service-accounts describe ${SERVICE_ACCOUNT_EMAIL} \
  --project=${PROJECT_ID} \
  --format="value(email, displayName)"
echo ""

echo "========================================"
echo "✓ GitHub Actions CI/CD setup complete!"
echo "========================================"
echo ""
echo "Next steps:"
echo "1. Commit and push the workflow files to GitHub:"
echo "   git add .github/"
echo "   git commit -m 'Add GitHub Actions CI/CD workflows'"
echo "   git push origin main"
echo ""
echo "2. Monitor deployments at:"
echo "   https://github.com/${REPO_OWNER}/${REPO_NAME}/actions"
echo ""
echo "3. Verify services:"
echo "   Backend:  https://cs6604-trafficsafety-180117512369.europe-west1.run.app/health"
echo "   Frontend: https://safety-index-frontend-180117512369.europe-west1.run.app"
echo ""
