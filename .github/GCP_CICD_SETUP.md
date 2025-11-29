# GitHub Actions CI/CD Setup Guide

This guide explains how to set up automatic deployment to Google Cloud Run using GitHub Actions.

## Overview

When you push code to the `main` branch:
- Backend changes automatically deploy to Cloud Run backend service
- Frontend changes automatically deploy to Cloud Run frontend service
- Tests run on all pull requests

## Prerequisites

- Google Cloud SDK (`gcloud`) installed and authenticated
- Access to GCP project `180117512369`
- Admin permissions on the GitHub repository

## Step-by-Step Setup

### Step 1: Enable Required GCP APIs

Run this command to enable the necessary Google Cloud APIs:

```bash
gcloud services enable \
  run.googleapis.com \
  containerregistry.googleapis.com \
  iamcredentials.googleapis.com \
  secretmanager.googleapis.com \
  --project=180117512369
```

### Step 2: Create Workload Identity Pool

This allows GitHub Actions to authenticate with GCP without storing service account keys.

```bash
# Create workload identity pool
gcloud iam workload-identity-pools create "github-pool" \
  --project="180117512369" \
  --location="global" \
  --display-name="GitHub Actions Pool"

# Create workload identity provider
gcloud iam workload-identity-pools providers create-oidc "github-provider" \
  --project="180117512369" \
  --location="global" \
  --workload-identity-pool="github-pool" \
  --display-name="GitHub Provider" \
  --attribute-mapping="google.subject=assertion.sub,attribute.actor=assertion.actor,attribute.repository=assertion.repository,attribute.repository_owner=assertion.repository_owner" \
  --attribute-condition="assertion.repository_owner=='Ulrixon'" \
  --issuer-uri="https://token.actions.githubusercontent.com"
```

### Step 3: Create Service Account

```bash
# Create service account
gcloud iam service-accounts create github-actions \
  --display-name="GitHub Actions Service Account" \
  --project=180117512369
```

### Step 4: Grant IAM Permissions

```bash
# Grant Cloud Run Admin role
gcloud projects add-iam-policy-binding 180117512369 \
  --member="serviceAccount:github-actions@180117512369.iam.gserviceaccount.com" \
  --role="roles/run.admin"

# Grant Storage Admin role (for GCR)
gcloud projects add-iam-policy-binding 180117512369 \
  --member="serviceAccount:github-actions@180117512369.iam.gserviceaccount.com" \
  --role="roles/storage.admin"

# Grant Service Account User role
gcloud projects add-iam-policy-binding 180117512369 \
  --member="serviceAccount:github-actions@180117512369.iam.gserviceaccount.com" \
  --role="roles/iam.serviceAccountUser"
```

### Step 5: Grant Secret Manager Access

```bash
# Grant access to db_user secret
gcloud secrets add-iam-policy-binding db_user \
  --member="serviceAccount:github-actions@180117512369.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor" \
  --project=180117512369

# Grant access to db_password secret
gcloud secrets add-iam-policy-binding db_password \
  --member="serviceAccount:github-actions@180117512369.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor" \
  --project=180117512369
```

### Step 6: Allow Workload Identity Federation

```bash
# Allow GitHub Actions to impersonate the service account
gcloud iam service-accounts add-iam-policy-binding \
  github-actions@180117512369.iam.gserviceaccount.com \
  --project=180117512369 \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/projects/180117512369/locations/global/workloadIdentityPools/github-pool/attribute.repository/Ulrixon/cs6604-trafficsafety"
```

### Step 7: Verify Setup

```bash
# Verify workload identity pool
gcloud iam workload-identity-pools describe github-pool \
  --location=global \
  --project=180117512369

# Verify service account
gcloud iam service-accounts describe \
  github-actions@180117512369.iam.gserviceaccount.com \
  --project=180117512369
```

## Testing the Setup

### Option 1: Test on a Feature Branch First

```bash
# Create test branch
git checkout -b test-cicd

# Make a small change to trigger deployment
echo "# Testing CI/CD" >> backend/README.md

# Commit and push
git add .github/ backend/README.md
git commit -m "test: Add GitHub Actions CI/CD workflows"
git push origin test-cicd

# Go to GitHub and check Actions tab to see the workflow run
```

### Option 2: Manual Workflow Trigger

1. Go to your GitHub repository
2. Click on "Actions" tab
3. Select "Deploy Backend to Cloud Run" or "Deploy Frontend to Cloud Run"
4. Click "Run workflow"
5. Select branch "main"
6. Click "Run workflow"

## Monitoring Deployments

### GitHub Actions
- View workflow runs: `https://github.com/Ulrixon/cs6604-trafficsafety/actions`
- Check logs for each deployment step
- View build times and success/failure status

### Cloud Run
```bash
# Check backend service status
gcloud run services describe cs6604-trafficsafety-backend \
  --region=europe-west1 \
  --project=180117512369

# Check frontend service status
gcloud run services describe safety-index-frontend \
  --region=europe-west1 \
  --project=180117512369

# View recent revisions
gcloud run revisions list \
  --service=cs6604-trafficsafety-backend \
  --region=europe-west1 \
  --project=180117512369
```

## Troubleshooting

### Common Issues

**Issue: Workload Identity authentication fails**
```
Error: google-github-actions/auth failed with: retry function failed after 3 attempts
```

**Solution:** Verify the workload identity pool provider is correctly configured:
```bash
gcloud iam workload-identity-pools providers describe github-provider \
  --workload-identity-pool=github-pool \
  --location=global \
  --project=180117512369
```

**Issue: Permission denied when deploying to Cloud Run**
```
Error: User [github-actions@180117512369.iam.gserviceaccount.com] does not have permission
```

**Solution:** Re-run Step 4 to ensure all IAM permissions are granted.

**Issue: Secret not found**
```
Error: Secret [db_user] not found
```

**Solution:** Verify secrets exist:
```bash
gcloud secrets list --project=180117512369
```

### Useful Commands

```bash
# View GitHub Actions service account permissions
gcloud projects get-iam-policy 180117512369 \
  --flatten="bindings[].members" \
  --filter="bindings.members:github-actions@180117512369.iam.gserviceaccount.com"

# Test Docker build locally
cd backend
docker build -t test-backend .

# View Cloud Run logs
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=cs6604-trafficsafety-backend" \
  --limit=50 \
  --project=180117512369
```

## Workflow Triggers

### Deploy Backend
- Triggers on: Push to `main` when `backend/**` files change
- Manual trigger: Available via GitHub Actions UI

### Deploy Frontend
- Triggers on: Push to `main` when `frontend/**` files change
- Manual trigger: Available via GitHub Actions UI

### Run Tests
- Triggers on: All pull requests and pushes to `main`
- Runs linting and tests for both backend and frontend

## Cost Estimate

- **GitHub Actions**: FREE (2,000 minutes/month included)
- **Container Registry storage**: ~$0.10/month
- **Cloud Run deployments**: No extra cost (same as manual)

**Total estimated cost: $0/month** (within free tiers)

## Next Steps

1. Run the setup commands above
2. Push workflow files to GitHub
3. Make a test change to verify automatic deployment
4. Monitor the Actions tab for successful deployment
5. Verify services are running at:
   - Backend: https://cs6604-trafficsafety-180117512369.europe-west1.run.app
   - Frontend: https://safety-index-frontend-180117512369.europe-west1.run.app

## Security Notes

- ✅ No service account keys stored in GitHub
- ✅ Workload Identity Federation provides secure authentication
- ✅ Service account has minimal required permissions
- ✅ Secrets managed in GCP Secret Manager
- ✅ All deployments logged and auditable
