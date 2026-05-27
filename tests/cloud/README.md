# Cloud Endpoint Tests

These tests hit the deployed Cloud Run services directly. They are skipped by
default so the normal local suite does not depend on network access or Cloud Run
cold starts.

Run backend cloud API smoke tests:

```bash
RUN_CLOUD_TESTS=1 python -m pytest tests/cloud -q
```

Override the deployed backend:

```bash
RUN_CLOUD_TESTS=1 \
CLOUD_BACKEND_URL=https://your-backend.run.app \
python -m pytest tests/cloud -q
```

Defaults:

- Backend: `https://cs6604-trafficsafety-180117512369.europe-west1.run.app`
- API base: `${CLOUD_BACKEND_URL}/api/v1`
