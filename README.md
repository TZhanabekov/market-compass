# Market Compass (iPassport) — Developer Documentation

This documentation is written to align **backend behavior with the current frontend mock** (Vite/React + shadcn/ui) and the product constraints discussed in chat:

- **Canonical page = Golden SKU** (configuration-level SKU)
- **UI shows Top‑10 only** (no infinite list)
- **SerpAPI cost control**: `google_shopping` is the primary feed; `google_immersive_product` is **selective** (Top‑N / on-click hydration)
- **Comparison + Guides**: comparison is computed for the same Golden SKU; guides are generated via LLM from a **whitelist of sources**, with versioning and freshness control
- **Frontend on Vercel** and **Backend on Railway** deployed from a single GitHub **monorepo**
- **Backend language**: **Python + FastAPI**

> Date of this doc snapshot: 2026-01-11

## Quick navigation

- [Product & scope](docs/01-product-overview.md)
- [Core principles](docs/02-principles.md)
- [Monorepo layout (pnpm workspaces + Python FastAPI)](docs/03-repo-structure.md)
- [System architecture](docs/04-system-architecture.md)
- [Data model (Postgres + Redis)](docs/05-data-model.md)
- [API contract for the current UI](docs/06-api-contract.md)
- [SerpAPI integration & cost controls](docs/07-serpapi-integration.md)
- [Deduplication & ranking](docs/08-ranking-and-dedup.md)
- [Comparison & Guides (LLM + whitelist sources)](docs/09-comparison-and-guides.md)
- [Operations: local dev, deploy, env](docs/10-operations-and-deploy.md)
- [Security & reliability](docs/11-security-and-compliance.md)
- [Roadmap](docs/12-roadmap.md)

## Folder map

```
docs/
  00-glossary.md
  01-product-overview.md
  02-principles.md
  03-repo-structure.md
  04-system-architecture.md
  05-data-model.md
  06-api-contract.md
  07-serpapi-integration.md
  08-ranking-and-dedup.md
  09-comparison-and-guides.md
  10-operations-and-deploy.md
  11-security-and-compliance.md
  12-roadmap.md
```
