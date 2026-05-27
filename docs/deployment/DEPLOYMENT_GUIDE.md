# Cloud Run Deployment Guide

This project deploys two Cloud Run services from the same repository:

- Backend API: `cs6604-trafficsafety`
- Frontend dashboard: `safety-index-frontend`

Both Cloud Build triggers are configured for pushes to `main`.

## Frontend

The active frontend is the Vite React app in `frontend/`.

Cloud Build trigger behavior:

```text
docker build frontend -f frontend/Dockerfile
docker push europe-west1-docker.pkg.dev/.../safety-index-frontend:$COMMIT_SHA
gcloud run services update safety-index-frontend --image ...
```

The frontend container:

- Builds Vite with `npm ci && npm run build`
- Serves `dist/` with nginx
- Listens on port `8080`
- Exposes `/health`

Manual deployment:

```bash
cd frontend
./deploy-gcp.sh
```

Important: `VITE_API_URL` is a Vite build-time value. If the backend URL changes, update the Docker build arg in `frontend/deploy-gcp.sh` or the default `ARG VITE_API_URL` in `frontend/Dockerfile`.

## Backend

Manual backend deployment:

```bash
cd backend
./deploy-gcp.sh
```

Backend service URL:

```text
https://cs6604-trafficsafety-6mb53achqa-ew.a.run.app
```

Health check:

```bash
curl https://cs6604-trafficsafety-6mb53achqa-ew.a.run.app/health
```

## Cloud Build Triggers

Current triggers:

- `rmgpgab-safety-index-frontend-europe-west1-Ulrixon-cs6604-trhid`
- `rmgpgab-cs6604-trafficsafety-europe-west1-Ulrixon-cs6604-trakvx`

Both trigger on `^main$`. There are no path filters, so a push to `main` can rebuild both services.

## Verify Frontend

```bash
curl -I https://safety-index-frontend-6mb53achqa-ew.a.run.app/
curl https://safety-index-frontend-6mb53achqa-ew.a.run.app/health
```

## Rollback

List revisions:

```bash
gcloud run revisions list \
  --service safety-index-frontend \
  --region europe-west1 \
  --project symbolic-cinema-305010
```

Route traffic to a known-good revision:

```bash
gcloud run services update-traffic safety-index-frontend \
  --to-revisions REVISION_NAME=100 \
  --region europe-west1 \
  --project symbolic-cinema-305010
```
