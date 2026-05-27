# Local Development

## Active Frontend

The active frontend is Vite React in `frontend/`.

```bash
cd frontend
npm install
npm run dev
```

Default URL: `http://localhost:5173`

## Backend

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Default API base: `http://localhost:8000/api/v1`

## Environment

Frontend environment variables use Vite's `VITE_` prefix and are compiled into the built static assets:

```bash
VITE_API_URL=http://localhost:8000/api/v1
```

Backend configuration remains Python environment based; see `backend/app/core/config.py` and backend deployment docs for required secrets.

## Containers

Frontend image:

```bash
cd frontend
docker build --build-arg VITE_API_URL=http://localhost:8000/api/v1 -t traffic-safety-dashboard .
docker run -p 8080:8080 traffic-safety-dashboard
```

Open `http://localhost:8080`.

## Legacy Streamlit

Legacy Streamlit code and docs are isolated under `frontend/legacy-streamlit/`. Run those only when you intentionally need to inspect or compare the old implementation.
