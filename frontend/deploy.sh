#!/bin/bash

# Quick deployment script for Traffic Safety Dashboard
# Supports multiple cloud platforms

set -e

echo "🚀 Traffic Safety Dashboard - Cloud Deployment"
echo "==============================================="
echo ""

# Function to display menu
show_menu() {
    echo "Select deployment platform:"
    echo "1) Google Cloud Run (GCP)"
    echo "2) AWS ECS"
    echo "3) Azure Container Instances"
    echo "4) Heroku"
    echo "5) Fly.io"
    echo "6) Railway"
    echo "7) Docker Hub (push image only)"
    echo "8) Local Docker Test"
    echo "9) Exit"
    echo ""
}

# Google Cloud Run deployment
deploy_cloudrun() {
    echo "🚀 Deploying to Google Cloud Run..."
    
    read -p "Enter GCP Project ID: " PROJECT_ID
    gcloud config set project "$PROJECT_ID"
    
    echo ""
    echo "Building and deploying..."
    gcloud run deploy traffic-safety-dashboard \
        --source . \
        --region us-central1 \
        --platform managed \
        --allow-unauthenticated \
        --port 8501 \
        --memory 1Gi \
        --cpu 1 \
        --max-instances 10
    
    echo ""
    echo "✅ Deployment complete!"
    gcloud run services describe traffic-safety-dashboard \
        --region us-central1 \
        --format='value(status.url)'
}

# Heroku deployment
deploy_heroku() {
    echo "🚀 Deploying to Heroku..."
    
    # Check if app exists
    read -p "Enter Heroku app name (or press Enter for auto-generated): " APP_NAME
    
    if [ -z "$APP_NAME" ]; then
        heroku create
    else
        heroku create "$APP_NAME" || echo "App exists, using existing..."
    fi
    
    heroku stack:set container
    
    echo ""
    echo "Deploying..."
    git push heroku HEAD:main || git push heroku main
    
    echo ""
    echo "✅ Deployment complete!"
    heroku open
}

# Fly.io deployment
deploy_flyio() {
    echo "🚀 Deploying to Fly.io..."
    
    if [ ! -f "fly.toml" ]; then
        echo "Initializing Fly.io app..."
        fly launch --name traffic-safety-dashboard --region sjc --now
    else
        echo "Deploying existing app..."
        fly deploy
    fi
    
    echo ""
    echo "✅ Deployment complete!"
    fly open
}

# Railway deployment
deploy_railway() {
    echo "🚀 Deploying to Railway..."
    
    if [ ! -d ".railway" ]; then
        railway init
    fi
    
    railway up
    
    echo ""
    echo "✅ Deployment complete!"
    echo "Check your Railway dashboard for the URL"
}

# Docker Hub push
push_dockerhub() {
    echo "🐳 Pushing to Docker Hub..."
    
    read -p "Enter Docker Hub username: " DOCKER_USER
    
    echo ""
    echo "Building image..."
    docker build -t traffic-safety-dashboard .
    
    echo ""
    echo "Tagging image..."
    docker tag traffic-safety-dashboard:latest \
        "$DOCKER_USER/traffic-safety-dashboard:latest"
    
    echo ""
    echo "Logging in to Docker Hub..."
    docker login
    
    echo ""
    echo "Pushing image..."
    docker push "$DOCKER_USER/traffic-safety-dashboard:latest"
    
    echo ""
    echo "✅ Image pushed to Docker Hub!"
    echo "Pull with: docker pull $DOCKER_USER/traffic-safety-dashboard:latest"
}

# Local Docker test
test_docker() {
    echo "🐳 Testing Docker locally..."
    
    echo ""
    echo "Building image..."
    docker build -t traffic-safety-dashboard .
    
    echo ""
    echo "Starting container..."
    docker run -p 8501:8501 \
        --name traffic-safety-test \
        traffic-safety-dashboard
}

# Main menu loop
while true; do
    show_menu
    read -p "Enter your choice [1-9]: " choice
    
    case $choice in
        1)
            deploy_cloudrun
            break
            ;;
        2)
            echo "AWS ECS requires more setup. Please see DEPLOYMENT.md for detailed instructions."
            echo ""
            ;;
        3)
            echo "Azure ACI requires more setup. Please see DEPLOYMENT.md for detailed instructions."
            echo ""
            ;;
        4)
            deploy_heroku
            break
            ;;
        5)
            deploy_flyio
            break
            ;;
        6)
            deploy_railway
            break
            ;;
        7)
            push_dockerhub
            break
            ;;
        8)
            test_docker
            break
            ;;
        9)
            echo "Exiting..."
            exit 0
            ;;
        *)
            echo "Invalid option. Please try again."
            echo ""
            ;;
    esac
done
