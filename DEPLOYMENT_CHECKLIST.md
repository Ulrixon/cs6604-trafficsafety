# GCP Deployment Checklist

## Pre-Deployment

- [ ] Google Cloud SDK installed and configured
- [ ] Docker installed and running
- [ ] Authenticated with GCP: `gcloud auth login`
- [ ] Project set: `gcloud config set project 180117512369`
- [ ] Required APIs enabled (Run, Container Registry, Secret Manager)
- [ ] Database accessible from Cloud Run (firewall rules configured)
- [ ] Secrets created in Secret Manager:
  - [ ] `db_user` (version 1)
  - [ ] `db_password` (version 1)

## Backend Deployment

- [ ] Review `backend/Dockerfile`
- [ ] Review `backend/docker-entrypoint.sh`
- [ ] Update environment variables if needed
- [ ] Make scripts executable: `chmod +x backend/*.sh`
- [ ] Run deployment: `cd backend && ./deploy-gcp.sh`
- [ ] Verify health: `curl https://cs6604-trafficsafety-180117512369.europe-west1.run.app/health`
- [ ] Test API endpoint: `curl https://cs6604-trafficsafety-180117512369.europe-west1.run.app/api/v1/safety/index/`
- [ ] Check logs: `gcloud logging tail "resource.labels.service_name=cs6604-trafficsafety-backend"`

## Frontend Deployment

- [ ] Review `frontend/Dockerfile` - ensure backend URL is correct
- [ ] Make scripts executable: `chmod +x frontend/*.sh`
- [ ] Run deployment: `cd frontend && ./deploy-gcp.sh`
- [ ] Get frontend URL: `gcloud run services describe cs6604-trafficsafety-frontend --region europe-west1 --format 'value(status.url)'`
- [ ] Open in browser and test:
  - [ ] Main dashboard loads
  - [ ] Map shows intersection(s)
  - [ ] Trend Analysis page accessible
  - [ ] Data loads from backend
- [ ] Check logs: `gcloud logging tail "resource.labels.service_name=cs6604-trafficsafety-frontend"`

## Post-Deployment

- [ ] Test end-to-end flow:
  - [ ] Frontend → Backend → Database
  - [ ] MCDM calculations working
  - [ ] Time-based queries working
  - [ ] Trend charts displaying
- [ ] Monitor for errors
- [ ] Set up alerts (optional)
- [ ] Document frontend URL for users
- [ ] Consider setting up custom domain (optional)

## Rollback Plan

If deployment fails:
```bash
# Rollback backend
gcloud run services update-traffic cs6604-trafficsafety-backend \
  --to-revisions <PREVIOUS_REVISION>=100 \
  --region europe-west1

# Rollback frontend
gcloud run services update-traffic cs6604-trafficsafety-frontend \
  --to-revisions <PREVIOUS_REVISION>=100 \
  --region europe-west1
```

## Key Commands

```bash
# Backend health check
curl https://cs6604-trafficsafety-180117512369.europe-west1.run.app/health

# Backend API test
curl https://cs6604-trafficsafety-180117512369.europe-west1.run.app/api/v1/safety/index/

# Backend API docs
open https://cs6604-trafficsafety-180117512369.europe-west1.run.app/docs

# View backend logs
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=cs6604-trafficsafety-backend" --limit 20

# View frontend logs
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=cs6604-trafficsafety-frontend" --limit 20

# Get frontend URL
gcloud run services describe cs6604-trafficsafety-frontend --region europe-west1 --format 'value(status.url)'
```

## Troubleshooting

### Backend Issues
- **Database connection failed**: Check firewall rules, verify DB credentials in Secret Manager
- **Secret access denied**: Grant Secret Manager accessor role to Cloud Run service account
- **Timeout**: Increase timeout or CPU/memory allocation

### Frontend Issues
- **Can't reach backend**: Verify backend URL in Dockerfile, check backend is running
- **Slow loading**: Increase memory/CPU, check API_CACHE_TTL setting
- **Chart errors**: Check plotly is installed, verify data format from backend

### Common Fixes
```bash
# Update backend environment variables
gcloud run services update cs6604-trafficsafety-backend \
  --set-env-vars "VTTI_DB_HOST=34.140.49.230" \
  --region europe-west1

# Scale up instances
gcloud run services update cs6604-trafficsafety-backend \
  --min-instances 1 \
  --region europe-west1

# Increase memory
gcloud run services update cs6604-trafficsafety-backend \
  --memory 4Gi \
  --region europe-west1
```
