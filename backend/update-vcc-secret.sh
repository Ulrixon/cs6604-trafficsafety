#!/bin/bash
# Update VCC client secret with correct value

set -e

PROJECT_ID="symbolic-cinema-305010"

echo "=== Updating VCC Client Secret ==="
echo "Project: ${PROJECT_ID}"
echo ""

echo "Updating vcc_client_secret with correct value..."
echo -n "wHqQjvksKE6rYLYedkuIqewrFtEOpjHH" | gcloud secrets versions add vcc_client_secret \
  --data-file=- \
  --project=${PROJECT_ID}

echo ""
echo "✅ Secret updated successfully!"
echo ""
echo "Verify with:"
echo "  gcloud secrets versions access latest --secret=vcc_client_secret --project=${PROJECT_ID}"
