#!/bin/bash
# Local Development Startup Script
# Starts both backend (FastAPI) and frontend (Streamlit) servers

set -e  # Exit on error

echo "=========================================="
echo "🚀 Starting Traffic Safety Application"
echo "=========================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Get the project root directory
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

echo -e "${BLUE}📁 Project root: $PROJECT_ROOT${NC}"
echo ""

# Function to cleanup on exit
cleanup() {
    echo ""
    echo -e "${YELLOW}🛑 Shutting down servers...${NC}"
    kill $BACKEND_PID $FRONTEND_PID 2>/dev/null
    exit 0
}

trap cleanup SIGINT SIGTERM

# ============================================
# BACKEND (FastAPI)
# ============================================
echo -e "${BLUE}🔧 Starting Backend (FastAPI)...${NC}"
echo "   Port: 8000"
echo "   API Docs: http://localhost:8000/docs"
echo ""

cd "$PROJECT_ROOT/backend"

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}⚠️  No virtual environment found. Creating one...${NC}"
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install/update dependencies
echo "   Installing backend dependencies..."
pip install -q -r requirements.txt

# Start backend server
echo -e "${GREEN}✅ Backend starting on http://localhost:8000${NC}"
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload > backend.log 2>&1 &
BACKEND_PID=$!

# Wait for backend to start
sleep 3

# Check if backend is running
if ! kill -0 $BACKEND_PID 2>/dev/null; then
    echo -e "${YELLOW}⚠️  Backend failed to start. Check backend.log for errors.${NC}"
    cat backend.log
    exit 1
fi

echo ""

# ============================================
# FRONTEND (Streamlit)
# ============================================
echo -e "${BLUE}🎨 Starting Frontend (Streamlit)...${NC}"
echo "   Port: 8501"
echo "   Dashboard: http://localhost:8501"
echo ""

cd "$PROJECT_ROOT/frontend"

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}⚠️  No virtual environment found. Creating one...${NC}"
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install/update dependencies
echo "   Installing frontend dependencies..."
pip install -q -r requirements.txt

# Start frontend server
echo -e "${GREEN}✅ Frontend starting on http://localhost:8501${NC}"
streamlit run app.py --server.port 8501 --server.address 0.0.0.0 > frontend.log 2>&1 &
FRONTEND_PID=$!

# Wait for frontend to start
sleep 3

# Check if frontend is running
if ! kill -0 $FRONTEND_PID 2>/dev/null; then
    echo -e "${YELLOW}⚠️  Frontend failed to start. Check frontend.log for errors.${NC}"
    cat frontend.log
    exit 1
fi

echo ""
echo "=========================================="
echo -e "${GREEN}✅ All servers are running!${NC}"
echo "=========================================="
echo ""
echo "📊 Backend API:     http://localhost:8000"
echo "📚 API Docs:        http://localhost:8000/docs"
echo "🎨 Frontend App:    http://localhost:8501"
echo ""
echo "📝 Logs:"
echo "   Backend:  tail -f backend/backend.log"
echo "   Frontend: tail -f frontend/frontend.log"
echo ""
echo "Press Ctrl+C to stop all servers"
echo "=========================================="
echo ""

# Keep script running
wait
