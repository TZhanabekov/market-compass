# System architecture

## High-level components

1. **Frontend (Vercel)**
   - Home screen (Top‑10 + Compare + Risk slider)
   - Deal cards (expand for guides + alerts)
   - CTA redirects through backend (never store raw merchant links on the client)

2. **Backend API (FastAPI on Railway)**
   - serves UI-specific endpoints
   - computes comparison values
   - provides redirect endpoint with lazy hydration
   - enforces rate limits and caching

3. **Data layer**
   - Postgres: normalized entities (SKU, offers, merchants, prices, country facts, guide versions)
   - Redis: caching + locks (SerpAPI responses, hydration results, redirect cache)

4. **Ingestion & ranking pipeline**
   - fetch: SerpAPI `google_shopping`
   - normalize & dedup: match to Golden SKU(s)
   - rank: compute effective price and choose Top‑10
   - enrich: selective `google_immersive_product` (Top‑N or on-click)

5. **Guides pipeline (LLM + whitelist sources)**
   - crawl/refresh country sources on schedule
   - extract facts to structured JSON with citations
   - compose UI steps (3–7) + alerts
   - publish to `country_guides` table

## Request flows

### A) Home screen load
```mermaid
sequenceDiagram
  autonumber
  participant U as User (Web)
  participant W as Vercel Web
  participant A as FastAPI
  participant R as Redis
  participant P as Postgres

  U->>W: Open home
  W->>A: GET /v1/ui/home?sku=...&home=DE&minTrust=80
  A->>R: Check cached Top‑10 for (home, sku, minTrust_bucket)
  alt Cache hit
    R-->>A: Top‑10 payload
  else Cache miss
    A->>P: Read materialized Top‑N offers for sku (global + home)
    P-->>A: offers
    A->>A: Rank + filter + compute comparison summary
    A->>R: Store cache (short TTL)
  end
  A-->>W: HomeResponse (Top‑10 + winner + local market)
  W-->>U: Render UI
```

### B) CTA “Claim Arbitrage” (lazy hydration)
```mermaid
sequenceDiagram
  autonumber
  participant U as User (Web)
  participant A as FastAPI
  participant R as Redis
  participant P as Postgres
  participant S as SerpAPI
  participant M as Merchant site

  U->>A: GET /r/offers/{offer_id}
  A->>P: lookup offer_id -> merchant_url?
  alt merchant_url exists
    A-->>U: 302 redirect merchant_url
  else merchant_url missing
    A->>R: acquire lock offer_id (prevent storms)
    A->>R: check cached merchant_url by token
    alt token cached
      R-->>A: merchant_url
    else no cache
      A->>S: google_immersive_product(token)
      S-->>A: stores[].link
      A->>P: persist merchant_url
      A->>R: cache merchant_url (long TTL)
    end
    A-->>U: 302 redirect merchant_url (or fallback)
  end
  U->>M: Navigate to merchant offer
```

## Modules (backend)

- `api.routes.ui`: UI bootstrap endpoints
- `api.routes.redirect`: redirect + lazy hydration
- `services.serpapi`: SerpAPI clients and request budgeting
- `services.normalize`: attribute extraction, golden SKU matching
- `services.rank`: effective price, trust weighting, Top‑10 selection
- `services.guides`: country facts retrieval + LLM composition
- `stores.postgres`: repositories / ORM models
- `stores.redis`: cache + locks + TTL policy
- `workers.refresh`: scheduled refresh jobs (prices + guides)
