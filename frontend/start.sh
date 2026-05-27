#!/usr/bin/env bash

set -e

echo "Traffic Safety Dashboard - Vite frontend"
echo "========================================"

if ! command -v npm >/dev/null 2>&1; then
  echo "npm is required. Install Node.js 18 or newer, then rerun this script."
  exit 1
fi

if [ ! -d "node_modules" ]; then
  echo "Installing frontend dependencies..."
  npm install
fi

echo "Starting Vite dev server at http://localhost:5173"
echo "Backend API defaults to http://localhost:8000/api/v1 unless VITE_API_URL is set."
npm run dev
