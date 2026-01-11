# Roadmap

## Phase 1 — Wire mock to real API
- implement `/v1/ui/home` with real Top‑10 payload
- implement `/r/offers/{offerId}` with lazy hydration and caching
- implement basic SKU catalog (Golden SKU)

## Phase 2 — SerpAPI ingestion + dedup
- scheduled `google_shopping` ingestion
- attribute extraction + SKU matching
- trust score baseline + anomaly detection
- materialized leaderboards

## Phase 3 — Guides pipeline (LLM + whitelist)
- country_sources whitelist management
- facts extraction with citations + versioning
- UI guide composition
- multi-language support

## Phase 4 — SEO scale
- SKU x country pages (programmatic)
- structured data (Product + AggregateOffer)
- hreflang and localization

## Phase 5 — Admin tools
- review queue for low-confidence matches
- merchant management (verified/blacklist)
- guide source auditing
