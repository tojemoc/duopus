# AGENTS.md

## Duopus NRCS

Docker Compose brings up PostgreSQL 16, Redis 7, the FastAPI backend (with Alembic migrations on startup), and nginx (static `rundown-ui` at `/`, `prompter` at `/prompter/`, proxy `/api` and `/ws` to the backend).

Prebuilt **backend** and **nginx** images are published to GHCR on every push to `main` (workflow `Publish GHCR images`). Compose defaults to `ghcr.io/tojemoc/duopus-backend:latest` and `ghcr.io/tojemoc/duopus-nginx:latest`; override with `DUOPUS_BACKEND_IMAGE` / `DUOPUS_NGINX_IMAGE` (see `.env.example`). Until the first publish succeeds, run `docker compose build` locally. Forks typically keep `build:` and override those image variables to their own registry.

Copy `.env.example` to `.env` if you want to override defaults locally. Postgres credentials, `POSTGRES_URL`, and `SECRET_KEY` are resolved at **container runtime** from your environment or `.env` (Compose interpolation); committed defaults are for local development only—change them for shared or production hosts. Adjust `VMIX_HOST` to your vMix machine’s LAN IP.

**GHCR trade-offs:** `latest` can change without notice (pin a digest or SHA tag for reproducible deploys). New packages may default to private visibility—set the package to public if you need anonymous `docker pull`. Pulling third-party images means you trust the publisher’s build; building from source (`docker compose build`) avoids that but costs build time.

### Commands

**Backend (from `backend/`)**

- `python3 -m pip install -r requirements.txt` — install dependencies
- `python3 -m pytest` — run tests (vMix tally parsing + rundown engine DB logic)
- `python3 -m uvicorn main:app --reload --host 0.0.0.0 --port 8000` — local API (requires Postgres + Redis + env)

**Database migrations**

- `POSTGRES_URL=... python3 -m alembic upgrade head` — apply migrations (also runs automatically in the backend container entrypoint)

**Frontends**

- `cd frontend/rundown-ui && npm install && npm run build`
- `cd frontend/prompter && npm install && npm run build`

**Companion module**

- `cd companion-module && npm install && node --check src/index.js`

**Docker**

- `docker compose build` then `docker compose up` from the repo root (requires Docker).
