# ── Stage 1: build the React frontend ───────────────────────────────────────
FROM node:20-alpine AS frontend-build
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci --ignore-scripts
COPY frontend/ ./
RUN npm run build          # → /frontend/dist/

# ── Stage 2: Python runtime ─────────────────────────────────────────────────
FROM python:3.11-slim AS runtime
WORKDIR /app

# Drop in uv
COPY --from=astral-sh/uv:latest /uv /usr/local/bin/uv

# Install Python dependencies (cached layer)
COPY pyproject.toml uv.lock* ./
RUN uv sync --no-dev --frozen

# Copy application code
COPY app/ ./app/

# Copy the built frontend so FastAPI can serve it
COPY --from=frontend-build /frontend/dist/ ./frontend/dist/

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
