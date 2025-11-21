# Docker Setup Guide

This guide explains how to run the Traffic Safety API using Docker.

## Prerequisites

- Docker Desktop installed (Windows/Mac) or Docker Engine (Linux)
- Docker Compose (usually included with Docker Desktop)
- Access to VTTI Smart Cities Trino database (for OAuth2 authentication)

## Quick Start

### 1. Set Up Environment Variables

Copy the example environment file:

```bash
cp .env.example .env
```

Edit `.env` if you need to change any default values. The defaults should work for most cases.

### 2. Build and Run with Docker Compose

```bash
docker-compose up --build
```

This will:
- Build the Docker image
- Start the API container
- Expose the API on http://localhost:8000

### 3. Verify It's Running

Open your browser to:
- **Health check:** http://localhost:8000/health
- **API docs:** http://localhost:8000/docs
- **Safety index endpoint:** http://localhost:8000/api/v1/safety/index/

Or use curl:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/api/v1/safety/index/
```

## Trino Authentication

The API needs to authenticate with Trino to query the smart-cities database. There are **three authentication methods** available:

### Method 1: OAuth Token Cache Mounting (RECOMMENDED - No Browser in Docker!)

**How it works:** Authenticate once on your host machine, then Docker uses the cached token.

**Steps:**

1. **Authenticate on your host machine first** (run your Jupyter notebook or any Trino query)
   - This creates a token cache at `C:\Users\YourUsername\.trino\token-cache.json`

2. **Token is automatically mounted into Docker** via docker-compose.yml volume:
   ```yaml
   volumes:
     - ${USERPROFILE}/.trino:/root/.trino
   ```

3. **Run Docker:**
   ```bash
   docker-compose up --build
   ```

**That's it!** Docker will use your cached token automatically.

---

### Method 2: Extract JWT Token (Alternative)

If you need to run Docker without the volume mount, extract the JWT token manually:

**Steps:**

1. **Run the token extractor script** (on host machine with browser):
   ```bash
   cd backend
   python extract_trino_token.py
   ```

2. **Copy the token to `.env` file:**
   ```env
   TRINO_JWT_TOKEN=eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...
   ```

3. **Run Docker:**
   ```bash
   docker-compose up --build
   ```

---

### Method 3: Basic Authentication (If Supported)

If your Trino server supports username/password authentication:

**Add to `.env` file:**
```env
TRINO_USERNAME=your_vtti_username
TRINO_PASSWORD=your_password
```

**Note:** Check with your Trino admin if this is enabled.

---

### Which Method to Use?

| Method | Pros | Cons | Recommended For |
|--------|------|------|-----------------|
| **OAuth Cache Mount** | ✅ Automatic, no extra steps | Requires host auth first | **Development (BEST)** |
| **JWT Token** | ✅ Works without volume | Manual token extraction | Production/CI/CD |
| **Basic Auth** | ✅ Simple credentials | May not be enabled | If available |

**For most users:** Just use Method 1 (OAuth Cache Mount) - it's already configured!

## Docker Commands

### Start the API (detached mode)

```bash
docker-compose up -d
```

### Stop the API

```bash
docker-compose down
```

### View logs

```bash
docker-compose logs -f api
```

### Rebuild after code changes

```bash
docker-compose up --build
```

### Restart the container

```bash
docker-compose restart
```

## Development Mode

The `docker-compose.yml` includes a volume mount that syncs your local `app/` directory with the container. This means:

1. Code changes are reflected immediately (with uvicorn's auto-reload)
2. No need to rebuild for Python file changes

To disable this (production mode), comment out the volumes section in `docker-compose.yml`:

```yaml
# volumes:
#   - ./app:/app/app
```

## Manual Docker Build (without docker-compose)

If you prefer to use Docker directly:

### Build the image

```bash
docker build -t safety-index-api .
```

### Run the container

```bash
docker run -p 8000:8000 --env-file .env safety-index-api
```

### Run with custom port

```bash
docker run -p 9000:8000 --env-file .env safety-index-api
```

Access at: http://localhost:9000

## Troubleshooting

### Container won't start

1. Check logs:
   ```bash
   docker-compose logs api
   ```

2. Verify environment variables are set correctly in `.env`

3. Make sure port 8000 is not already in use:
   ```bash
   # Windows
   netstat -ano | findstr :8000

   # Mac/Linux
   lsof -i :8000
   ```

### Trino authentication errors

The API uses OAuth2 authentication for Trino. When you first access an endpoint that queries the database:

1. A browser window will open for authentication
2. Log in with your VTTI credentials
3. The token will be cached for subsequent requests

If authentication fails:
- Ensure you have valid VTTI credentials
- Check that `TRINO_HOST` is set correctly in `.env`
- Try accessing the API from a browser first (not curl) to complete OAuth flow

### No data returned

If `/api/v1/safety/index/` returns an empty list:

1. Check logs for error messages: `docker-compose logs api`
2. Verify date range has data in Trino (last 24 hours)
3. Confirm your account has access to the `alexandria` schema in Trino

### Out of memory errors

If the container crashes due to memory:

1. Increase Docker memory limit in Docker Desktop settings (Recommended: 4GB minimum)
2. Reduce `DEFAULT_LOOKBACK_DAYS` in `.env` to process less data

## Configuration Options

All settings can be configured via environment variables in `.env`:

| Variable | Default | Description |
|----------|---------|-------------|
| `PROJECT_NAME` | Traffic Safety API | API display name |
| `VERSION` | 0.1.0 | API version |
| `DEBUG` | true | Enable debug mode |
| `BASE_URL` | http://localhost:8000 | Base URL for the service |
| `TRINO_HOST` | smart-cities-trino.pre-prod.cloud.vtti.vt.edu | Trino server hostname |
| `TRINO_PORT` | 443 | Trino server port |
| `TRINO_HTTP_SCHEME` | https | HTTP or HTTPS |
| `TRINO_CATALOG` | smartcities_iceberg | Trino catalog name |
| `EMPIRICAL_BAYES_K` | 50 | Tuning parameter for EB adjustment |
| `DEFAULT_LOOKBACK_DAYS` | 7 | Default analysis window |

## Next Steps

- **Test the API:** Use the interactive docs at http://localhost:8000/docs
- **Implement full version:** See [INTEGRATION_GUIDE.md](INTEGRATION_GUIDE.md) for Option A (complete implementation)
- **Monitor performance:** Check logs for query times and optimize as needed
- **Production deployment:** Remove volume mounts, set `DEBUG=false`, use proper secrets management

## API Endpoints

Once running, you can access:

- `GET /health` - Health check
- `GET /api/v1/safety/index/` - List all intersections with current safety indices
- `GET /api/v1/safety/index/{intersection_id}` - Get specific intersection details

See [README_API.md](README_API.md) for detailed API documentation.
