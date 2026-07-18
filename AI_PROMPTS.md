# AI_PROMPTS.md

**AI tool used:** Claude (Anthropic), via the Claude.ai chat interface with code execution.
**Candidate name:** [Biswamber Rout]
**Candidate role:** Directed the architecture and requirements, reviewed and tested every
generated file, fixed data/logic bugs found during testing, and made all final
deployment decisions.

---

## Prompt 1 — Architecture

> "Here's the assessment brief [pasted PDF]. Given a 24-hour deadline, propose a stack
> that's fast to build and easy to deploy, and explain the tradeoffs versus the
> recommended React/Next.js + Postgres stack."

**What AI generated correctly:** A recommendation for FastAPI + SQLite + a build-free
HTML/JS frontend, with a clear rationale (no build-step risk, single-service deploy,
still upgradeable to Postgres via one env var).

**What I changed:** Confirmed SQLite was acceptable per the brief's own text ("SQLite
acceptable for local demo") before committing to it, rather than taking the AI's word
for it.

---

## Prompt 2 — Database design

> "Design SQLAlchemy models for employees, projects, seats, and seat_allocations matching
> this schema suggestion from the brief [pasted section 7], with proper foreign keys and
> unique constraints for the business rules in section 8."

**What AI generated correctly:** Full `models.py` with relationships, a composite unique
constraint on `(floor, zone, seat_number)`, and unique constraints on employee email/code.

**What I fixed:** None required — verified constraints manually by attempting duplicate
inserts against the running database (see "How I verified" below).

---

## Prompt 3 — Backend APIs

> "Implement every endpoint listed in section 5 of the brief using FastAPI, with Pydantic
> schemas for validation, proper 404/400 error handling, and query-param based
> filtering for the GET list endpoints."

**What AI generated correctly:** All required endpoints (`/employees`, `/projects`,
`/seats`, `/dashboard/*`, `/ai/query`) with working filters and validation.

**What AI generated incorrectly:** Initially omitted the `email-validator` dependency
needed by Pydantic's `EmailStr` type, which crashed the server on startup.

**What I manually fixed:** Added `pydantic[email]` to `requirements.txt` and installed
`email-validator` directly; re-ran the server to confirm the fix.

---

## Prompt 4 — Seat Allocation Logic

> "Implement the proximity-based allocation logic from section 3.4: prefer seats near
> existing project teammates, fall back to a preferred zone, then to any available seat.
> Enforce rules 1–4 from section 8 (one active seat per employee, one active employee
> per seat, released seats become available, reserved seats excluded)."

**What AI generated correctly:** The three-tier fallback logic in `find_best_seat()`,
and correct status transitions in `allocate_seat()` / `release_seat()`.

**What I fixed:** None in the logic itself, but I found and fixed a **seed-data** bug
downstream of it (see Prompt 5) where the ratio of seats to employees was wrong.

---

## Prompt 5 — Seed Data

> "Write a seed script generating 5,000 employees, 5+ floors, 10+ zones, 5,500+ seats,
> 10+ projects, 500+ available seats, 100+ reserved seats, and 50+ pending-allocation
> employees, matching the schema."

**What AI generated incorrectly:** The first version only produced **480 seats**
(6 bays × 8 seats × 10 zones) — far short of the 5,500 minimum — and a second pass at
allocation math left **0 available and 0 reserved seats** because every seat got consumed
allocating to non-pending employees before the reserved/available split ran.

**What I manually fixed:** Recalculated bay/seat density (20 bays × 28 seats per zone
→ 5,600 total seats) and rewrote the post-allocation split logic to guarantee a minimum
available/reserved count regardless of how many employees needed seats, rather than
using a percentage of "whatever's left."

**How I verified:** Ran the script and checked the printed summary against every minimum
in section 6 of the brief before moving on — see the table in `README.md`.

---

## Prompt 6 — AI Assistant

> "Build the natural-language assistant from section 3.7. Minimum requirement first:
> a reliable keyword/intent parser answering the sample queries in the brief exactly in
> the format shown. Also add an optional LLM fallback path for anything the parser can't
> classify, gated behind an API key env var so the core assistant works without one."

**What AI generated correctly:** Intent handlers for all six sample query types (seat
lookup, project assignment, available seats, nearby colleagues, utilization, allocation
guidance), matching the brief's exact sample response format
("`<Name> is seated on Floor X, Zone Y, Bay Z, Seat W. They are assigned to Project N.`").

**What I fixed:** Nothing — but I deliberately tested edge cases the AI hadn't been asked
about (e.g. an employee with no project assigned, a floor/zone combination with zero
available seats) to confirm it degraded gracefully rather than erroring.

---

## Prompt 7 — Frontend

> "Build a single-file HTML/Tailwind/vanilla-JS dashboard covering: summary stats,
> project/floor utilization, employee directory search, seat map filtering, a new-joiner
> form that calls the create + allocate endpoints in sequence, and a chat UI for the AI
> assistant. No build step — must run by opening the file or serving it statically."

**What AI generated correctly:** All five views, wired to the real API with fetch calls,
no framework dependency.

**What I fixed:** Nothing functionally, but I directed the visual design explicitly
(a "blueprint/floor-plan" theme instead of a generic dashboard look) since the AI's
first instinct for styling defaults to generic templates — I asked for a look
specifically tied to the subject matter.

---

## Prompt 8 — Testing

> "Before we call anything done, run the actual server and curl every endpoint category
> (dashboard, employee search, seat allocation, all six AI query types) and show me the
> real output, not just the code."

**What AI generated correctly:** Live test output for every endpoint, confirming correct
JSON shapes and correct AI assistant answers.

**What this caught:** The seed-data seat-count bug (Prompt 5) was only caught because I
insisted on running the seed script and reading its own summary output rather than
trusting the code by inspection.

---

## Prompt 9 — Debugging

> "The uvicorn server won't start — here's the traceback." [pasted `ModuleNotFoundError:
> email_validator`]

**What AI generated correctly:** Correctly diagnosed the missing optional Pydantic
dependency and gave the exact `pip install` fix.

**How I verified:** Re-ran the server and re-tested the `/employees` POST endpoint that
depends on `EmailStr` validation to confirm the fix actually resolved it, not just that
the server started.

---

## Prompt 10 — Deployment & Refactoring

> "Write a Dockerfile and a Railway-compatible Procfile for this project, and a
> deployment README a non-DevOps person could follow in under 20 minutes."

**What AI generated correctly:** A working Dockerfile pattern (standard Python slim
image, seed-at-build-time for demo purposes) and Procfile.

**What I noted as a limitation:** I could not build/run the actual Docker image inside
the development sandbox (no Docker daemon available there), so the Dockerfile is
verified by inspection against a standard, well-known pattern rather than an actual
build — **this should be smoke-tested once on the real deployment platform** before
final submission, and is flagged as a follow-up in `DEPLOYMENT.md`.

---

## Prompt 11 — Deployment Debugging (Postgres Migration)

After initial deployment to Railway, discovered the SQLite database was being wiped 
on every redeploy since Railway's filesystem is ephemeral. Migrated to Railway's 
managed PostgreSQL for persistence.

First attempt crashed with `ImportError: libpq.so.5: cannot open shared object file` — 
`psycopg2-binary`'s compiled binary wasn't compatible with Railway's build image. 
Fixed by switching to `pg8000`, a pure-Python Postgres driver requiring no system 
library, and updating `database.py` to rewrite the `DATABASE_URL` connection string 
accordingly.

Also found a text-contrast bug in the AI Assistant chat UI (white bubble background 
inheriting light text color from a parent dark panel, making answers unreadable) — 
fixed with an explicit `color` override on `.chat-bubble-ai`.

**How verified:** Re-ran `seed_data.py` against the live Postgres instance via 
Railway's console, confirmed `/dashboard/summary` returned correct data, then 
triggered a redeploy and re-checked the same endpoint to confirm data persisted 
(unlike the earlier SQLite setup).

## Summary: what I validated manually, end to end

- Started the real FastAPI server and hit every endpoint category with `curl`, reading
  actual JSON responses rather than trusting generated code by inspection.
- Ran the seed script and cross-checked its printed summary numbers against every
  minimum in section 6 of the brief.
- Opened the frontend in a headless browser and confirmed the dashboard, directory
  search, and AI chat actually populate from live API calls (not just that the file
  has no syntax errors).
- Deliberately tried invalid/edge-case inputs (duplicate email, allocating a seat to an
  employee who already has one, querying seats for a floor with none available) to
  confirm error handling matches the business rules in section 8.
- Have **not** yet completed a live deployment smoke test — this is the next step and is
  called out explicitly in `DEPLOYMENT.md` as the first thing to do after cloning the
  repo to Railway/Render.
