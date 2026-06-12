#!/bin/bash
# Quick start script for development

echo "🚀 Starting REPOWISE Development Environment..."

# Start backend in background
echo "📦 Starting Backend on http://localhost:8000..."
cd backend
source venv/bin/activate 2>/dev/null || . venv/Scripts/activate
python app.py &
BACKEND_PID=$!
cd ..

# Wait for backend to start
sleep 2

# Start frontend
echo "🎨 Starting Frontend on http://localhost:3000..."
cd frontend
npm run dev
