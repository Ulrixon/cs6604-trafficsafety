# Traffic Safety Dashboard

Vite React frontend for the VTTSI traffic safety application. It keeps the original backend API contract while combining operations, trends, validation, sensitivity analysis, database exploration, and SafetyChat into one dashboard.

## Run Locally

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`.

Set `VITE_API_URL` in `frontend/.env` if the backend is not running at `http://localhost:8000/api/v1`.

```bash
VITE_API_URL=http://localhost:8000/api/v1
```

## Build

```bash
npm run build
npm run preview -- --port 8080
```

## Cloud UI Tests

The Playwright cloud test set exercises the deployed Vite dashboard and the
deployed backend API it should be wired to.

```bash
cd frontend
npm run test:e2e:cloud
```

Optional overrides:

```bash
CLOUD_FRONTEND_URL=https://your-frontend.run.app \
CLOUD_BACKEND_API_URL=https://your-backend.run.app/api/v1 \
npm run test:e2e:cloud
```

Defaults:

- Frontend: `https://safety-index-frontend-180117512369.europe-west1.run.app`
- Backend API: `https://cs6604-trafficsafety-180117512369.europe-west1.run.app/api/v1`

## Dashboard Areas

- Operations: blended safety scores, risk map, filters, priority queue, and detail panel.
- Trends: single time-bin lookup and range trend analysis.
- Validation: crash correlation metrics, confusion matrix, scatter, time series, and weather impact.
- Sensitivity: RT-SI robustness checks under parameter perturbation.
- Database: raw table/schema explorer with quick charts.
- SafetyChat: always-available assistant docked beside the dashboard.

The previous Streamlit implementation is isolated under `frontend/legacy-streamlit/` for reference during migration.
