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
3. Controlled LLM fallback only if confidence is low (optional, recommended)

## LLM-assisted parsing & Golden SKU matching (optional, recommended)
Goal: improve attribute extraction, SKU matching, and trust signals **without changing the UI contract** and without introducing per-result LLM cost.

### Core rule: deterministic-first, LLM as fallback
- Always run deterministic extraction (regex + rules) first.
- Call an LLM (e.g. GPT‑5‑mini) **only** for ambiguous or low-confidence items.
- Cache LLM results and use locks to prevent request storms.

### When to call the LLM
Trigger conditions (examples):
- extraction confidence is LOW (or MEDIUM with missing storage/color)
- title looks like accessory/bundle/contract and rule-based filter is unsure
- conflict between `second_hand_condition` and title text
- multiple close Golden SKU candidates exist (e.g. 256GB vs 512GB) and deterministic scoring can’t pick a winner

Hard exclusions (do NOT call the LLM):
- multi-variant listings (one title lists multiple storage/colors, e.g. "256GB/512GB/1TB", "All colors")
  - LLM cannot reliably pick a single SKU from an enumerated listing without additional product-variant context
- obvious contract/plan offers ("with data plan", "monthly payments", "with contract") if the product policy excludes them

Budget constraints:
- cap LLM calls per ingestion run (e.g. <= 10–20% of processed results)
- never call LLM for every SerpAPI shopping result

### Candidate-set matching (LLM chooses from a constrained list)
To avoid hallucinated SKU keys:
- build a small candidate set from DB (by model family + condition, then score by storage/color)
- ask the LLM to select the best candidate **from that list**, and return a `match_confidence` (0..1) + reason codes
- if confidence < threshold, quarantine the offer for review (optional)

### Strict JSON output (schema + validation)
LLM output must be validated (server-side) and treated as untrusted input.
Recommended output fields:
- `is_accessory` / `is_bundle` / `is_contract` (booleans)
- `attrs`: model, storage_gb, color, condition, sim_variant, lock_state, region_variant (nullable where unknown)
- `match`: `sku_key` (chosen from candidates), `match_confidence`, `reason_codes`
- `trust_signals`: text-derived red flags (no external web lookups)

Recommended contract shape (high-level):
- `classification`: is_phone / is_accessory / is_contract / is_multi_variant + confidence + reason codes
- `attrs`: normalized attributes (or null if unknown)
- `match`: `chosen_sku_key` (must be in candidates or null) + `match_confidence` + reason codes

Validation rules (recommended):
- reject unknown fields
- clamp confidences to 0..1
- clamp trust score contributions to 0..100 (if any are returned)
- reject `chosen_sku_key` if not in candidate set

### Storage and explainability
Persist minimal, stable artifacts:
- `match_confidence` on offers (0..1)
- optional: `match_reason_codes` / `trust_reason_codes` (small enum-like strings)
This supports explainability and a review queue, without bloating UI payloads.

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

LLM note (optional):
- LLM can contribute **only** text-derived signals (e.g. accessory/bundle/contract indicators, ambiguous condition),
  but price anomaly should be computed deterministically (distribution/MSRP-based) for stability and auditability.

## Risk slider behavior
Frontend slider maps to `minTrust`.
Backend must:
- apply filter (`trust_score >= minTrust`)
- return:
  - Top‑10 after filtering
  - `matchCount` for UX feedback
- if fewer than 10 matches exist, return what exists (<=10)

## Multi-language titles (production reality)
Shopping results are country-specific; `title` may be in Japanese/German/French/etc.

Design principles:
- deterministic-first extraction should rely on language-agnostic signals where possible (digits + GB/TB, SerpAPI `second_hand_condition`)
- maintain small per-language dictionaries for high-value tokens (colors, "new/used/refurb", accessory keywords, contract keywords)
- use LLM only as a fallback when deterministic extraction is missing critical attributes **and** the listing appears to be single-variant
