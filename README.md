# Sing-Along

Shared sing-along app for Hebrew and English songs. Your library is built from a one-time Google Takeout import, plus songs you add manually.

## Quick start

### Backend

```bash
cd backend
.venv\Scripts\activate
uvicorn main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:5175** (port 5175 avoids conflict with other Vite apps on 5173).

## One-time Takeout import (already done)

To re-import from CLI:

```bash
cd backend
.venv\Scripts\python -c "from pathlib import Path; from db.database import SessionLocal, init_db; from services.takeout_sync import import_takeout; init_db(); db=SessionLocal(); import_takeout(db, Path('../data/takeout/Takeout/YouTube and YouTube Music/history/watch-history.json'))"
```

Or use `scripts/parse_takeout.py` to preview rankings.

## Admin access

Mutating API calls and room sync require admin auth:

- **Browser:** click **Unlock admin** in the nav and enter `ADMIN_PASSWORD`.
- **CLI / curl:** send `X-Admin-Token: <ADMIN_TOKEN>` (set in `backend/.env`).

Copy `backend/.env.example` to `backend/.env` and set strong secrets before deploying.

## Add songs manually

In the app, click **Add song**. Or via API (after unlocking admin or with a token):

```bash
curl -X POST http://127.0.0.1:8000/api/songs \
  -H "Content-Type: application/json" \
  -H "X-Admin-Token: YOUR_ADMIN_TOKEN" \
  -d "{\"title\":\"שיר חדש\",\"artist\":\"אמן\",\"language\":\"he\"}"
```

## API

All JSON routes are under `/api`. Health check: `GET /health` (also `GET /api/health`).

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/library/status` | Song counts |
| GET | `/api/songs?lang=he\|en&q=` | Ranked song list |
| POST | `/api/songs` | Add song manually (admin) |
| POST | `/api/auth/login` | Browser admin login |
| GET | `/api/admin/export.json` | Full library JSON backup (admin) |
| GET | `/api/admin/db.sqlite` | SQLite file download (admin, SQLite only) |

## Production deployment

Pick a path:

- **Single host (Docker)** — same origin for UI + API, simplest. See below.
- **Split free-tier (GitHub Pages + Render + Supabase)** — see [the split deploy guide](#split-deploy-github-pages--render--supabase).


### Environment variables

Set these in `backend/.env` or your host's secret store (`backend/.env.example` lists all options):

| Variable | Purpose |
|----------|---------|
| `ENV=prod` | Enables strict config checks at startup |
| `ADMIN_TOKEN` | Secret for `X-Admin-Token` header |
| `ADMIN_PASSWORD` | Password for **Unlock admin** in the UI |
| `SESSION_SECRET` | Signs session cookies — generate with `openssl rand -hex 32` |
| `CORS_ORIGINS` | Comma-separated frontend URLs if not same-origin |
| `DATABASE_URL` | SQLite path or Postgres connection string |
| `STATIC_DIR` | Path to `frontend/dist` for single-container serve |

With `ENV=prod`, the server refuses to start if `ADMIN_TOKEN`, `ADMIN_PASSWORD`, or `SESSION_SECRET` still use dev defaults.

### Docker (single container)

Build and run from the repo root:

```bash
docker build -t sing-along .
docker run --rm -p 8080:8080 \
  -e ENV=prod \
  -e ADMIN_TOKEN=... \
  -e ADMIN_PASSWORD=... \
  -e SESSION_SECRET=... \
  -v singalong-data:/app/data \
  sing-along
```

Open **http://localhost:8080**. The image serves the React app at `/` and the API at `/api`.

### Post-deploy seed (Takeout)

Upload `watch-history.json` to the container/host, then:

```bash
cd backend
python scripts/seed_from_takeout.py --takeout /path/to/watch-history.json --enrich-limit 100
```

Use `--skip-enrich` to import only.

### Backups

As an authenticated admin:

```bash
curl -b cookies.txt -o export.json http://localhost:8080/api/admin/export.json
curl -H "X-Admin-Token: YOUR_ADMIN_TOKEN" -o singalong.db http://localhost:8080/api/admin/db.sqlite
```

## Split deploy: GitHub Pages + Render + Supabase

Free-tier setup where the React UI lives on GitHub Pages, the FastAPI backend runs on Render, and Postgres lives on Supabase (so songs persist when the free Render instance sleeps or redeploys).

```
GitHub Pages (UI)  ──►  Render (FastAPI)  ──►  Supabase (Postgres)
```

### 1. Supabase database

1. Create a project at <https://supabase.com>.
2. **Project Settings → Database → Connection string → URI** — copy the `postgresql://...` URL.
3. The backend auto-normalizes `postgres://` and `postgresql://` URLs to use the bundled `psycopg2` driver, so paste the URL as-is.

### 2. Render backend

1. Push this repo to GitHub.
2. In Render, **New → Blueprint** and point it at the repo. It picks up [`render.yaml`](./render.yaml).
3. Fill the prompted secrets:
   - `ADMIN_TOKEN` — strong random string (CLI / curl).
   - `ADMIN_PASSWORD` — strong random string (browser **Unlock admin**).
   - `DATABASE_URL` — the Supabase URI from step 1.
   - `CORS_ORIGINS` — your Pages URL, e.g. `https://YOUR_USER.github.io`.
4. Render generates `SESSION_SECRET` automatically. `ENV=prod` and `SESSION_COOKIE_CROSS_SITE=true` are pre-set in the blueprint.
5. Wait for the deploy. The API is now at `https://sing-along-api.onrender.com` (or whatever Render assigns) with routes under `/api`.

### 3. GitHub Pages frontend

1. In the repo: **Settings → Pages → Build and deployment → Source → GitHub Actions**.
2. **Settings → Secrets and variables → Actions → Variables (tab)** — add a repository variable named `VITE_API_BASE` set to your Render URL plus `/api`, e.g.:

   ```
   VITE_API_BASE = https://sing-along-api.onrender.com/api
   ```

3. Push to `main`. The included [`pages.yml`](./.github/workflows/pages.yml) workflow builds the frontend with `VITE_BASE_PATH=/<repo-name>/` and deploys to Pages.
4. Open `https://YOUR_USER.github.io/<repo-name>/`.

### 4. Seed songs

After Render is up, run the seed locally against the Supabase DB (so you don't have to upload Takeout to Render):

```bash
cd backend
$env:DATABASE_URL="postgresql://...supabase..."
python scripts/seed_from_takeout.py --takeout path/to/watch-history.json --enrich-limit 100
```

### Notes

- The free Render web service sleeps after 15 min idle and cold-starts in ~30 s. Songs and admin sessions survive because they live in Supabase.
- Cross-origin cookies require HTTPS on both sides — GitHub Pages and Render both provide it.
- If you change the Pages URL, update `CORS_ORIGINS` on Render to match (comma-separated to add more origins).
