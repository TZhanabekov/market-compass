# Market Compass API

FastAPI backend for Market Compass - Global iPhone price intelligence.

## Quick Start

### With Docker Compose (recommended)

From repository root:

```bash
docker compose up -d
```

API will be available at http://localhost:8080

### Local Development

```bash
cd services/api

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows

# Install dependencies
pip install -e ".[dev]"

# Set environment variables
export DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/market_compass"
export REDIS_URL="redis://localhost:6379/0"
export DEBUG=true

# Run development server
uvicorn app.main:app --reload --port 8080
```

## API Endpoints

### Health Check
```bash
curl http://localhost:8080/health
# {"ok": true}
```

### Home UI Bootstrap
```bash
curl "http://localhost:8080/v1/ui/home?sku=iphone-16-pro-256gb-black-new&home=DE&minTrust=80"
```

### CTA Redirect
```bash
curl -I "http://localhost:8080/r/offers/offer_jp_1"
# 302 redirect to merchant URL
```

## API Documentation

- Swagger UI: http://localhost:8080/docs
- ReDoc: http://localhost:8080/redoc
- OpenAPI JSON: http://localhost:8080/openapi.json

## Project Structure

```
services/api/
├── app/
│   ├── main.py           # FastAPI instance, middleware
│   ├── settings.py       # Pydantic Settings
│   ├── routes/           # API endpoints
│   │   ├── ui.py         # GET /v1/ui/home
│   │   └── redirect.py   # GET /r/offers/{offerId}
│   ├── services/         # Business logic
│   │   ├── ranking.py    # Top-10 selection
│   │   ├── dedup.py      # SKU matching
│   │   ├── trust.py      # Trust score calculation
│   │   ├── hydration.py  # Lazy merchant URL hydration
│   │   └── serpapi_client.py
│   ├── stores/           # Data access
│   │   ├── postgres.py   # DB session
│   │   └── redis.py      # Cache + locks
│   ├── models/           # SQLAlchemy ORM
│   └── schemas/          # Pydantic schemas
├── tests/
├── Dockerfile
└── pyproject.toml
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DEBUG` | `false` | Enable debug mode |
| `HOST` | `0.0.0.0` | Server host |
| `PORT` | `8080` | Server port |
| `DATABASE_URL` | `postgresql+asyncpg://...` | PostgreSQL connection |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection |
| `CORS_ORIGINS` | `["http://localhost:3000"]` | Allowed CORS origins |
| `AUTO_MIGRATE` | `false` | Run `alembic upgrade head` on start/deploy |
| `SERPAPI_API_KEY` | `` | SerpAPI key (optional; also accepts `SERPAPI_KEY`) |
| `SERPAPI_DEBUG` | `false` | Log full SerpAPI response JSON for debugging |

## Railway Deployment

### Setup

1. Create a new project on Railway
2. Add PostgreSQL plugin
3. Add Redis plugin (optional for now)
4. Create a new service from GitHub repo
5. Set root directory to `services/api`
6. Railway will auto-detect Dockerfile

### Environment Variables (Railway)

Set these in Railway dashboard:

| Variable | Value |
|----------|-------|
| `DATABASE_URL` | `${{Postgres.DATABASE_URL}}` (reference) |
| `REDIS_URL` | `${{Redis.REDIS_URL}}` (reference, optional) |
| `CORS_ORIGINS` | `["https://your-frontend.vercel.app"]` |
| `DEBUG` | `false` |

### Run Migrations

After deployment, run migrations via Railway CLI or shell (or set `AUTO_MIGRATE=true`):

```bash
railway run alembic upgrade head
```

### Seed Data (optional)

```bash
railway run python -m scripts.seed
```

## Development

### Run Tests
```bash
pytest
```

### Format Code
```bash
ruff check --fix .
black .
```

### Type Check
```bash
mypy app
```
