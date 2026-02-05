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

# Install Python dependencies via pip (avoids external uv image pull)
COPY pyproject.toml ./
RUN pip install --no-cache-dir fastapi uvicorn[standard] argon2-cffi

# Copy application code
COPY app/ ./app/

# Copy the built frontend so FastAPI can serve it
COPY --from=frontend-build /frontend/dist/ ./frontend/dist/

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
