#!/bin/bash

# Traffic Safety Dashboard - UV-Powered Quick Start
# This script uses UV (ultra-fast Python package manager) to set up and run the app

set -e  # Exit on error

echo "🚦 Traffic Safety Dashboard - UV Quick Start"
echo "=============================================="
echo ""

# Check if UV is installed
if ! command -v uv &> /dev/null; then
    echo "❌ UV is not installed."
    echo ""
    echo "Install UV with one of these methods:"
    echo "  1. curl -LsSf https://astral.sh/uv/install.sh | sh"
    echo "  2. brew install uv"
    echo "  3. pip install uv"
    echo ""
    exit 1
fi

echo "✅ UV found: $(uv --version)"
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
    echo "📦 Creating virtual environment with UV..."
    uv venv
    echo "✅ Virtual environment created"
else
    echo "✅ Virtual environment already exists"
fi

echo ""
echo "🔧 Activating virtual environment..."
source .venv/bin/activate

echo ""
echo "📥 Installing dependencies with UV (this is FAST ⚡)..."
uv pip install -r requirements.txt

echo "✅ Dependencies installed"
echo ""

echo "🚀 Starting Streamlit application..."
echo ""
echo "The dashboard will open in your browser at http://localhost:8501"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

streamlit run app/views/main.py
