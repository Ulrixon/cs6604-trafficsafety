#!/bin/bash

# Traffic Safety Dashboard - Quick Start Script
# This script sets up and runs the Streamlit application

set -e  # Exit on error

echo "🚦 Traffic Safety Dashboard - Setup & Launch"
echo "============================================="
echo ""

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install Python 3.9 or higher."
    exit 1
fi

echo "✅ Python found: $(python3 --version)"
echo ""

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv .venv
    echo "✅ Virtual environment created"
else
    echo "✅ Virtual environment already exists"
fi

echo ""
echo "🔧 Activating virtual environment..."
source .venv/bin/activate

echo ""
echo "📥 Installing dependencies..."
pip install --upgrade pip -q
pip install -r requirements.txt -q

echo "✅ Dependencies installed"
echo ""

echo "🚀 Starting Streamlit application..."
echo ""
echo "The dashboard will open in your browser at http://localhost:8501"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

streamlit run app/views/main.py
