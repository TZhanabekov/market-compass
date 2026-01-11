# Deduplication & ranking

## Canonical key (SKU key)
A stable `sku_key` is computed from normalized attributes.

Recommended fields:
- model_family (e.g. "iPhone 16 Pro")
- storage_gb
- color
- condition
- sim_variant (optional but recommended)
- lock_state (unlocked/locked)
- region_variant (optional)

Example SKU key:
`iphone-16-pro-512gb-black-new-unlocked`

## Attribute extraction (priority)
1. Deterministic extraction from structured sources (when present)
2. Regex extraction from title/snippet
3. Controlled LLM fallback only if confidence is low

## Offer deduplication within a leaderboard
Even inside one SKU, multiple results can be clones:
- same merchant, same price, same link
- same merchant with tiny variations in title

Dedup key:
- `(merchant_id, extracted_price, currency, availability)` plus url hash if present

## Effective price
Compute:
- USD conversion at ingestion time (store exchange_rate used)
- `effective_price_usd = price_usd + shipping_usd - tax_refund_est_usd - known_credits + known_fees`

If any component is unknown:
- set it to 0
- set `effective_price_metadata` flags (unknown_refund, unknown_shipping)

## Ranking rules
Sort by:
1) `effective_price_usd` ascending
2) `trust_score` descending
3) `availability` (in stock first)
4) tie-breaker: reviews_count descending

## Trust score (0–100)
Signals:
- merchant allow/block list
- rating & reviews count (if present)
- price anomaly vs median for that SKU/country
- historical consistency (optional)
- “too new / too few signals” penalty

## Risk slider behavior
Frontend slider maps to `minTrust`.
Backend must:
- apply filter (`trust_score >= minTrust`)
- return:
  - Top‑10 after filtering
  - `matchCount` for UX feedback
- if fewer than 10 matches exist, return what exists (<=10)
