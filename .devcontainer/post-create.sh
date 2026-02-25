#!/bin/bash
# =============================================================================
# Certinator AI — Dev Container Post-Create Setup
# =============================================================================
# This script runs automatically after the dev container is created.

set -e

echo "========================================"
echo "Setting up Certinator AI Development Environment"
echo "========================================"

# -----------------------------------------------------------------------------
# Backend Setup
# -----------------------------------------------------------------------------
echo ""
echo "📦 Setting up Python backend..."

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Upgrade pip and install dependencies
pip install --upgrade pip -q
pip install -r requirements.txt

echo "✓ Backend dependencies installed"

# -----------------------------------------------------------------------------
# Frontend Setup
# -----------------------------------------------------------------------------
echo ""
echo "📦 Setting up Next.js frontend..."

cd frontend
pnpm install
cd ..

echo "✓ Frontend dependencies installed"

# -----------------------------------------------------------------------------
# Environment Setup
# -----------------------------------------------------------------------------
echo ""
if [ ! -f ".env" ]; then
    echo "⚠️  Creating .env from .env.sample..."
    cp .env.sample .env
    echo "   Please edit .env with your configuration."
else
    echo "✓ .env file already exists"
fi

# -----------------------------------------------------------------------------
# Done
# -----------------------------------------------------------------------------
echo ""
echo "========================================"
echo "✅ Setup complete!"
echo "========================================"
echo ""
echo "Quick Start:"
echo "  • Run 'make dev' to start both backend and frontend"
echo "  • Or use VS Code: Ctrl+Shift+P → 'Tasks: Run Task' → '🚀 Start Certinator'"
echo ""
echo "URLs:"
echo "  • Frontend: http://localhost:3000"
echo "  • Backend:  http://localhost:8087"
echo ""
echo "⚠️  Remember to configure your .env file before starting!"
