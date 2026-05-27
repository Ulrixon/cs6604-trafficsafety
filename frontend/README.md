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

## Dashboard Areas

- Operations: blended safety scores, risk map, filters, priority queue, and detail panel.
- Trends: single time-bin lookup and range trend analysis.
- Validation: crash correlation metrics, confusion matrix, scatter, time series, and weather impact.
- Sensitivity: RT-SI robustness checks under parameter perturbation.
- Database: raw table/schema explorer with quick charts.
- SafetyChat: always-available assistant docked beside the dashboard.

The previous Streamlit implementation remains in `frontend/app` and `frontend/pages` for reference during migration.
