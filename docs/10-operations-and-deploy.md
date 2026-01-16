# Operations: local development, deploy, env

## Local development

### Frontend (pnpm)
From repo root:
- install: `pnpm install`
- run: `pnpm --filter web dev`
- build: `pnpm --filter web build`

Frontend env:
- `NEXT_PUBLIC_API_URL=http://localhost:8080`

### Backend (FastAPI)
From `services/api`:
- create venv and install deps (example with uv):
  - `uv venv`
  - `uv pip install -r requirements.txt`
- run:
  - `uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload`

Backend env:
- `DATABASE_URL`
- `REDIS_URL`
- `SERPAPI_API_KEY`
- `OPENAI_API_KEY` (for guides generation)
- `CORS_ORIGINS` (CORS; also accepts `ALLOWED_ORIGINS` for backward compatibility)
- `AUTO_MIGRATE` (set `true` on Railway to run Alembic on deploy/start)

## Deploy

### Vercel (apps/web)
- Root Directory: `apps/web`
- Install: `pnpm install --frozen-lockfile`
- Build: `pnpm build`
- Env:
  - `NEXT_PUBLIC_API_URL=https://api.example.com`

### Railway (services/api)
- Root Directory: `services/api`
- Start command: Dockerfile default (`./scripts/start.sh`)
- Env:
  - `DATABASE_URL` (Railway Postgres)
  - `REDIS_URL` (Upstash or Railway Redis)
  - `SERPAPI_API_KEY`
  - `OPENAI_API_KEY`
  - `CORS_ORIGINS=["https://app.example.com"]`
  - `AUTO_MIGRATE=true`

### Workers (optional)
Create a second Railway service from `services/worker` to run:
- scheduled refresh (prices)
- scheduled refresh (country facts/guides)
- queue processing for hydration backfills

## Observability
- Log request id, offer id, sku id
- Capture SerpAPI cost counters (calls/day)
- Track hydration success rate
- Track guide freshness distribution
