#!/bin/bash
set -e

echo "Starting Traffic Safety Backend API..."

# Set default port (Cloud Run uses PORT env var)
PORT=${PORT:-8080}

# Database configuration from environment or secrets
# If running on Cloud Run, these will be set as environment variables
# from Secret Manager bindings

# Cloud SQL Instance Connection Name (for Cloud Run Unix socket connection)
# If set, the app will connect via /cloudsql/INSTANCE_CONNECTION_NAME socket
# If not set, it will use TCP connection with VTTI_DB_HOST and VTTI_DB_PORT
export VTTI_DB_INSTANCE_CONNECTION_NAME=${VTTI_DB_INSTANCE_CONNECTION_NAME:-""}

# Database credentials
export VTTI_DB_NAME=${VTTI_DB_NAME:-"vtsi"}
export VTTI_DB_USER=${VTTI_DB_USER:-"postgres"}
export VTTI_DB_PASSWORD=${VTTI_DB_PASSWORD:-""}

# TCP connection settings (used only if VTTI_DB_INSTANCE_CONNECTION_NAME is not set)
export VTTI_DB_HOST=${VTTI_DB_HOST:-"34.140.49.230"}
export VTTI_DB_PORT=${VTTI_DB_PORT:-"5432"}

# MCDM Configuration
export MCDM_BIN_MINUTES=${MCDM_BIN_MINUTES:-"15"}
export MCDM_LOOKBACK_HOURS=${MCDM_LOOKBACK_HOURS:-"24"}

# VCC Configuration (if needed)
export VCC_USERNAME=${VCC_USERNAME:-""}
export VCC_PASSWORD=${VCC_PASSWORD:-""}
export VCC_API_URL=${VCC_API_URL:-""}

echo "Configuration:"
if [ -n "$VTTI_DB_INSTANCE_CONNECTION_NAME" ]; then
    echo "  Database Connection: Cloud SQL Unix Socket"
    echo "  Instance: $VTTI_DB_INSTANCE_CONNECTION_NAME"
else
    echo "  Database Connection: TCP"
    echo "  Database Host: $VTTI_DB_HOST"
    echo "  Database Port: $VTTI_DB_PORT"
fi
echo "  Database Name: $VTTI_DB_NAME"
echo "  Database User: $VTTI_DB_USER"
echo "  MCDM Bin Minutes: $MCDM_BIN_MINUTES"
echo "  MCDM Lookback Hours: $MCDM_LOOKBACK_HOURS"
echo "  Listening on port: $PORT"

# Start the application
exec uvicorn app.main:app --host 0.0.0.0 --port $PORT
