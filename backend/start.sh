#!/bin/bash
# Start Backend (FastAPI) Server

echo "🔧 Starting Backend Server..."
cd "$(dirname "$0")"

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Install dependencies
pip install -q -r requirements.txt

# Start server
echo "✅ Backend running on http://localhost:8000"
echo "📚 API Docs at http://localhost:8000/docs"
echo ""
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
