# Quickstart

## Backend

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Useful URLs:

- API health: `http://localhost:8000/health`
- API docs: `http://localhost:8000/docs`

## Frontend

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`.

The Vite frontend reads `VITE_API_URL` at build time. For local development, create `frontend/.env` when the backend is not at the default:

```bash
VITE_API_URL=http://localhost:8000/api/v1
```

## Docker Compose

```bash
docker compose up --build
```

The compose frontend is exposed at `http://localhost:5173` and proxies API calls to the backend exposed at `http://localhost:8001`.

## Legacy Streamlit

The previous Streamlit frontend was moved to `frontend/legacy-streamlit/`. It is no longer the active frontend or Cloud Run target.
