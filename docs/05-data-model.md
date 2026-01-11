# Data model (Postgres + Redis)

## Postgres tables (logical)

### 1) golden_skus
Represents canonical configurations.

Columns:
- `sku_id` (uuid, pk)
- `sku_key` (text, unique) — stable canonical key
- `model_family` (text) — e.g. "iPhone 16 Pro"
- `storage_gb` (int)
- `color` (text)
- `condition` (text) — new/refurb/used
- `sim_variant` (text, nullable)
- `lock_state` (text, nullable)
- `region_variant` (text, nullable)
- `seo_slug` (text, unique)
- `created_at`, `updated_at`

### 2) merchants
- `merchant_id` (uuid, pk)
- `name` (text)
- `domain` (text, nullable)
- `rating` (numeric, nullable)
- `reviews_count` (int, nullable)
- `is_verified` (bool)
- `is_blacklisted` (bool)
- `created_at`, `updated_at`

### 3) offers
Normalized offers attached to a Golden SKU.

- `offer_id` (uuid, pk)
- `sku_id` (uuid, fk golden_skus)
- `country_code` (char(2))
- `merchant_id` (uuid, fk merchants)
- `source` (text) — "serpapi_google_shopping"
- `source_product_id` (text, nullable)
- `product_link` (text) — Google product link from `google_shopping`
- `immersive_token` (text, nullable) — `immersive_product_page_token`
- `merchant_url` (text, nullable) — direct offer URL (hydrated)
- `title_raw` (text)
- `price_local` (numeric)
- `currency` (char(3))
- `shipping_local` (numeric, nullable)
- `total_local` (numeric, nullable)
- `price_usd` (numeric)
- `shipping_usd` (numeric, nullable)
- `effective_price_usd` (numeric)
- `tax_refund_est_usd` (numeric, nullable)
- `availability` (text, nullable)
- `trust_score` (int) — 0..100
- `match_confidence` (numeric) — 0..1
- `first_seen_at`, `last_seen_at`

### 4) materialized_leaderboards
Optional but strongly recommended for speed.

- `leaderboard_id` (uuid, pk)
- `scope` (text) — "global" | "country"
- `country_code` (char(2), nullable)
- `sku_id` (uuid)
- `computed_at` (timestamp)
- `min_trust_bucket` (int) — 0/20/40/60/80
- `payload_json` (jsonb) — Top‑10 deals and metadata
- `data_version` (text)

### 5) country_sources (whitelist)
- `source_id` (uuid, pk)
- `country_code` (char(2))
- `name` (text)
- `url` (text)
- `source_type` (text) — customs / airport / operator / embassy / etc.
- `is_active` (bool)
- `priority` (int)

### 6) country_facts_versions
Structured facts extracted from whitelist sources.

- `facts_id` (uuid, pk)
- `country_code` (char(2))
- `facts_version` (int)
- `facts_json` (jsonb) — structured schema
- `citations_json` (jsonb) — map field -> source url(s)
- `last_verified_at` (timestamp)
- `status` (text) — fresh/stale/unknown/needs_review

### 7) country_guides_versions
UI-facing guide steps.

- `guide_id` (uuid, pk)
- `country_code` (char(2))
- `facts_version` (int, fk or reference)
- `language` (text) — "en", "de", ...
- `guide_steps_json` (jsonb) — array of steps
- `alerts_json` (jsonb)
- `last_generated_at` (timestamp)

## Redis keys

### SerpAPI caches
- `serp:shopping:{country}:{sku_key}:{page}` -> raw json (TTL: 1–6h)
- `serp:immersive:{token}` -> raw json (TTL: 7–30d)

### Merchant link cache
- `offer:merchant_url:{offer_id}` -> url (TTL: 7–30d)

### Locks (to prevent request storms)
- `lock:hydrate:{offer_id}` (TTL: 30–120s)

### UI payload cache
- `ui:home:{home}:{sku_key}:{minTrustBucket}` -> HomeResponse (TTL: 30–300s)
