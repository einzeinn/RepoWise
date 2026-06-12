@echo off
REM REPOWISE Development Setup Script for Windows

echo 🏷️ REPOWISE Setup Started

REM Create .env file if it doesn't exist
if not exist .env (
    copy .env.example .env
    echo ✅ Created .env file from .env.example
    echo    ⚠️  Please update .env with your credentials
)

REM Backend setup
echo.
echo 📦 Setting up Backend...
cd backend

REM Create Python venv
if not exist venv (
    python -m venv venv
    echo ✅ Created Python virtual environment
)

REM Activate venv
call venv\Scripts\activate.bat

REM Install dependencies
pip install -r requirements.txt
echo ✅ Installed backend dependencies

cd ..

REM Frontend setup
echo.
echo 🎨 Setting up Frontend...
cd frontend

REM Install npm dependencies
call npm install
echo ✅ Installed frontend dependencies

cd ..

echo.
echo ✅ Setup Complete!
echo.
echo To start development:
echo   Backend:  cd backend ^&^& venv\Scripts\activate ^&^& python app.py
echo   Frontend: cd frontend ^&^& npm run dev
