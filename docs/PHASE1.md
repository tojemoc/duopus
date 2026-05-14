# Duopus — Phase 1 product brief

This file is the **authoritative scope** for Phase 1. Other docs should not contradict it. If code and this brief disagree, **update the code** to match the brief (or explicitly amend this document in the same change).

---

## Context

Duopus is an on-premises NRCS (Newsroom Computer System) replacing a Google Sheets workflow. Non-technical journalists and producers are the primary users. Frictionless UX is a hard requirement — if it needs explaining, it needs redesigning.

Phase 1 is a **self-contained, locally-runnable web app**. No broadcast integrations yet.

---

## Out of scope for Phase 1 — do not implement

- WebSockets or Redis  
- CasparCG or vMix integration  
- Companion / Streamdeck module  
- Docker / docker-compose (no containerized stack in this phase)  
- Alembic migrations (**SQLModel `create_all` is sufficient**)  
- Prompter scroll velocity / mirror flip modes (use QPrompt externally)  
- Auth beyond simple **session-based** login (FastAPI-Users with cookies; no JWT complexity)

---

## Stack

- **Backend:** Python 3.12, FastAPI, SQLModel, **SQLite**  
- **Frontend:** React 18 + Vite + TypeScript, TailwindCSS  
- **Auth:** FastAPI-Users with SQLite backend, session cookies  

---

## Data models (target)

The mental model: a **Story** has a **beat strip** — an ordered inline sequence of category chips (VO / ILU / SYN), not separate sub-stories.

### `beats` JSON (Story and TemplateSlot)

Replace a single `category` field with a `beats` JSON column (stored as a string in SQLite):

```python
# Each beat object:
{
  "id": "uuid",
  "category": "VO" | "ILU" | "SYN",
  "duration": 15,   # seconds; optional; defaults to 0
  "note": ""        # optional short note
}
```

`Story.planned_duration` is the **sum of beat durations** where set; if beats have no durations, use a **manual override** field (`planned_duration_override` in the implementation).

`TemplateSlot` carries the same `beats` column as the **default** sequence for new stories from that slot.

### Reference model sketch (align `models.py` over time)

```python
class User(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    username: str = Field(unique=True)
    display_name: str
    password_hash: str
    role: str = "editor"   # "editor" | "admin"

class Template(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    recurrence: str        # "daily" | "weekdays" | "weekly"
    recurrence_day: int | None  # 0=Mon–6=Sun, only for weekly
    auto_generate_days_ahead: int = 1

class TemplateSlot(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    template_id: int = Field(foreign_key="template.id")
    position: int
    label: str
    segment: str
    planned_duration: int = 0   # seconds
    title_in: int = 0
    title_duration: int = 5
    notes: str = ""
    beats: str = "[]"

class Rundown(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    template_id: int | None = Field(foreign_key="template.id")
    title: str
    show_date: date
    status: str = "preparing"  # "preparing" | "live" | "done"
    generated_at: datetime | None = None

class Story(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    rundown_id: int = Field(foreign_key="rundown.id")
    position: int
    label: str
    segment: str
    planned_duration: int = 0
    planned_duration_override: int | None = None  # used when beats carry no durations
    title_in: int = 0
    title_duration: int = 5
    ready: bool = False
    status: str = "pending"     # "pending" | "live" | "done"
    beats: str = "[]"
    locked_by: int | None = Field(foreign_key="user.id")
    locked_at: datetime | None = None

class Script(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    story_id: int = Field(foreign_key="story.id")
    body: str = ""
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    updated_by: int | None = Field(foreign_key="user.id")
```

**Implementation note:** FastAPI-Users expects an `email` (and `hashed_password`) field rather than `username` / `password_hash`. Treat **`email` as the login identifier**; seed data uses `admin@example.com` for the admin account.

---

## Beat strip UI

In the rundown row, beats render as a horizontal strip of coloured chips; totals show planned duration from beats. In the story panel, beats are reorderable with inline edit (category, duration, note) and a `+` control — see the brief you were handed for full UX constraints.

---

## Locking model

When a user opens a story for editing, set `locked_by` and `locked_at`. Others see read-only with **“Being edited by [display_name]”**. Release lock on save, explicit close, or after **5 minutes** of inactivity (`locked_at` check). Never silently block — always show who holds the lock.

---

## Template auto-generation

- Admin UI for templates and slots  
- **Lifespan** background loop: once per day at configurable UTC time, apply recurrence and generate rundowns **N days ahead** if missing  
- Generated rundowns: story rows from template slots, empty scripts  
- `POST /api/templates/{id}/generate?date=YYYY-MM-DD` for manual generation  
- If rundown already exists for template + date → **clear error**, no overwrite  

---

## REST API surface (Phase 1)

```
POST   /api/auth/login
POST   /api/auth/logout
GET    /api/auth/me

GET    /api/users
POST   /api/users
PATCH  /api/users/{id}
DELETE /api/users/{id}

GET    /api/templates
POST   /api/templates
PATCH  /api/templates/{id}
DELETE /api/templates/{id}
POST   /api/templates/{id}/generate

GET    /api/rundowns
POST   /api/rundowns
GET    /api/rundowns/{id}/full
PATCH  /api/rundowns/{id}

PATCH  /api/stories/{id}
PATCH  /api/stories/{id}/ready
PATCH  /api/stories/{id}/status
PATCH  /api/stories/reorder
POST   /api/stories/{id}/lock
DELETE /api/stories/{id}/lock

GET    /api/scripts/{story_id}
PUT    /api/scripts/{story_id}
```

Prompter polling (handoff to QPrompt): **`GET /api/prompter/{story_id}`** — large-type prompter page polls roughly every **3 seconds** (see `frontend/prompter`).

---

## Frontend pages (summary)

| Area | Route | Notes |
|------|--------|--------|
| Login | `/` or login route | Username + password; no self-registration |
| Rundown list | `/` | Today’s rundowns first; ready counts; status |
| Rundown editor | `/rundown/:id` | Main working view; beat strip; locks visible |
| Templates | `/admin/templates` | Admin only |
| Users | `/admin/users` | Admin only |
| Prompter | `/prompter/:storyId` | New tab; dark, large text; slim top bar |

---

## UX constraints

- No routine action > **2 clicks** from the rundown editor  
- Lock state **always visible** (no hover-only)  
- Category colours distinct (VO / ILU / SYN)  
- Segment names as specified — **no abbreviations** in UI  
- Intro / tech rows visually distinct per brief  
- Errors: **plain language** — no raw HTTP codes for users  

---

## Seed data (first run)

- One **admin** user for development: sign in with email **`admin@example.com`** and password **`duopus2025`** (unless `ADMIN_PASSWORD` is set, e.g. in production).  
- One example template **“Večerné správy”** with segments in newsroom order, **daily** recurrence.  
- **Today’s** rundown generated from that template if missing.  

---

## Running locally (no Docker)

1. **Backend:** from `backend/`, `uv sync --extra dev`, set `SECRET_KEY` (and optional `DATABASE_URL`), then `uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000`.  
2. **Rundown UI:** `frontend/rundown-ui` — `npm install` && `npm run dev` (Vite proxies `/api` to the backend per `vite.config`).  
3. **Prompter:** `frontend/prompter` — `npm run dev` on a second port if needed; configure API origin as in Vite config.  

`CORS_ORIGINS` in `.env` must include the Vite dev origin (e.g. `http://localhost:5173`).
