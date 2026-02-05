# PiNotes Lite — 1-Pager

## Vision
A lightweight, read-only web portal to browse and read notes from the personal vault (`/home/professor/notes`), optimized for mobile. Faster and simpler than PiNotes — no editing, no complex auth, just clean reading.

## Target User
Single user (Hafidz), primarily on mobile browser via Tailscale.

## MVP Outcomes
- Browse notes via file tree navigation (PARA folder structure)
- Render Markdown notes with full formatting
- **Inline image rendering** — images referenced in notes (relative paths, `_attachments/`) display correctly without broken links
- Full-text search across the vault
- Tailscale-only access (no public internet exposure)
- Simple auth (username + password, cookie session) — lightweight but not open

## Non-Goals (v1)
- Note creation or editing
- File uploads or attachments
- Wikilinks / backlinks rendering
- Real-time sync or conflict detection
- User management or roles

## Proposed Tech Stack
- **Frontend:** Vite + React + CSS (mobile-first layout)
- **Backend:** Python (FastAPI) — serves Markdown files, resolves image paths, handles search indexing
- **Deployment:** Docker Compose on Raspberry Pi via Portainer
- **Access:** Tailscale only, subdomain via Nginx Proxy Manager + Cloudflare

## Success Metrics
- Notes load and render in < 1 second
- Images render inline without broken links
- Search returns relevant results in < 500 ms
- Smooth and usable on mobile browser

## Key Risks
- **Image path resolution** — relative paths and `_attachments/` references need correct mapping
- **Path traversal** — read-only but vault must be sandboxed; no access outside `/home/professor/notes`
- **Search performance** — vault indexing needs to stay fast as notes grow
