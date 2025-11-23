# Cloud Run Deployment Troubleshooting

## Error: Container failed to start on PORT=8080

### Possible Causes & Solutions

### 1. **Startup Timeout (Most Common)**

Cloud Run default timeout is 60 seconds. The app might be taking too long to start due to:
- Database connection delays
- Heavy imports
- Lambda optimization calculations

**Solution**: Increase the startup timeout

```bash
gcloud run services update traffic-safety-backend \
  --region us-east1 \
  --timeout 300 \
  --startup-cpu-boost
```

### 2. **Database Connection Issues**

The app might be trying to connect to the database during startup and failing.

**Check**: Database credentials and connection

```bash
# Verify secret manager secrets
gcloud secrets versions access latest --secret="vtti-db-password"

# Test database connectivity
gcloud compute ssh <instance-name> --zone=us-east1-b -- \
  'psql -h 34.140.49.230 -U postgres -d vtsi -c "SELECT 1;"'
```

**Solution**: Ensure database secrets are properly bound

```bash
gcloud run services update traffic-safety-backend \
  --set-secrets=VTTI_DB_PASSWORD=vtti-db-password:latest \
  --set-env-vars=VTTI_DB_HOST=34.140.49.230 \
  --set-env-vars=VTTI_DB_PORT=5432 \
  --set-env-vars=VTTI_DB_NAME=vtsi \
  --set-env-vars=VTTI_DB_USER=postgres
```

### 3. **Import Errors from Recent Changes**

Recent code changes might have syntax or import errors.

**Test locally first**:

```bash
cd backend
python test_startup.py
```

**Check for errors**:

```bash
# Build and test the Docker image locally
cd backend
docker build -t traffic-safety-backend:test .
docker run -p 8080:8080 \
  -e VTTI_DB_HOST=34.140.49.230 \
  -e VTTI_DB_PORT=5432 \
  -e VTTI_DB_NAME=vtsi \
  -e VTTI_DB_USER=postgres \
  -e VTTI_DB_PASSWORD=<password> \
  traffic-safety-backend:test

# Test the endpoint
curl http://localhost:8080/health
```

### 4. **Missing Dependencies**

**Check**: requirements.txt includes all necessary packages

```bash
# From backend directory
cat requirements.txt | grep -E "(fastapi|uvicorn|psycopg2)"
```

**Required packages**:
- fastapi
- uvicorn[standard]
- psycopg2-binary
- pydantic
- requests

### 5. **Port Configuration**

**Verify**: The app listens on $PORT (Cloud Run sets this to 8080)

**Check docker-entrypoint.sh**:
```bash
PORT=${PORT:-8080}
exec uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

### 6. **Memory/CPU Limits**

The app might be OOM killed or CPU throttled.

**Solution**: Increase resources

```bash
gcloud run services update traffic-safety-backend \
  --memory 2Gi \
  --cpu 2 \
  --min-instances 1 \
  --max-instances 10
```

### 7. **Health Check Configuration**

Cloud Run might be checking the wrong endpoint.

**Solution**: Configure health check properly

```bash
gcloud run services update traffic-safety-backend \
  --no-use-http2 \
  --startup-probe-initial-delay 30 \
  --startup-probe-period 10 \
  --startup-probe-timeout 5 \
  --startup-probe-failure-threshold 6
```

## Recommended Deployment Command

```bash
gcloud run deploy traffic-safety-backend \
  --source ./backend \
  --region us-east1 \
  --platform managed \
  --port 8080 \
  --timeout 300 \
  --memory 2Gi \
  --cpu 2 \
  --min-instances 0 \
  --max-instances 10 \
  --startup-cpu-boost \
  --allow-unauthenticated \
  --set-env-vars=VTTI_DB_HOST=34.140.49.230 \
  --set-env-vars=VTTI_DB_PORT=5432 \
  --set-env-vars=VTTI_DB_NAME=vtsi \
  --set-env-vars=VTTI_DB_USER=postgres \
  --set-secrets=VTTI_DB_PASSWORD=vtti-db-password:latest \
  --startup-probe-initial-delay 30 \
  --startup-probe-period 10 \
  --startup-probe-timeout 10 \
  --startup-probe-failure-threshold 6
```

## Check Logs

```bash
# View recent logs
gcloud run services logs read traffic-safety-backend \
  --region us-east1 \
  --limit 100

# Stream logs in real-time
gcloud run services logs tail traffic-safety-backend \
  --region us-east1
```

## Test After Deployment

```bash
# Get the service URL
SERVICE_URL=$(gcloud run services describe traffic-safety-backend \
  --region us-east1 \
  --format='value(status.url)')

# Test health endpoint
curl $SERVICE_URL/health

# Test API endpoint
curl "$SERVICE_URL/api/v1/safety/index/intersections/list"
```

## Common Error Patterns

### "Container failed to start"
- **Cause**: Startup timeout or crash during initialization
- **Fix**: Increase timeout, check logs for Python errors

### "Error: Could not connect to Cloud SQL"
- **Cause**: Database credentials or connection issues
- **Fix**: Verify secrets, check database is accessible

### "ModuleNotFoundError"
- **Cause**: Missing dependency in requirements.txt
- **Fix**: Add missing package and rebuild

### "Port already in use"
- **Cause**: Multiple processes trying to bind to same port
- **Fix**: Ensure only one uvicorn process in entrypoint script

## Quick Fixes to Try

```bash
# 1. Increase timeout and resources
gcloud run services update traffic-safety-backend \
  --region us-east1 \
  --timeout 300 \
  --memory 2Gi \
  --cpu 2 \
  --startup-cpu-boost

# 2. Add startup probe configuration
gcloud run services update traffic-safety-backend \
  --region us-east1 \
  --startup-probe-initial-delay 30 \
  --startup-probe-period 10 \
  --startup-probe-timeout 10 \
  --startup-probe-failure-threshold 6

# 3. Set minimum instances (keeps app warm)
gcloud run services update traffic-safety-backend \
  --region us-east1 \
  --min-instances 1
```

## Debug Mode

To see detailed startup logs:

```bash
# Deploy with increased verbosity
gcloud run deploy traffic-safety-backend \
  --source ./backend \
  --region us-east1 \
  --verbosity=debug
```

---

**Last Updated**: November 22, 2025
**Status**: Troubleshooting Cloud Run deployment
