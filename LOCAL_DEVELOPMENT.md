# Local Development Quick Start Guide

## Prerequisites

- Python 3.8+
- pip
- Access to VTTI PostgreSQL database (credentials in .env files)

## Option 1: Start Both Servers (Recommended)

```bash
# From project root
chmod +x start_local.sh
./start_local.sh
```

This will start:

- **Backend**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **Frontend**: http://localhost:8501

Press `Ctrl+C` to stop both servers.

---

## Option 2: Start Servers Separately

### Terminal 1 - Backend (FastAPI)

```bash
cd backend

# Create virtual environment (first time only)
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Start backend
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

**Backend will be available at:**

- API: http://localhost:8000
- Interactive API Docs: http://localhost:8000/docs
- Alternative Docs: http://localhost:8000/redoc

### Terminal 2 - Frontend (Streamlit)

```bash
cd frontend

# Create virtual environment (first time only)
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Start frontend
streamlit run app.py --server.port 8501 --server.address 0.0.0.0
```

**Frontend will be available at:**

- Dashboard: http://localhost:8501

---

## Option 3: Using Existing Scripts

### Backend

```bash
cd backend
chmod +x start.sh
./start.sh
```

### Frontend

```bash
cd frontend
chmod +x start.sh
./start.sh
```

---

## Quick Commands Summary

| Action            | Command                                                          |
| ----------------- | ---------------------------------------------------------------- |
| **Start Both**    | `./start_local.sh` (from root)                                   |
| **Backend Only**  | `cd backend && uvicorn app.main:app --reload`                    |
| **Frontend Only** | `cd frontend && streamlit run app.py`                            |
| **Stop Servers**  | `Ctrl+C` in terminal                                             |
| **View Logs**     | `tail -f backend/backend.log` or `tail -f frontend/frontend.log` |

---

## Environment Variables

### Backend (.env file in backend/ directory)

```bash
# Database
DATABASE_URL=postgresql://user:password@host:port/database

# Optional
LOG_LEVEL=INFO
API_V1_PREFIX=/api/v1
```

### Frontend (.env file in frontend/ directory)

```bash
# API Configuration
API_BASE_URL=http://localhost:8000/api/v1
```

---

## Troubleshooting

### Port Already in Use

If you get "Address already in use" error:

```bash
# Find and kill process on port 8000 (backend)
lsof -ti:8000 | xargs kill -9

# Find and kill process on port 8501 (frontend)
lsof -ti:8501 | xargs kill -9
```

### Database Connection Issues

1. Check your `.env` file has correct database credentials
2. Ensure you have VPN access to VTTI database
3. Test connection:
   ```bash
   cd backend
   python -c "from app.services.db_client import VTTIPostgresClient; VTTIPostgresClient()"
   ```

### Module Not Found Errors

```bash
# Reinstall dependencies
cd backend && pip install -r requirements.txt
cd frontend && pip install -r requirements.txt
```

### Frontend Can't Connect to Backend

1. Ensure backend is running on port 8000
2. Check `frontend/.env` has `API_BASE_URL=http://localhost:8000/api/v1`
3. Test API: `curl http://localhost:8000/api/v1/safety/index/`

---

## Development Tips

### Auto-reload

Both servers support auto-reload:

- **Backend**: Changes to Python files automatically reload (uvicorn --reload)
- **Frontend**: Streamlit detects changes and prompts to rerun

### API Testing

Use the interactive API docs:

1. Go to http://localhost:8000/docs
2. Expand any endpoint
3. Click "Try it out"
4. Fill in parameters
5. Click "Execute"

### Debugging

**Backend logs:**

```bash
tail -f backend/backend.log
```

**Frontend logs:**

```bash
tail -f frontend/frontend.log
```

**Or run in foreground to see logs directly in terminal**

---

## Next Steps

1. **Test Backend**: Visit http://localhost:8000/docs
2. **Test Frontend**: Visit http://localhost:8501
3. **Try API**: Get intersections list at http://localhost:8000/api/v1/safety/index/
4. **Explore Dashboard**: Select an intersection and adjust the alpha slider

---

**Need help?** Check the logs or API documentation at http://localhost:8000/docs
