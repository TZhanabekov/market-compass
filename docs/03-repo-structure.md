# Monorepo structure (pnpm workspaces + Python FastAPI)

## Goal
One GitHub repository, two independent deploy targets:
- **Vercel**: frontend
- **Railway**: backend + workers

## Recommended layout

```
market-compass/
  apps/
    web/                    # Vite/React frontend (current mock)
  services/
    api/                    # Python FastAPI backend
    worker/                 # Optional: scheduled refresh / queues
  packages/
    shared/                 # TS-only shared types for frontend + API schema artifacts
  pnpm-workspace.yaml
  package.json              # pnpm scripts for web + shared
  pyproject.toml            # tooling/lint for python services (optional root-level)
  README.md
```

### Notes
- pnpm workspaces manage `apps/web` and `packages/shared`.
- Python services are not “installed” by pnpm; they use Poetry/uv/pip.
- `packages/shared` can also store generated artifacts:
  - OpenAPI JSON exported from FastAPI (CI step)
  - Zod schemas derived from OpenAPI (optional)

## pnpm workspaces setup
`pnpm-workspace.yaml`:

```yaml
packages:
  - "apps/*"
  - "packages/*"
```

Root scripts should provide:
- `pnpm dev:web`
- `pnpm build:web`
- `pnpm lint`
- `pnpm typecheck`

Python services are run via `uv` / `poetry` / `pip` and `uvicorn`.

## Deploy mapping

### Vercel
- Git repo: `market-compass`
- Root Directory: `apps/web`
- Build: `pnpm install --frozen-lockfile && pnpm build`
- Output: `dist`

### Railway
- Git repo: `market-compass`
- Service Root Directory: `services/api`
- Build: install python deps, run migrations, run `uvicorn`
- Optional second Railway service: `services/worker` (scheduled refresh jobs)
