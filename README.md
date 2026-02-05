# PiNotes Lite

A lightweight, read-only web portal for browsing personal notes. Mobile-friendly, fast, and Tailscale-only.

## Features
- Read-only Markdown note viewer
- Inline image rendering (relative paths + Obsidian `![[]]` embeds)
- File tree navigation (PARA structure)
- Full-text search
- Simple auth + cookie sessions

## Tech Stack
- **Frontend:** Vite + React + CSS (mobile-first)
- **Backend:** Python 3.11 + FastAPI
- **Deployment:** Docker Compose → Portainer (Raspberry Pi)

---

## Dev Setup

### Prerequisites
- Node.js 20+
- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (Python package manager)

### Install
```bash
make install
```

### Run (two terminals)
```bash
# Terminal A — FastAPI backend
make dev-backend   # → http://localhost:8000

# Terminal B — Vite dev server (proxies /api/* → backend)
make dev-frontend  # → http://localhost:5173
```

Browse to `http://localhost:5173` — Vite proxies `/api/*` to FastAPI automatically.

### Production build
```bash
make build         # compiles frontend → frontend/dist/
# Then run backend alone — it serves the built SPA:
make dev-backend   # → http://localhost:8000 (serves React + API)
```

---

## Docker

```bash
docker compose build
docker compose up -d
# → http://localhost:8090
```

---

## Project Structure
```
pinotes-lite/
├── app/                  # FastAPI backend
│   └── main.py           # routes + static serving
├── frontend/             # Vite + React app
│   ├── src/
│   │   ├── App.jsx       # root component
│   │   └── App.css       # styles
│   ├── vite.config.js    # dev proxy config
│   └── index.html
├── Dockerfile            # multi-stage build
├── docker-compose.yml    # Portainer-ready
├── Makefile              # convenience targets
└── pyproject.toml        # Python deps (uv)
```
