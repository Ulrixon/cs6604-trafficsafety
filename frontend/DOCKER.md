# Build and Test Docker Image Locally

This guide helps you test the Docker container before deploying to the cloud.

## Quick Test

```bash
cd frontend

# Build the image
docker build -t traffic-safety-dashboard .

# Run the container
docker run -p 8501:8501 traffic-safety-dashboard

# Open browser to http://localhost:8501
```

## Detailed Build and Test

### 1. Build the Image

```bash
cd frontend

# Build with tag
docker build -t traffic-safety-dashboard:latest .

# Build with build args (if needed)
docker build \
  --build-arg PYTHON_VERSION=3.9 \
  -t traffic-safety-dashboard:latest .
```

### 2. Test Locally

```bash
# Run container
docker run -p 8501:8501 \
  --name traffic-safety \
  traffic-safety-dashboard:latest

# Run in detached mode
docker run -d -p 8501:8501 \
  --name traffic-safety \
  traffic-safety-dashboard:latest

# Run with environment variables
docker run -p 8501:8501 \
  -e API_URL="https://your-api.com/..." \
  --name traffic-safety \
  traffic-safety-dashboard:latest
```

### 3. Test with Docker Compose

```bash
# Start services
docker-compose up

# Start in detached mode
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

### 4. Check Container Health

```bash
# Check if container is running
docker ps

# Check logs
docker logs traffic-safety

# Follow logs
docker logs -f traffic-safety

# Check health status
docker inspect --format='{{.State.Health.Status}}' traffic-safety

# Execute command in container
docker exec -it traffic-safety /bin/bash
```

### 5. Test the Application

```bash
# Open in browser
open http://localhost:8501

# Test health endpoint
curl http://localhost:8501/_stcore/health

# Test with different port
docker run -p 8080:8501 traffic-safety-dashboard
open http://localhost:8080
```

## Troubleshooting

### Container won't start

```bash
# Check logs
docker logs traffic-safety

# Run interactively to see errors
docker run -it traffic-safety-dashboard /bin/bash
```

### Port already in use

```bash
# Use different port
docker run -p 8502:8501 traffic-safety-dashboard

# Or stop other containers
docker ps
docker stop <container-id>
```

### Memory issues

```bash
# Run with memory limit
docker run -p 8501:8501 \
  --memory="1g" \
  traffic-safety-dashboard
```

### Image too large

```bash
# Check image size
docker images traffic-safety-dashboard

# Remove unused images
docker image prune

# Multi-stage build (already implemented in Dockerfile)
```

## Performance Testing

### 1. Measure Startup Time

```bash
time docker run -p 8501:8501 traffic-safety-dashboard
```

### 2. Check Resource Usage

```bash
# Monitor container stats
docker stats traffic-safety

# Check memory usage
docker stats --no-stream traffic-safety
```

### 3. Load Testing

```bash
# Install Apache Bench
brew install httpd  # macOS

# Simple load test
ab -n 1000 -c 10 http://localhost:8501/
```

## Optimization Tips

### 1. Layer Caching

The Dockerfile is optimized with:
- UV for faster package installation
- Requirements copied before code (better caching)
- Multi-stage pattern

### 2. Image Size

```bash
# Check image size
docker images traffic-safety-dashboard

# Current size: ~400-500MB (Python + dependencies)
```

### 3. Build Speed

```bash
# Use BuildKit for faster builds
DOCKER_BUILDKIT=1 docker build -t traffic-safety-dashboard .
```

## Cleanup

```bash
# Stop and remove container
docker stop traffic-safety
docker rm traffic-safety

# Remove image
docker rmi traffic-safety-dashboard

# Remove all stopped containers
docker container prune

# Remove unused images
docker image prune -a

# Clean everything (careful!)
docker system prune -a
```

## Push to Registry

### Docker Hub

```bash
# Login
docker login

# Tag
docker tag traffic-safety-dashboard:latest \
  YOUR_USERNAME/traffic-safety-dashboard:latest

# Push
docker push YOUR_USERNAME/traffic-safety-dashboard:latest
```

### Google Container Registry

```bash
# Tag
docker tag traffic-safety-dashboard:latest \
  gcr.io/YOUR_PROJECT_ID/traffic-safety-dashboard:latest

# Push
docker push gcr.io/YOUR_PROJECT_ID/traffic-safety-dashboard:latest
```

### AWS ECR

```bash
# Login
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS \
  --password-stdin YOUR_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com

# Tag
docker tag traffic-safety-dashboard:latest \
  YOUR_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/traffic-safety-dashboard:latest

# Push
docker push YOUR_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/traffic-safety-dashboard:latest
```

## Best Practices Checklist

✅ **Non-root user**: Container runs as `appuser` (not root)  
✅ **Health check**: Built-in health endpoint  
✅ **Environment variables**: Configurable via ENV  
✅ **Proper logging**: STDOUT/STDERR captured  
✅ **Security**: No secrets in image  
✅ **Size optimized**: Slim base image + UV  
✅ **Layer caching**: Requirements before code  
✅ **Graceful shutdown**: Streamlit handles SIGTERM  

## Ready for Production

Once local testing passes:

1. ✅ Container starts successfully
2. ✅ App loads at http://localhost:8501
3. ✅ Health check returns 200
4. ✅ API connection works (or fallback loads)
5. ✅ All features functional (map, filters, etc.)
6. ✅ No errors in logs

**→ Ready to deploy to cloud!** See [DEPLOYMENT.md](DEPLOYMENT.md) for cloud deployment instructions.
