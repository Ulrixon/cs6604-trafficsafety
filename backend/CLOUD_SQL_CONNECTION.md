# Cloud SQL Connection Configuration

This document explains how the application connects to the PostgreSQL database differently in local development vs Cloud Run.

## Connection Modes

### 1. **Local Development** (TCP Connection)
When running locally (via Cloud SQL Proxy or direct connection):
- Uses **TCP/IP connection**
- Connects to `VTTI_DB_HOST:VTTI_DB_PORT`
- Example: `127.0.0.1:9470` (Cloud SQL Proxy) or `34.140.49.230:5432` (direct IP)

### 2. **Cloud Run** (Unix Socket Connection)
When deployed to Cloud Run:
- Uses **Unix socket connection** via Cloud SQL Proxy built into Cloud Run
- Connects to `/cloudsql/INSTANCE_CONNECTION_NAME`
- No need for external IP or port
- More secure and efficient

## How It Works

The `db_client.py` automatically detects which mode to use:

```python
instance_connection_name = os.getenv("VTTI_DB_INSTANCE_CONNECTION_NAME")

if instance_connection_name:
    # Cloud Run: Use Unix socket
    self.host = f"/cloudsql/{instance_connection_name}"
    self.port = None
else:
    # Local: Use TCP connection
    self.host = host or os.getenv("VTTI_DB_HOST", "127.0.0.1")
    self.port = int(port or os.getenv("VTTI_DB_PORT", "9470"))
```

## Environment Variables

### For Local Development
```bash
# .env file
VTTI_DB_HOST=127.0.0.1
VTTI_DB_PORT=9470
VTTI_DB_NAME=vtsi
VTTI_DB_USER=postgres
VTTI_DB_PASSWORD=your_password
```

### For Cloud Run
```bash
# Set in deploy-gcp.sh
VTTI_DB_INSTANCE_CONNECTION_NAME=symbolic-cinema-305010:europe-west1:vtsi-postgres
VTTI_DB_NAME=vtti_db
VTTI_DB_USER=<from Secret Manager>
VTTI_DB_PASSWORD=<from Secret Manager>

# VTTI_DB_HOST and VTTI_DB_PORT are NOT used when VTTI_DB_INSTANCE_CONNECTION_NAME is set
```

## Cloud Run Deployment

The deployment script (`deploy-gcp.sh`) configures Cloud Run with:

1. **Cloud SQL instance connection** via `--add-cloudsql-instances`:
   ```bash
   --add-cloudsql-instances symbolic-cinema-305010:europe-west1:vtsi-postgres
   ```
   This tells Cloud Run to mount the Unix socket for this Cloud SQL instance.

2. **Environment variable** to enable Unix socket mode:
   ```bash
   --set-env-vars "VTTI_DB_INSTANCE_CONNECTION_NAME=symbolic-cinema-305010:europe-west1:vtsi-postgres,..."
   ```

3. **Secret Manager** for credentials:
   ```bash
   --set-secrets "VTTI_DB_USER=db_user:1,VTTI_DB_PASSWORD=db_password:1"
   ```

## Benefits of This Approach

### Local Development
- ✅ Easy to test with Cloud SQL Proxy
- ✅ Can connect to remote databases directly
- ✅ Flexible port configuration

### Cloud Run Production
- ✅ No need for public IP on database
- ✅ More secure (no network exposure)
- ✅ Better performance (Unix socket vs TCP)
- ✅ Built-in Cloud SQL Proxy (no manual setup)
- ✅ Automatic credential rotation support

## Testing

### Test Local Connection
```bash
cd backend
export VTTI_DB_HOST=127.0.0.1
export VTTI_DB_PORT=9470
export VTTI_DB_NAME=vtsi
export VTTI_DB_USER=postgres
export VTTI_DB_PASSWORD=your_password
python -c "from app.services.db_client import get_db_client; client = get_db_client(); print('✓ Connected')"
```

### Test Cloud Run Connection
After deployment:
```bash
curl https://cs6604-trafficsafety-180117512369.europe-west1.run.app/health
curl https://cs6604-trafficsafety-180117512369.europe-west1.run.app/api/v1/safety/index/
```

## Troubleshooting

### Issue: "Connection refused" in Cloud Run
- **Cause**: Cloud SQL instance not properly connected
- **Solution**: Verify `--add-cloudsql-instances` matches your actual instance name
- **Check**: `gcloud sql instances list --project=symbolic-cinema-305010`

### Issue: "No such file or directory: /cloudsql/..."
- **Cause**: `VTTI_DB_INSTANCE_CONNECTION_NAME` set but instance not mounted
- **Solution**: Ensure `--add-cloudsql-instances` is in deployment script

### Issue: Works locally but fails in Cloud Run
- **Cause**: Database credentials different between local and production
- **Solution**: Verify Secret Manager secrets are correct:
  ```bash
  gcloud secrets versions access 1 --secret=db_user --project=180117512369
  gcloud secrets versions access 1 --secret=db_password --project=180117512369
  ```

## Instance Connection Name Format

The Cloud SQL instance connection name follows this format:
```
PROJECT_ID:REGION:INSTANCE_NAME
```

Example:
```
symbolic-cinema-305010:europe-west1:vtsi-postgres
```

To find your instance connection name:
```bash
gcloud sql instances describe INSTANCE_NAME --project=PROJECT_ID --format="value(connectionName)"
```
