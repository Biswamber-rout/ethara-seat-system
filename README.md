# Ethara Seat Allocation & Project Mapping System

A full-stack application for managing seat allocation and project mapping across ~5,000
Ethara employees, built for the Ethara Vibe Coding Assessment.

## What this does

- Tracks employees, projects, floors/zones/seats, and the mapping between them
- Auto-allocates seats for new joiners, prioritizing proximity to their project team,
  with automatic fallback to alternate zones when the preferred zone is full
- Prevents duplicate seat/employee allocation (enforced both in business logic and at
  the database constraint level)
- Provides a dashboard with company-wide, project-wise, and floor-wise seat utilization
- Includes a natural-language AI assistant (keyword/intent-based, with an optional LLM
  fallback) for queries like "Where is employee Amit seated?"

## Tech stack

| Layer      | Choice                                   | Why |
|------------|-------------------------------------------|-----|
| Backend    | Python, FastAPI, SQLAlchemy               | Fast to build, auto-generated OpenAPI docs at `/docs`, matches the brief's recommended stack |
| Database   | SQLite by default, Postgres via `DATABASE_URL` | SQLite needs zero setup for local/demo use; swapping to Postgres is a one-line env var change |
| Frontend   | Single-page HTML + Tailwind (CDN) + vanilla JS | No build step, so it deploys in seconds and stays easy to debug under a tight deadline |
| AI Assistant | Rule/intent-based NLP parser, optional LLM fallback | 100% reliable for a live demo (no API key / network dependency); the LLM fallback path is included and documented for the "advanced" requirement |

> **Why not React/Next.js for the frontend?** Given the 24-hour turnaround, a build-free
> single HTML file removes an entire category of deployment risk (broken builds, missing
> env vars at build time) while still delivering a fully responsive, componentized UI.
> The codebase is structured so it could be lifted into React components later without
> re-architecting the API layer.

## Project structure

```
ethara-seat-system/
├── backend/
│   ├── main.py            # FastAPI app & all API endpoints
│   ├── models.py          # SQLAlchemy ORM models
│   ├── schemas.py         # Pydantic request/response schemas
│   ├── database.py        # DB engine/session setup
│   ├── allocation.py      # Seat allocation business logic & rules
│   ├── ai_assistant.py    # NLP query handling (intent parser + optional LLM)
│   ├── seed_data.py       # Generates 5,000 employees / 5,600 seats / 11 projects
│   ├── requirements.txt
│   └── Procfile            # For Railway/Render process definitions
├── frontend/
│   └── index.html          # Dashboard, directory, seat map, new-joiner form, AI chat
├── Dockerfile
├── AI_PROMPTS.md
└── README.md (this file)
```

## Running locally

```bash
# 1. Backend
cd backend
python3 -m venv venv && source venv/bin/activate   # optional but recommended
pip install -r requirements.txt

# 2. Seed the database (creates ethara.db with 5,000 employees, 5,600 seats, etc.)
python seed_data.py

# 3. Start the API
uvicorn main:app --reload --port 8000
# API now running at http://localhost:8000, interactive docs at http://localhost:8000/docs

# 4. Frontend — in a second terminal
cd ../frontend
python3 -m http.server 8080
# open http://localhost:8080 in your browser
```

By default the frontend calls `http://localhost:8000`. To point it at a deployed backend,
open `frontend/index.html` and add before the closing `</head>`:
```html
<script>window.ETHARA_API_BASE = "https://your-backend-url.up.railway.app";</script>
```

## Seed data

`seed_data.py` generates data that clears every minimum specified in the assessment brief:

| Requirement            | Minimum | Generated |
|-------------------------|---------|-----------|
| Employees                | 5,000   | 5,000 |
| Floors                   | 5       | 5 |
| Zones                     | 10      | 10 |
| Seats                     | 5,500   | 5,600 |
| Projects                  | 10      | 11 |
| Available seats           | 500     | 511 |
| Reserved seats             | 100     | 150 |
| Pending-allocation employees | 50   | ~91 (randomized each run unless seeded) |

Run `python seed_data.py` again any time to reset to a fresh, consistent dataset — it
truncates and re-seeds rather than appending.

## Business rules enforced

1. One employee can have only one **active** seat allocation at a time.
2. One seat can be actively allocated to only one employee at a time.
3. Releasing a seat immediately returns it to `Available`.
4. `Reserved` and `Maintenance` seats are excluded from auto-allocation until their
   status is explicitly changed.
5. New joiners are allocated near their project teammates first; if no seat is free in
   that zone, the system falls back to the requested `preferred_zone`, then to any
   available seat company-wide.
6. Duplicate employee email is rejected (unique constraint + explicit check).
7. Duplicate seat number on the same floor/zone is rejected (unique constraint + check).
8. Dashboard totals are computed live from the database on every request, so they're
   always current after an allocation or release.

## API reference

Full interactive documentation (Swagger UI) is auto-generated by FastAPI at `/docs`
once the backend is running (e.g. `http://localhost:8000/docs`), and the raw OpenAPI
schema is at `/openapi.json`. All endpoints listed in the assessment brief are
implemented — see the brief or `/docs` for the complete list of routes, request/response
shapes, and to try them live.

Example AI assistant call:
```bash
curl -X POST http://localhost:8000/ai/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Where is employee Danielle Johnson seated?"}'
```

## Deployment

See `AI_PROMPTS.md` for the exact prompts used and `DEPLOYMENT.md` for step-by-step
deployment instructions (Railway recommended for the backend + SQLite; the frontend can
be served as a static site on Railway, Netlify, or Vercel).

## Known limitations / next steps

- The AI assistant's LLM fallback path (`ai_assistant.py::_llm_fallback`) is implemented
  but disabled unless an `ANTHROPIC_API_KEY`/`OPENAI_API_KEY` env var is set — this was a
  deliberate choice so the core assistant works reliably offline for grading/demo, while
  still satisfying the "advanced AI requirement" as an optional, documented extension.
- No authentication layer is implemented (not required by the brief for this scope);
  adding role-based auth for HR/Admin vs. Employee views would be the natural next step.
- SQLite is used for the demo deployment; `DATABASE_URL` can be pointed at a managed
  Postgres instance (e.g. Railway's Postgres add-on) with no code changes.
