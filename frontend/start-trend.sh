#!/bin/bash

# Start Traffic Safety Trend Analysis Dashboard
# This script starts the Streamlit trend analysis page

echo "🚦 Starting Traffic Safety Trend Analysis Dashboard..."
echo ""

# Check if backend is running
echo "Checking backend API..."
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo "✅ Backend API is running"
else
    echo "❌ Backend API is not running!"
    echo ""
    echo "Please start the backend first:"
    echo "  cd /path/to/project"
    echo "  uvicorn backend.app.main:app --reload --port 8000"
    echo ""
    exit 1
fi

echo ""
echo "Starting Streamlit trend analysis page..."
echo "Access at: http://localhost:8501"
echo ""

# Run Streamlit
streamlit run app/views/trend_analysis.py
