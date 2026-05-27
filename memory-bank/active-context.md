# Active Context

**Last Updated**: 2026-05-27  
**Status**: Production Cloud Run system active | Vite frontend live | FastAPI backend live | Cloud SQL private IP only | per-instance cache enabled

---

## Current System State

### Cloud Run Services

| Service | URL | Current Role | State Notes |
|---|---|---|---|
| Backend API | `https://cs6604-trafficsafety-180117512369.europe-west1.run.app` | FastAPI API for safety index, analytics, database explorer, SafetyChat, VCC status | Active. Latest verified backend revision after cache/private-IP work: `cs6604-trafficsafety-00159-pfk`. |
| Frontend Dashboard | `https://safety-index-frontend-180117512369.europe-west1.run.app` | Active Vite React dashboard | Active. Replaces Streamlit for production UI. |
| Data Collector | `cs6604-trafficsafety-collector` | Historical collector service | Cost-control target. Do not assume it should run continuously; verify before re-enabling. |

### Cloud SQL

- Active instance: `vtsi-postgres`
- Region: `europe-west1`
- Version: PostgreSQL 17.9
- Machine: `db-f1-micro`
- Database: `vtsi`
- Backend connection mode: private IP `10.75.222.3`
- Public IP: disabled to avoid public IP reservation billing.
- Duplicate instance `vttsi`: deleted.
- Backend Cloud Run uses Direct VPC egress for private ranges and connects with `VTTI_DB_HOST=10.75.222.3`.
- Do not reintroduce Cloud SQL public IP unless there is a clear, temporary operational need.

### Caching

- Backend API caching is per Cloud Run instance.
- Redis config can be present, but current agreed behavior is no external shared Redis requirement.
- If Redis is unavailable, cache falls back to in-process memory via `backend/app/core/redis_cache.py`.
- Cache-enabled endpoint areas include safety index, history, chat/tools-related reads, database explorer, transparency, and VCC/status-style reads.

### Frontend

- Active frontend is Vite React under `frontend/`.
- Legacy Streamlit is archived under `frontend/legacy-streamlit/` and should not be treated as production frontend.
- Production frontend defaults to backend API base `https://cs6604-trafficsafety-180117512369.europe-west1.run.app/api/v1` at build/deploy time.
- Network risk map uses OpenStreetMap raster tiles and intersection markers in `frontend/src/App.tsx`.

### Backend SQL Safety

- Local app database API paths have been refactored away from raw SQL strings toward SQLAlchemy models/statements.
- SQLAlchemy table metadata lives in `backend/app/models/database.py`.
- `backend/app/services/db_service.py` no longer depends on `execute_raw_sql`.
- `backend/app/db/connection.py` no longer exposes `execute_raw_sql`; health checks use SQLAlchemy `select(...)`.
- External VTTI/Trino paths cannot all become SQLAlchemy ORM because they use psycopg2 or Trino clients. They are hardened with parameter binding, identifier composition, and Trino string literal escaping where applicable.
- SafetyChat `run_sql_query` remains an ad-hoc read-only SELECT tool, but now rejects comments, multiple statements, and write/DDL keywords.

---

## Recent Completed Work

### 1. Vite Frontend Migration and UI Consolidation

- Replaced the production dashboard with Vite React.
- Kept the original functional areas:
  - Operations overview
  - Network risk map
  - Trends
  - Analytics and validation
  - Sensitivity analysis
  - Database explorer
  - SafetyChat
- Streamlit is separated into `frontend/legacy-streamlit/`.
- Build verified with `npm run build`.

### 2. Frontend Map and UI Verification

- Network risk map now renders OpenStreetMap road/city tile background.
- Added Playwright cloud UI tests under `frontend/e2e/`.
- Playwright config: `frontend/playwright.cloud.config.ts`.
- Test command:

```bash
cd frontend
npm run test:e2e:cloud
```

Latest verified result: `4 passed`.

### 3. Backend Cloud API Test Set

- Added Cloud Run backend smoke tests under `tests/cloud/`.
- Tests are skipped by default and enabled with `RUN_CLOUD_TESTS=1`.
- Test command:

```bash
RUN_CLOUD_TESTS=1 python -m pytest tests/cloud -q
```

Latest verified result against deployed backend: `7 passed`.

### 4. Validation Logic

- Frontend validation panel no longer collapses to placeholder zeros when backend summary metrics are empty.
- Frontend derives validation metrics from returned scatter/time-series rows when backend summary metrics are missing or unusable.
- Backend validation endpoints still provide primary analytics where available.

### 5. SQL Injection Hardening

- Refactored local backend DB service paths to SQLAlchemy statements.
- Hardened database explorer table/column access with allowlists plus `psycopg2.sql.Identifier`.
- Parameterized VTTI MCDM timestamp/bin queries.
- Added Trino literal escaping for user-controlled intersection filters.
- Added regression tests in `tests/backend/test_sql_safety.py`.
- Latest local backend verification: `python -m pytest tests/backend -q` passed with `48 passed`.

### 6. Cloud Cost Controls

- Duplicate Cloud SQL instance `vttsi` removed.
- Public IP disabled on `vtsi-postgres`.
- Backend wired to private IP through VPC egress.
- Collector service should remain off unless explicitly needed because it can consume Cloud Run cost without useful work.

---

## Commands to Verify Current State

### Backend Health

```bash
curl -s https://cs6604-trafficsafety-180117512369.europe-west1.run.app/health
```

### Backend API Smoke Tests

```bash
RUN_CLOUD_TESTS=1 python -m pytest tests/cloud -q
```

### Frontend Cloud UI Tests

```bash
cd frontend
npm run test:e2e:cloud
```

### Local Backend Tests

```bash
python -m pytest tests/backend -q
```

### Frontend Build

```bash
cd frontend
npm run build
```

---

## Important Defaults and URLs

- GCP project: `symbolic-cinema-305010`
- Region: `europe-west1`
- Backend URL: `https://cs6604-trafficsafety-180117512369.europe-west1.run.app`
- Backend API base: `https://cs6604-trafficsafety-180117512369.europe-west1.run.app/api/v1`
- Frontend URL: `https://safety-index-frontend-180117512369.europe-west1.run.app`
- Cloud SQL private host: `10.75.222.3`

---

## Known Constraints

- Cloud endpoint tests require network access and may be affected by Cloud Run cold starts.
- Playwright browser tests require Chromium installed via:

```bash
cd frontend
npx playwright install chromium
```

- `npm install` currently reports 2 moderate audit findings. Do not run `npm audit fix --force` without reviewing breaking dependency changes.
- Some external queries remain raw SQL strings because the Trino and VTTI clients are not SQLAlchemy ORM clients. Treat those as hardened external query paths, not ORM-managed local DB paths.
- Pydantic warning noise remains in tests due to deprecated `Field(..., env/example=...)` usage.

---

## Next Best Actions

1. Keep the production frontend on Vite and avoid adding new Streamlit production features.
2. If changing backend endpoints, update both local unit tests and cloud smoke tests.
3. If changing map rendering, run `npm run test:e2e:cloud` and inspect map tile/marker assertions.
4. If changing database connectivity, preserve private-IP Cloud SQL access and avoid restoring public IP.
5. Consider a follow-up cleanup for Pydantic V2 warnings and npm audit findings.

