# Deployment Guide (Railway — recommended, ~15–20 minutes)

This gets you a live backend URL + live frontend URL + GitHub repo, everything the
submission checklist (section 12) requires.

## 0. Push to GitHub first

```bash
cd ethara-seat-system
git init
git add .
git commit -m "Ethara Seat Allocation & Project Mapping System"
# create a new repo on github.com, then:
git remote add origin https://github.com/<your-username>/ethara-seat-system.git
git branch -M main
git push -u origin main
```

## 1. Deploy the backend on Railway

1. Go to [railway.app](https://railway.app) → sign in with GitHub → **New Project** →
   **Deploy from GitHub repo** → select your `ethara-seat-system` repo.
2. Railway will detect the `Procfile`. If it doesn't auto-detect the Python app, set:
   - **Root directory:** `backend`
   - **Build command:** `pip install -r requirements.txt`
   - **Start command:** `uvicorn main:app --host 0.0.0.0 --port $PORT`
3. Once deployed, open the service → **Settings** → **Networking** → **Generate Domain**.
   This gives you your live backend URL, e.g. `https://ethara-backend-production.up.railway.app`.
4. **Seed the database** — open the Railway service's **Shell** tab (or use the Railway
   CLI: `railway run python seed_data.py`) and run:
   ```
   python seed_data.py
   ```
   This creates and populates `ethara.db` on the deployed instance. Note: Railway's
   filesystem is ephemeral on redeploys — for a persistent demo, either re-run this after
   any redeploy, or attach a Railway volume, or switch to Railway's managed Postgres
   (see step 4 below).
5. Visit `https://<your-backend-url>/docs` to confirm the API is live and browsable.

## 2. (Optional but recommended) Switch to Postgres for persistence

1. In your Railway project, click **New** → **Database** → **Add PostgreSQL**.
2. Copy the generated `DATABASE_URL` from the Postgres service's **Variables** tab.
3. Go to your backend service → **Variables** → add `DATABASE_URL` with that value.
4. Redeploy, then re-run `python seed_data.py` once via the Shell tab to populate it.
   Data will now persist across redeploys.

## 3. Deploy the frontend

Simplest path — serve it as a second Railway service (static site), or use Netlify:

**Option A: Netlify (drag-and-drop, ~2 minutes)**
1. Before deploying, edit `frontend/index.html` and add this line just before `</head>`:
   ```html
   <script>window.ETHARA_API_BASE = "https://<your-backend-url>";</script>
   ```
2. Go to [app.netlify.com/drop](https://app.netlify.com/drop) and drag the `frontend`
   folder in. You'll get a live URL immediately (e.g. `https://ethara-seats.netlify.app`).

**Option B: Railway static service**
1. New service in the same Railway project → **Empty service** → connect the same GitHub
   repo, root directory `frontend`.
2. Add a static file server, e.g. set the start command to:
   `npx serve -s . -l $PORT`
3. Generate a domain as in backend step 3.

## 4. Update CORS if you lock it down later

`main.py` currently allows all origins (`allow_origins=["*"]`) for demo simplicity. If
you tighten this for a "production" story in your interview, restrict it to your actual
frontend domain and mention the tradeoff.

## 5. Final checklist before submitting

- [ ] Backend `/docs` loads and endpoints respond
- [ ] Frontend loads and dashboard numbers populate (confirms it's hitting the live backend, not localhost)
- [ ] Ran `python seed_data.py` against the deployed database at least once
- [ ] GitHub repo is public (or shared with the reviewer)
- [ ] README.md, AI_PROMPTS.md included in the repo root
- [ ] Take screenshots of: dashboard, employee directory, seat map, new-joiner
      allocation, AI assistant chat — save into a `/screenshots` folder in the repo
- [ ] Paste both live URLs + GitHub link into your submission email/form

## Alternative: Render instead of Railway

Render works almost identically:
1. New **Web Service** → connect repo → root directory `backend` → build command
   `pip install -r requirements.txt` → start command
   `uvicorn main:app --host 0.0.0.0 --port $PORT`.
2. New **Static Site** for the frontend → root directory `frontend` → publish directory `.`.
3. Same `ETHARA_API_BASE` edit and same seeding step via Render's Shell.
