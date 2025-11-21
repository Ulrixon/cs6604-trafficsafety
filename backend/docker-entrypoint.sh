#!/bin/bash
set -e

echo "Starting Traffic Safety Backend API..."

# Set default port (Cloud Run uses PORT env var)
PORT=${PORT:-8080}

# Database configuration from environment or secrets
# If running on Cloud Run, these will be set as environment variables
# from Secret Manager bindings
export VTTI_DB_HOST=${VTTI_DB_HOST:-"34.140.49.230"}
export VTTI_DB_PORT=${VTTI_DB_PORT:-"5432"}
export VTTI_DB_NAME=${VTTI_DB_NAME:-"vtti_db"}
export VTTI_DB_USER=${VTTI_DB_USER:-"vtti_user"}
export VTTI_DB_PASSWORD=${VTTI_DB_PASSWORD:-""}

# MCDM Configuration
export MCDM_BIN_MINUTES=${MCDM_BIN_MINUTES:-"15"}
export MCDM_LOOKBACK_HOURS=${MCDM_LOOKBACK_HOURS:-"24"}

# VCC Configuration (if needed)
export VCC_USERNAME=${VCC_USERNAME:-""}
export VCC_PASSWORD=${VCC_PASSWORD:-""}
export VCC_API_URL=${VCC_API_URL:-""}

echo "Configuration:"
echo "  Database Host: $VTTI_DB_HOST"
echo "  Database Port: $VTTI_DB_PORT"
echo "  Database Name: $VTTI_DB_NAME"
echo "  Database User: $VTTI_DB_USER"
echo "  MCDM Bin Minutes: $MCDM_BIN_MINUTES"
echo "  MCDM Lookback Hours: $MCDM_LOOKBACK_HOURS"
echo "  Listening on port: $PORT"

# Start the application
exec uvicorn app.main:app --host 0.0.0.0 --port $PORT
