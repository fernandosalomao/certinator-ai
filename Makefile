# =============================================================================
# Certinator AI — Makefile
# =============================================================================
# Quick start commands for development and testing.
# Run `make help` to see all available commands.

.PHONY: help install dev start stop backend frontend clean check-node

# Minimum Node.js version required
MIN_NODE_VERSION := 20.9.0

# Default target
help:
	@echo "Certinator AI - Development Commands"
	@echo "====================================="
	@echo ""
	@echo "Setup:"
	@echo "  make install     Install all dependencies (backend + frontend)"
	@echo ""
	@echo "Development:"
	@echo "  make dev         Start both backend and frontend (Ctrl+C to stop both)"
	@echo "  make backend     Start backend only"
	@echo "  make frontend    Start frontend only"
	@echo ""
	@echo "Utilities:"
	@echo "  make stop        Stop all running processes"
	@echo "  make clean       Remove virtual environment and node_modules"
	@echo "  make logs        Tail the backend server logs"
	@echo "  make check-node  Verify Node.js version"
	@echo ""
	@echo "Prerequisites:"
	@echo "  - Python 3.10+"
	@echo "  - Node.js 20.9+ and pnpm (run: nvm use)"
	@echo "  - Copy .env.sample to .env and configure"

# =============================================================================
# Setup
# =============================================================================

# Install all dependencies
install: install-backend install-frontend
	@echo "✓ All dependencies installed!"

install-backend:
	@echo "Installing backend dependencies..."
	@if [ ! -d ".venv" ]; then python3 -m venv .venv; fi
	@.venv/bin/pip install --upgrade pip -q
	@.venv/bin/pip install -r requirements.txt -q
	@echo "✓ Backend dependencies installed"

install-frontend: check-node
	@echo "Installing frontend dependencies..."
	@cd frontend && pnpm install
	@echo "✓ Frontend dependencies installed"

# Check Node.js version (>=20.9.0 required for Next.js)
check-node:
	@NODE_VER=$$(node -v 2>/dev/null | sed 's/v//'); \
	if [ -z "$$NODE_VER" ]; then \
		echo "❌ Node.js not found. Install Node.js >= $(MIN_NODE_VERSION)"; \
		echo "   https://nodejs.org/ or use nvm: nvm install $(MIN_NODE_VERSION)"; \
		exit 1; \
	fi; \
	MAJOR=$$(echo $$NODE_VER | cut -d. -f1); \
	MINOR=$$(echo $$NODE_VER | cut -d. -f2); \
	if [ "$$MAJOR" -lt 20 ] || ([ "$$MAJOR" -eq 20 ] && [ "$$MINOR" -lt 9 ]); then \
		echo "❌ Node.js $$NODE_VER is too old. Requires >= $(MIN_NODE_VERSION)"; \
		echo "   Run: nvm use $(MIN_NODE_VERSION)  (or nvm install $(MIN_NODE_VERSION))"; \
		exit 1; \
	fi; \
	echo "✓ Node.js $$NODE_VER"

# =============================================================================
# Development - Run Both Services
# =============================================================================

# Start both backend and frontend (Ctrl+C stops both)
dev: check-node
	@if [ ! -f ".env" ]; then \
		echo "⚠️  Missing .env file. Copy .env.sample to .env and configure it."; \
		exit 1; \
	fi
	@echo "Starting Certinator AI..."
	@echo "Backend:  http://localhost:8087"
	@echo "Frontend: http://localhost:3000"
	@echo ""
	@echo "Press Ctrl+C to stop both services"
	@echo "====================================="
	@trap 'kill 0' INT TERM; \
	(.venv/bin/python src/app.py --agui 2>&1 | tee certinator_server.log) & \
	(cd frontend && pnpm dev) & \
	(sleep 5 && open http://localhost:3000 2>/dev/null || xdg-open http://localhost:3000 2>/dev/null || true) & \
	wait

# =============================================================================
# Individual Services
# =============================================================================

backend:
	@if [ ! -f ".env" ]; then \
		echo "⚠️  Missing .env file. Copy .env.sample to .env and configure it."; \
		exit 1; \
	fi
	@echo "Starting backend on http://localhost:8087..."
	@.venv/bin/python src/app.py --agui 2>&1 | tee certinator_server.log

frontend: check-node
	@echo "Starting frontend on http://localhost:3000..."
	@cd frontend && pnpm dev

# =============================================================================
# Utilities
# =============================================================================

# Stop all running processes (backend and frontend)
stop:
	@echo "Stopping all Certinator processes..."
	@-pkill -f "src/app.py" 2>/dev/null || true
	@-pkill -f "next dev" 2>/dev/null || true
	@-pkill -f "node.*frontend" 2>/dev/null || true
	@echo "✓ All processes stopped"

# View backend logs
logs:
	@tail -f certinator_server.log

# Clean build artifacts
clean:
	@echo "Cleaning up..."
	@rm -rf .venv
	@rm -rf frontend/node_modules
	@rm -rf frontend/.next
	@rm -f certinator_server.log
	@echo "✓ Cleaned up. Run 'make install' to reinstall dependencies."
