# AGENTS.md

## Duopus NRCS — agent instructions

**Single source of truth for product scope:** [`docs/PHASE1.md`](docs/PHASE1.md). Implement only what that document describes for Phase 1. Treat everything listed under *Out of scope* as intentionally absent from the repo unless the brief is updated.

### Stack (Phase 1)

- **Backend:** Python 3.12, FastAPI, SQLModel, **SQLite** (`DATABASE_URL`). Dependencies and lockfile live under `backend/` (`pyproject.toml`, `uv.lock`). Schema is created with **`SQLModel.metadata.create_all`** (no Alembic in this phase).
- **Frontend:** `frontend/rundown-ui` and `frontend/prompter` — local dev with Vite (`npm run dev`). For a **one-command dev/smoke-test stack**, use Docker Compose from the repo root (see below); otherwise run the API and Vite dev servers separately.

### Commands

**Backend (from `backend/`)**

Install [uv](https://docs.astral.sh/uv/), then:

- `uv sync --extra dev` — create `.venv` and install from `uv.lock`
- `uv run pytest` — tests
- `uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000` — API (needs `SECRET_KEY` in the environment or `.env`)

After changing dependencies in `pyproject.toml`, run `uv lock` and commit `uv.lock`.

**Frontends**

- `cd frontend/rundown-ui && npm install && npm run dev`
- `cd frontend/prompter && npm install && npm run dev` — prompter handoff view (`/prompter/:storyId`); polls the API as described in `docs/PHASE1.md`

**Docker Compose (optional, dev / smoke testing)**

- Copy `.env.docker.example` to `.env.docker` (gitignored) and set at least `SECRET_KEY`; add or change any API env vars there (same semantics as `.env` for the backend).
- From the repo root: `docker compose up --build` — builds `backend/Dockerfile`, runs API on **8000**, rundown UI on **5173**, prompter on **5174**. SQLite uses the `duopus-sqlite` volume; see `docs/PHASE1.md` for rationale and Vite proxy details (`DUOPUS_API_PROXY`).

### Default dev login

See **Seed data** in `docs/PHASE1.md` (admin user and password for local development).
