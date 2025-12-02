#!/bin/bash
# Import local database schema and data to GCP Cloud SQL

set -e

export PATH="/c/Users/djjay/AppData/Local/Google/Cloud SDK/google-cloud-sdk/bin:$PATH"

PROJECT_ID="symbolic-cinema-305010"
INSTANCE="vtsi-postgres"
DATABASE="vtsi"
USER="jason"
PASSWORD='*9ZS^l(HGq].BA]6'

echo "=== Importing Local Database to GCP Cloud SQL ==="
echo "Instance: ${INSTANCE}"
echo "Database: ${DATABASE}"
echo ""

# Step 1: Import schema
echo "1. Importing schema..."
export PGPASSWORD="${PASSWORD}"
gcloud sql connect ${INSTANCE} --user=${USER} --database=${DATABASE} --project=${PROJECT_ID} --quiet < /tmp/local_safety_schema.sql 2>&1 | tail -20

echo ""
echo "2. Importing data..."
gcloud sql connect ${INSTANCE} --user=${USER} --database=${DATABASE} --project=${PROJECT_ID} --quiet < /tmp/local_safety_data.sql 2>&1 | tail -20

echo ""
echo "✅ Database import complete!"
