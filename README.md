# Virginia Transportation Safety Index

Traffic safety dashboard and API for real-time intersection risk analysis. The current frontend is a Vite React dashboard backed by the FastAPI service in `backend/`.

## Current Layout

- `backend/` - FastAPI backend, data services, collectors, and Cloud Run deployment scripts.
- `frontend/` - active Vite React frontend and Cloud Run container config.
- `frontend/legacy-streamlit/` - archived Streamlit frontend kept separate for reference.
- `docs/` - project documentation grouped by topic.
- `data/`, `files/`, `construction/`, `memory-bank/` - datasets, report assets, planning notes, and project history.

## Run Locally

Backend:

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. The frontend defaults to `http://localhost:8000/api/v1`; override with `frontend/.env`:

```bash
VITE_API_URL=http://localhost:8000/api/v1
```

## Deploy

The repository has Cloud Build triggers for both backend and frontend on pushes to `main`.

Frontend trigger builds `frontend/Dockerfile`, produces the Vite static app, serves it with nginx on port `8080`, and updates Cloud Run service `safety-index-frontend`.

Manual frontend deploy:

```bash
cd frontend
./deploy-gcp.sh
```

## Docs

Start with [docs/README.md](docs/README.md) for the organized documentation index.
