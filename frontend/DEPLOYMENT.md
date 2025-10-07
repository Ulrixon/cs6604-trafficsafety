# Cloud Deployment Guide for Traffic Safety Dashboard

This guide covers deploying the Streamlit frontend to various cloud platforms.

---

## Table of Contents

1. [Google Cloud Run (GCP)](#google-cloud-run-gcp)
2. [AWS Elastic Container Service (ECS)](#aws-ecs)
3. [Azure Container Instances](#azure-container-instances)
4. [Heroku](#heroku)
5. [Streamlit Community Cloud](#streamlit-community-cloud)
6. [DigitalOcean App Platform](#digitalocean-app-platform)
7. [Fly.io](#flyio)
8. [Railway](#railway)

---

## 🚀 Google Cloud Run (GCP)

**Best for**: Serverless, auto-scaling, pay-per-use

### Prerequisites

```bash
# Install Google Cloud SDK
brew install google-cloud-sdk  # macOS
# or download from: https://cloud.google.com/sdk/docs/install

# Login
gcloud auth login

# Set project
gcloud config set project YOUR_PROJECT_ID
```

### Deployment Steps

#### Option 1: Using gcloud (Recommended)

```bash
cd frontend

# Build and deploy in one command
gcloud run deploy traffic-safety-dashboard \
  --source . \
  --region us-central1 \
  --platform managed \
  --allow-unauthenticated \
  --port 8501 \
  --memory 1Gi \
  --cpu 1 \
  --max-instances 10 \
  --timeout 300

# Get the URL
gcloud run services describe traffic-safety-dashboard \
  --region us-central1 \
  --format='value(status.url)'
```

#### Option 2: Using Cloud Build

```bash
# Build image
gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/traffic-safety-dashboard

# Deploy
gcloud run deploy traffic-safety-dashboard \
  --image gcr.io/YOUR_PROJECT_ID/traffic-safety-dashboard \
  --region us-central1 \
  --platform managed \
  --allow-unauthenticated \
  --port 8501
```

### Cloud Run Configuration File

Create `cloudrun.yaml`:

```yaml
apiVersion: serving.knative.dev/v1
kind: Service
metadata:
  name: traffic-safety-dashboard
spec:
  template:
    metadata:
      annotations:
        autoscaling.knative.dev/maxScale: "10"
        autoscaling.knative.dev/minScale: "0"
    spec:
      containerConcurrency: 80
      timeoutSeconds: 300
      containers:
        - image: gcr.io/YOUR_PROJECT_ID/traffic-safety-dashboard
          ports:
            - name: http1
              containerPort: 8501
          env:
            - name: PORT
              value: "8501"
          resources:
            limits:
              cpu: "1"
              memory: 1Gi
```

Deploy with:

```bash
gcloud run services replace cloudrun.yaml --region us-central1
```

### Cost Estimate (GCP)

- **Free tier**: 2M requests/month, 180K vCPU-seconds/month
- **After free tier**: ~$0.05 per hour of compute
- **Estimated**: $5-20/month for moderate traffic

---

## 🚀 AWS Elastic Container Service (ECS)

**Best for**: AWS ecosystem integration, fine-grained control

### Prerequisites

```bash
# Install AWS CLI
brew install awscli  # macOS

# Configure
aws configure
```

### Deployment Steps

#### 1. Create ECR Repository

```bash
# Create repository
aws ecr create-repository \
  --repository-name traffic-safety-dashboard \
  --region us-east-1

# Get login
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS \
  --password-stdin YOUR_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com
```

#### 2. Build and Push Image

```bash
cd frontend

# Build
docker build -t traffic-safety-dashboard .

# Tag
docker tag traffic-safety-dashboard:latest \
  YOUR_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/traffic-safety-dashboard:latest

# Push
docker push YOUR_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/traffic-safety-dashboard:latest
```

#### 3. Create ECS Task Definition

Create `ecs-task-definition.json`:

```json
{
  "family": "traffic-safety-dashboard",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "512",
  "memory": "1024",
  "containerDefinitions": [
    {
      "name": "traffic-safety-dashboard",
      "image": "YOUR_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/traffic-safety-dashboard:latest",
      "portMappings": [
        {
          "containerPort": 8501,
          "protocol": "tcp"
        }
      ],
      "essential": true,
      "environment": [
        {
          "name": "PORT",
          "value": "8501"
        }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/traffic-safety-dashboard",
          "awslogs-region": "us-east-1",
          "awslogs-stream-prefix": "ecs"
        }
      }
    }
  ]
}
```

#### 4. Deploy to ECS

```bash
# Create log group
aws logs create-log-group --log-group-name /ecs/traffic-safety-dashboard

# Register task definition
aws ecs register-task-definition --cli-input-json file://ecs-task-definition.json

# Create cluster
aws ecs create-cluster --cluster-name traffic-safety-cluster

# Create service (requires VPC, subnet, security group)
aws ecs create-service \
  --cluster traffic-safety-cluster \
  --service-name traffic-safety-service \
  --task-definition traffic-safety-dashboard \
  --desired-count 1 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-xxx],securityGroups=[sg-xxx],assignPublicIp=ENABLED}"
```

### Cost Estimate (AWS)

- **Fargate**: ~$0.04/vCPU-hour + $0.004/GB-hour
- **Estimated**: $15-40/month for 1 task running 24/7

---

## 🚀 Azure Container Instances

**Best for**: Quick deployment, Azure integration

### Prerequisites

```bash
# Install Azure CLI
brew install azure-cli  # macOS

# Login
az login
```

### Deployment Steps

#### 1. Create Resource Group

```bash
az group create \
  --name traffic-safety-rg \
  --location eastus
```

#### 2. Create Container Registry

```bash
# Create ACR
az acr create \
  --resource-group traffic-safety-rg \
  --name trafficsafetyacr \
  --sku Basic

# Login to ACR
az acr login --name trafficsafetyacr
```

#### 3. Build and Push

```bash
cd frontend

# Build and push
az acr build \
  --registry trafficsafetyacr \
  --image traffic-safety-dashboard:latest \
  .
```

#### 4. Deploy Container Instance

```bash
az container create \
  --resource-group traffic-safety-rg \
  --name traffic-safety-dashboard \
  --image trafficsafetyacr.azurecr.io/traffic-safety-dashboard:latest \
  --dns-name-label traffic-safety-app \
  --ports 8501 \
  --cpu 1 \
  --memory 1 \
  --registry-login-server trafficsafetyacr.azurecr.io \
  --registry-username $(az acr credential show --name trafficsafetyacr --query username -o tsv) \
  --registry-password $(az acr credential show --name trafficsafetyacr --query passwords[0].value -o tsv)

# Get URL
az container show \
  --resource-group traffic-safety-rg \
  --name traffic-safety-dashboard \
  --query "{FQDN:ipAddress.fqdn,ProvisioningState:provisioningState}" \
  --out table
```

### Cost Estimate (Azure)

- **Container Instances**: ~$0.0000125/vCPU-second + $0.0000014/GB-second
- **Estimated**: $30-50/month for 24/7 operation

---

## 🚀 Heroku

**Best for**: Simplest deployment, built-in CI/CD

### Prerequisites

```bash
# Install Heroku CLI
brew tap heroku/brew && brew install heroku  # macOS

# Login
heroku login
```

### Deployment Steps

#### 1. Create Heroku App

```bash
cd frontend

# Create app
heroku create traffic-safety-dashboard

# Set stack to container
heroku stack:set container
```

#### 2. Create `heroku.yml`

```yaml
build:
  docker:
    web: Dockerfile
run:
  web: streamlit run app/views/main.py --server.port=$PORT --server.address=0.0.0.0
```

#### 3. Deploy

```bash
# Deploy
git add .
git commit -m "Add Heroku deployment"
git push heroku main

# Open app
heroku open
```

#### Alternative: Using Container Registry

```bash
# Login to Heroku Container Registry
heroku container:login

# Build and push
heroku container:push web

# Release
heroku container:release web

# Open
heroku open
```

### Cost Estimate (Heroku)

- **Free tier**: Limited hours, sleeps after 30 min
- **Hobby**: $7/month (no sleep)
- **Standard**: $25/month (better performance)

---

## 🚀 Streamlit Community Cloud

**Best for**: Free hosting for public apps, zero config

### Deployment Steps

1. **Push code to GitHub**

   ```bash
   git add .
   git commit -m "Prepare for Streamlit Cloud"
   git push origin main
   ```

2. **Deploy on Streamlit Cloud**

   - Go to [share.streamlit.io](https://share.streamlit.io)
   - Click "New app"
   - Select repository: `Ulrixon/cs6604-trafficsafety`
   - Set branch: `frontend` (or your branch)
   - Set main file path: `frontend/app/views/main.py`
   - Click "Deploy"

3. **Configure Secrets** (if needed)
   - In Streamlit Cloud dashboard, go to app settings
   - Add secrets in TOML format:
   ```toml
   API_URL = "https://your-api-endpoint.com/..."
   ```

### Cost

- **Free**: Unlimited public apps
- **Streamlit for Teams**: $250/month (private apps, custom domains)

---

## 🚀 DigitalOcean App Platform

**Best for**: Affordable, simple deployment

### Deployment Steps

#### 1. Create App

```bash
# Install doctl
brew install doctl  # macOS

# Authenticate
doctl auth init
```

#### 2. Create `app.yaml`

```yaml
name: traffic-safety-dashboard
services:
  - name: web
    dockerfile_path: Dockerfile
    github:
      repo: Ulrixon/cs6604-trafficsafety
      branch: frontend
      deploy_on_push: true
    http_port: 8501
    instance_count: 1
    instance_size_slug: basic-xxs
    routes:
      - path: /
    health_check:
      http_path: /_stcore/health
    envs:
      - key: PORT
        value: "8501"
```

#### 3. Deploy

```bash
# Create app
doctl apps create --spec app.yaml

# Or via web UI:
# 1. Go to https://cloud.digitalocean.com/apps
# 2. Click "Create App"
# 3. Connect GitHub repo
# 4. Select Dockerfile deployment
# 5. Configure and deploy
```

### Cost Estimate (DigitalOcean)

- **Basic**: $5/month (512MB RAM, 1 vCPU)
- **Professional**: $12/month (1GB RAM, 1 vCPU)

---

## 🚀 Fly.io

**Best for**: Edge deployment, global distribution

### Deployment Steps

#### 1. Install Fly CLI

```bash
# Install
curl -L https://fly.io/install.sh | sh

# Login
fly auth login
```

#### 2. Launch App

```bash
cd frontend

# Initialize (creates fly.toml)
fly launch --name traffic-safety-dashboard --region sjc

# It will detect Dockerfile and configure automatically
```

#### 3. Configure `fly.toml`

```toml
app = "traffic-safety-dashboard"
primary_region = "sjc"

[build]
  dockerfile = "Dockerfile"

[env]
  PORT = "8501"

[http_service]
  internal_port = 8501
  force_https = true
  auto_stop_machines = true
  auto_start_machines = true
  min_machines_running = 0

[[vm]]
  cpu_kind = "shared"
  cpus = 1
  memory_mb = 512
```

#### 4. Deploy

```bash
# Deploy
fly deploy

# Open
fly open
```

### Cost Estimate (Fly.io)

- **Free tier**: 3 shared-cpu-1x VMs with 256MB RAM
- **Paid**: ~$5-10/month for better specs

---

## 🚀 Railway

**Best for**: Easiest deployment, great developer experience

### Deployment Steps

1. **Via Web UI**:

   - Go to [railway.app](https://railway.app)
   - Click "New Project"
   - Select "Deploy from GitHub repo"
   - Choose `Ulrixon/cs6604-trafficsafety`
   - Railway auto-detects Dockerfile
   - Click "Deploy"

2. **Via CLI**:

   ```bash
   # Install
   npm i -g @railway/cli

   # Login
   railway login

   # Initialize
   cd frontend
   railway init

   # Deploy
   railway up
   ```

### Cost Estimate (Railway)

- **Hobby**: $5/month (500 hours, $0.01/hour after)
- **Pro**: $20/month (more resources)

---

## 🔒 Security Considerations

### Environment Variables

Never commit secrets! Use environment variables:

```bash
# Google Cloud Run
gcloud run services update traffic-safety-dashboard \
  --set-env-vars API_KEY=your-secret-key

# AWS ECS
# Add to task definition environment section

# Heroku
heroku config:set API_KEY=your-secret-key

# Docker Compose
# Create .env file (add to .gitignore)
```

### HTTPS

All platforms provide HTTPS by default except Docker Compose (use nginx reverse proxy).

---

## 📊 Cost Comparison Summary

| Platform         | Free Tier   | Paid (Basic) | Best For        |
| ---------------- | ----------- | ------------ | --------------- |
| Streamlit Cloud  | ✅ Yes      | $250/mo      | Public demos    |
| Google Cloud Run | 2M requests | $5-20/mo     | Auto-scaling    |
| Fly.io           | 3 VMs       | $5-10/mo     | Edge/global     |
| Railway          | 500 hrs     | $5/mo        | Quick deploy    |
| DigitalOcean     | ❌ No       | $5/mo        | Affordable      |
| Heroku           | Limited     | $7/mo        | Simplicity      |
| AWS ECS          | ❌ No       | $15-40/mo    | AWS ecosystem   |
| Azure ACI        | ❌ No       | $30-50/mo    | Azure ecosystem |

---

## 🚀 Recommended Deployment

### For Development/Testing

**Streamlit Community Cloud** - Free, easy, perfect for demos

### For Production (Low Traffic)

**Fly.io** or **Railway** - Affordable, easy to scale

### For Production (High Traffic)

**Google Cloud Run** - Auto-scales, pay per use, enterprise-ready

### For Enterprise

**AWS ECS** or **Azure ACI** - Full control, compliance, integration

---

## 📝 Quick Deploy Commands

### Google Cloud Run (Fastest)

```bash
cd frontend
gcloud run deploy traffic-safety-dashboard --source . --region us-central1 --allow-unauthenticated
```

### Railway (Easiest)

```bash
cd frontend
railway init && railway up
```

### Fly.io (Best Value)

```bash
cd frontend
fly launch && fly deploy
```

---

**Need help?** Check platform-specific documentation or open an issue!
