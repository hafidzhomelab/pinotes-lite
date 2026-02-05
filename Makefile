.PHONY = install dev-backend dev-frontend build clean

install:
	cd frontend && npm install
	uv sync

dev-backend:
	uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

dev-frontend:
	cd frontend && npm run dev

build:
	cd frontend && npm run build

clean:
	rm -rf frontend/dist frontend/node_modules .venv

# ── Usage ──────────────────────────────────────────────────────
# 1.  make install          → install all deps
# 2a. make dev-backend      → start FastAPI (in terminal A)
# 2b. make dev-frontend     → start Vite dev server (in terminal B)
# 3.  make build            → production build (frontend/dist/)
