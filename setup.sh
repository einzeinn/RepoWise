#!/bin/bash
# REPOWISE Development Setup Script

echo "🏷️ REPOWISE Setup Started"

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    cp .env.example .env
    echo "✅ Created .env file from .env.example"
    echo "   ⚠️  Please update .env with your credentials"
fi

# Backend setup
echo ""
echo "📦 Setting up Backend..."
cd backend

# Create Python venv
if [ ! -d "venv" ]; then
    python -m venv venv
    echo "✅ Created Python virtual environment"
fi

# Activate venv
source venv/bin/activate 2>/dev/null || . venv/Scripts/activate

# Install dependencies
pip install -r requirements.txt
echo "✅ Installed backend dependencies"

cd ..

# Frontend setup
echo ""
echo "🎨 Setting up Frontend..."
cd frontend

# Install npm dependencies
npm install
echo "✅ Installed frontend dependencies"

cd ..

echo ""
echo "✅ Setup Complete!"
echo ""
echo "To start development:"
echo "  Backend:  cd backend && source venv/bin/activate && python app.py"
echo "  Frontend: cd frontend && npm run dev"
