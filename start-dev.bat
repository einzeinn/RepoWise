@echo off
REM Quick start script for development on Windows

echo 🚀 Starting REPOWISE Development Environment...

REM Start backend in new window
echo 📦 Starting Backend on http://localhost:8000...
start "REPOWISE Backend" cmd /k "cd backend && venv\Scripts\activate && python app.py"

REM Wait a bit for backend to start
timeout /t 3 /nobreak

REM Start frontend
echo 🎨 Starting Frontend on http://localhost:3000...
cd frontend
call npm run dev
