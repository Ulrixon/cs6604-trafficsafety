#!/bin/bash
# Create VCC API credential secrets in Secret Manager

set -e

PROJECT_ID="symbolic-cinema-305010"

echo "=== Creating VCC API Secrets in Secret Manager ==="
echo "Project: ${PROJECT_ID}"
echo ""

# Create vcc_client_id secret
echo "1. Creating vcc_client_id secret..."
echo -n "course-cs6604-student-djjay" | gcloud secrets create vcc_client_id \
  --data-file=- \
  --replication-policy="automatic" \
  --project=${PROJECT_ID} 2>/dev/null && echo "✓ vcc_client_id created" || echo "⚠ vcc_client_id already exists (skipping)"

# Create vcc_client_secret secret
echo "2. Creating vcc_client_secret secret..."
echo -n "wHqQjvksKE6rYLYedkuIqewrFtEOpjHH" | gcloud secrets create vcc_client_secret \
  --data-file=- \
  --replication-policy="automatic" \
  --project=${PROJECT_ID} 2>/dev/null && echo "✓ vcc_client_secret created" || echo "⚠ vcc_client_secret already exists (skipping)"

echo ""
echo "✅ VCC secrets setup complete!"
echo ""
echo "Verify with:"
echo "  gcloud secrets list --project=${PROJECT_ID}"
