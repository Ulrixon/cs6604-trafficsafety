# Testing

## Frontend

```bash
cd frontend
npm ci
npm run build
```

The current CI frontend gate uses this build check.

## Backend

```bash
pip install -r backend/requirements.txt
pytest tests/backend -v --tb=short
```

## Plugin Tests

```bash
pip install -r backend/requirements.txt
pytest tests/plugins -v --tb=short
```

## Legacy Streamlit Tests

Older Streamlit-oriented tests remain in `tests/frontend/` for historical reference. They are not part of the active Vite CI gate.
