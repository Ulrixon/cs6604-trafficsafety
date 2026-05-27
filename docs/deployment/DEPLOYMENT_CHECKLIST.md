# GCP Deployment Checklist

## Pre-Deployment

- [ ] Google Cloud SDK installed and authenticated.
- [ ] Docker installed and running for manual deploys.
- [ ] Project set to `symbolic-cinema-305010`.
- [ ] Artifact Registry repository `cloud-run-source-deploy` exists in `europe-west1`.
- [ ] Required APIs enabled: Cloud Run, Cloud Build, Artifact Registry, Secret Manager.
- [ ] Backend secrets exist in Secret Manager.

## Frontend

- [ ] `frontend/Dockerfile` builds successfully.
- [ ] `frontend/Dockerfile` has the correct `ARG VITE_API_URL`.
- [ ] `cd frontend && npm ci && npm run build` passes.
- [ ] Cloud Run service is `safety-index-frontend`.
- [ ] Container port is `8080`.
- [ ] Health endpoint responds at `/health`.
- [ ] Browser can load `https://safety-index-frontend-6mb53achqa-ew.a.run.app/`.

Manual deploy:

```bash
cd frontend
./deploy-gcp.sh
```

## Backend

- [ ] `backend/Dockerfile` builds successfully.
- [ ] `backend/deploy-gcp.sh` has the right Cloud SQL and Secret Manager settings.
- [ ] Cloud Run service is `cs6604-trafficsafety`.
- [ ] Health endpoint responds at `/health`.

Manual deploy:

```bash
cd backend
./deploy-gcp.sh
```

## Cloud Build Triggers

- [ ] Frontend trigger is enabled for `^main$`.
- [ ] Backend trigger is enabled for `^main$`.
- [ ] Trigger service account can build, push to Artifact Registry, and update Cloud Run.

## Post-Deployment Smoke Tests

```bash
curl https://cs6604-trafficsafety-6mb53achqa-ew.a.run.app/health
curl https://cs6604-trafficsafety-6mb53achqa-ew.a.run.app/api/v1/safety/index/
curl https://safety-index-frontend-6mb53achqa-ew.a.run.app/health
```

## Rollback

```bash
gcloud run revisions list \
  --service safety-index-frontend \
  --region europe-west1 \
  --project symbolic-cinema-305010

gcloud run services update-traffic safety-index-frontend \
  --to-revisions REVISION_NAME=100 \
  --region europe-west1 \
  --project symbolic-cinema-305010
```
