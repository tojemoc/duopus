# AGENTS.md

## Duopus NRCS

Docker Compose brings up PostgreSQL 16, Redis 7, the FastAPI backend (with Alembic migrations on startup), and nginx (static `rundown-ui` at `/`, `prompter` at `/prompter/`, proxy `/api` and `/ws` to the backend).

Copy `.env.example` to `.env` if you want to override defaults locally. Compose sets `POSTGRES_URL`, `REDIS_URL`, and `VMIX_HOST` via the `environment` block; adjust `VMIX_HOST` to your vMix machine’s LAN IP.

### Commands

**Backend (from `backend/`)**

Install [uv](https://docs.astral.sh/uv/) once (see upstream install instructions), then:

- `uv sync --extra dev` — create `.venv` and install dependencies from `uv.lock` (omit `--extra dev` for runtime-only installs)
- `uv run pytest` — run tests (vMix tally parsing + rundown engine DB logic)
- `uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000` — local API (requires Postgres + Redis + env)

After changing dependencies in `pyproject.toml`, run `uv lock` and commit the updated `uv.lock`.

**Database migrations**

- `POSTGRES_URL=... uv run alembic upgrade head` — apply migrations (also runs automatically in the backend container entrypoint)

**Frontends**

- `cd frontend/rundown-ui && npm install && npm run build`
- `cd frontend/prompter && npm install && npm run build`

**Companion module**

- `cd companion-module && npm install && node --check src/index.js`

**Docker**

- `docker compose build` then `docker compose up` from the repo root (requires Docker).
