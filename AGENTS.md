# AGENTS.md

## Duopus NRCS

Docker Compose brings up PostgreSQL 16, Redis 7, the FastAPI backend (with Alembic migrations on startup), and nginx (static `rundown-ui` at `/`, proxy `/api` and `/ws` to the backend). The `frontend/prompter` app is not built into the nginx image; run it separately (for example `npm run dev` in that folder) if you need it.

Copy `.env.example` to `.env` if you want to override defaults locally. Compose sets `POSTGRES_URL`, `REDIS_URL`, and `VMIX_HOST` via the `environment` block; adjust `VMIX_HOST` to your vMix machine’s LAN IP.

### Commands

**Backend (from `backend/`)**

- `python3 -m pip install -r requirements.txt` — install dependencies
- `python3 -m pytest` — run tests (vMix tally parsing + rundown engine DB logic)
- `python3 -m uvicorn main:app --reload --host 0.0.0.0 --port 8000` — local API (requires Postgres + Redis + env)

**Database migrations**

- `POSTGRES_URL=... python3 -m alembic upgrade head` — apply migrations (also runs automatically in the backend container entrypoint)

**Frontends**

- `cd frontend/rundown-ui && npm install && npm run build` — bundled into the Docker nginx image
- `cd frontend/prompter && npm install && npm run dev` — local development only (not served by Compose nginx)

**Companion module**

- `cd companion-module && npm install && node --check src/index.js`

**Docker**

- `docker compose build` then `docker compose up` from the repo root (requires Docker).
