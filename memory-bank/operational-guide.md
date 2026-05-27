# Operational Guide - Traffic Safety Index System

**Last Updated**: 2026-05-27  
**Status**: Cloud Run production active | Vite frontend active | FastAPI backend active | Cloud SQL private IP only

---

## Production Architecture

```
Frontend user
    ↓
Cloud Run: safety-index-frontend
    - Vite React static app served by nginx
    - URL: https://safety-index-frontend-180117512369.europe-west1.run.app
    ↓
Cloud Run: cs6604-trafficsafety
    - FastAPI backend
    - URL: https://cs6604-trafficsafety-180117512369.europe-west1.run.app
    - API base: /api/v1
    - Direct VPC egress for private Cloud SQL access
    ↓
Cloud SQL: vtsi-postgres
    - PostgreSQL 17.9
    - Private IP: 10.75.222.3
    - Public IP: disabled
```

Legacy Streamlit is retained only at `frontend/legacy-streamlit/` for reference.

---

## Current Cloud Resources

| Resource | Name | Notes |
|---|---|---|
| GCP project | `symbolic-cinema-305010` | Project number `180117512369` |
| Region | `europe-west1` | Belgium |
| Backend Cloud Run | `cs6604-trafficsafety` | Latest verified revision after cache/private-IP work: `cs6604-trafficsafety-00159-pfk` |
| Frontend Cloud Run | `safety-index-frontend` | Active Vite dashboard |
| Collector Cloud Run | `cs6604-trafficsafety-collector` | Cost-control target; do not re-enable unless needed |
| Cloud SQL | `vtsi-postgres` | Active PostgreSQL database |
| Deleted Cloud SQL | `vttsi` | Duplicate instance removed |
| GCS bucket | `gs://cs6604-trafficsafety-parquet` | Historical/raw data bucket |

---

## Cloud SQL Operating Rules

- Use private IP `10.75.222.3` from Cloud Run.
- Public IP is disabled to avoid reservation billing.
- Backend must keep VPC egress configured for private ranges.
- Do not set `INSTANCE_CONNECTION_NAME` for socket mode unless intentionally reverting the connection strategy.
- Backend should use literal DB user env binding and secret-backed DB password. Do not expose password values in logs or docs.

Useful checks:

```bash
gcloud sql instances describe vtsi-postgres \
  --project symbolic-cinema-305010
```

```bash
gcloud run services describe cs6604-trafficsafety \
  --region europe-west1 \
  --project symbolic-cinema-305010
```

---

## Deployment Commands

### Backend

```bash
cd backend
./deploy-gcp.sh
```

Check backend health:

```bash
curl -s https://cs6604-trafficsafety-180117512369.europe-west1.run.app/health
```

View backend logs:

```bash
gcloud run services logs read cs6604-trafficsafety \
  --region=europe-west1 \
  --project=symbolic-cinema-305010 \
  --limit=100
```

### Frontend

```bash
cd frontend
npm run build
./deploy-gcp.sh
```

The frontend build should receive:

```bash
VITE_API_URL=https://cs6604-trafficsafety-180117512369.europe-west1.run.app/api/v1
```

View frontend logs:

```bash
gcloud run services logs read safety-index-frontend \
  --region=europe-west1 \
  --project=symbolic-cinema-305010 \
  --limit=100
```

---

## Test Commands

### Local Backend Regression

```bash
python -m pytest tests/backend -q
```

Latest verified: `48 passed`.

### Cloud Backend API Smoke Tests

```bash
RUN_CLOUD_TESTS=1 python -m pytest tests/cloud -q
```

Latest verified against Cloud Run: `7 passed`.

Override backend target:

```bash
RUN_CLOUD_TESTS=1 \
CLOUD_BACKEND_URL=https://your-backend.run.app \
python -m pytest tests/cloud -q
```

### Cloud Frontend UI Tests

```bash
cd frontend
npm run test:e2e:cloud
```

Latest verified against Cloud Run: `4 passed`.

If Playwright browser binaries are missing:

```bash
cd frontend
npx playwright install chromium
```

Override targets:

```bash
CLOUD_FRONTEND_URL=https://your-frontend.run.app \
CLOUD_BACKEND_API_URL=https://your-backend.run.app/api/v1 \
npm run test:e2e:cloud
```

### Frontend Build

```bash
cd frontend
npm run build
```

Latest verified: build passed.

---

## New Cloud Test Layout

| Test Set | Path | Purpose |
|---|---|---|
| Backend cloud tests | `tests/cloud/test_backend_cloud_api.py` | Cloud Run health, OpenAPI, safety index data, intersection catalog, range endpoint, chat tools |
| Cloud test docs | `tests/cloud/README.md` | How to run and override endpoint URLs |
| Frontend cloud E2E | `frontend/e2e/cloud-dashboard.spec.ts` | Vite dashboard loads live backend, map tiles/markers render, panels navigate |
| Playwright cloud config | `frontend/playwright.cloud.config.ts` | Defaults to production frontend and backend API |

---

## Caching

- Cache implementation: `backend/app/core/redis_cache.py`
- Current behavior: per-instance cache is acceptable.
- External Redis is optional. If unavailable, the app falls back to memory cache.
- Cache status appears in `/health`.
- Cached endpoint areas include safety index, history, database explorer, transparency, chat tool metadata, and VCC/status-style reads.

---

## SQL Safety Notes

- Local app DB service paths use SQLAlchemy statements/models.
- Core metadata: `backend/app/models/database.py`
- Main service refactor: `backend/app/services/db_service.py`
- Database explorer external table access validates identifiers and uses `psycopg2.sql.Identifier`.
- Trino query builders escape user-controlled string literals.
- SafetyChat ad-hoc SQL tool is read-only and rejects comments, multi-statements, and write/DDL keywords.

Run SQL safety tests:

```bash
python -m pytest tests/backend/test_sql_safety.py -q
```

---

## Cost-Control Notes

- Keep `vtsi-postgres` public IP disabled unless temporarily needed.
- Duplicate Cloud SQL instance `vttsi` has been deleted.
- Collector service can consume money without useful work; keep it disabled unless there is a specific data collection task.
- Private IP itself does not have the same public IP reservation charge, but VPC/network resources and Cloud SQL instance runtime still have normal costs.

---

## Common Checks

### Backend API

```bash
curl -s https://cs6604-trafficsafety-180117512369.europe-west1.run.app/api/v1/safety/index/
```

### Intersection List

```bash
curl -s https://cs6604-trafficsafety-180117512369.europe-west1.run.app/api/v1/safety/index/intersections/list
```

### Chat Tools

```bash
curl -s https://cs6604-trafficsafety-180117512369.europe-west1.run.app/api/v1/chat/tools
```

### Frontend

Open:

```text
https://safety-index-frontend-180117512369.europe-west1.run.app
```

---

## Known Warnings

- `pytest-asyncio` warns about unset default fixture loop scope.
- Pydantic V2 warns about deprecated `Field(..., env=...)` and `Field(..., example=...)` usage.
- `npm install` reports 2 moderate audit findings; do not run `npm audit fix --force` without reviewing breaking dependency changes.

