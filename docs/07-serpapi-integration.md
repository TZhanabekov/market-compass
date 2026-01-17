# SerpAPI integration & cost controls

## Why two endpoints exist
- `google_shopping` returns a list of shopping results and already includes:
  - item price (`extracted_price`)
  - merchant name (`source`)
  - product link (`product_link`)
  - `immersive_product_page_token`
  - helper field `serpapi_immersive_product_api`

- `google_immersive_product` is expensive and returns a single product’s enriched info:
  - `product_results.stores[]` with `link` (direct merchant URL)
  - additional offer details (shipping, total, etc.)

## Primary ingestion: google_shopping

### Minimal fields we use
From each `shopping_results[]` item:
- `position`
- `title`
- `product_id`
- `product_link`
- `source` (merchant name)
- `price`, `extracted_price`
- `rating`, `reviews` (optional trust signals)
- `immersive_product_page_token` (for later hydration)

### Strategy
- Use `google_shopping` to build candidate offers across a country/SKU query.
- Normalize + dedup by Golden SKU.
- Select Top‑10 for UI (and optionally Top‑30 internally).

## Optional: LLM-assisted parsing/matching (GPT‑5‑mini fallback)
LLM is a **separate cost center** from SerpAPI and must follow the same “cost control” philosophy:
- deterministic-first (regex/rules)
- LLM only for ambiguous items
- strict caching + locks

### What the LLM is allowed to do
- classify title as accessory/bundle/contract when heuristics are uncertain
- extract structured attributes (model/storage/color/condition variants)
- choose a Golden SKU **from a constrained candidate list** and return `match_confidence`
- emit small reason codes for explainability/review

### What the LLM must NOT do
- no open web browsing at request time
- no calling SerpAPI immersive in bulk (LLM doesn’t change SerpAPI rules)
- no unbounded/free-form outputs (must be strict JSON validated server-side)

### Caching and locks (LLM)
Recommended keys:
- `llm:parse:{hash(title + condition + merchant + model_hint)}` → parsed JSON (TTL: 30–180d)
- `lock:llm:parse:{same-hash}` → short lock (TTL: 30–120s)

Rationale:
- titles repeat heavily across refresh runs
- prevents thundering herd during ingestion bursts

### Multi-language titles (production reality)
SerpAPI shopping `title` varies by country and may be non-English.

Practical approach:
- Prefer structured SerpAPI fields when available (e.g. `second_hand_condition`) over title heuristics for condition.
- Keep deterministic extraction language-agnostic where possible (e.g. digits + `GB/TB` for storage).
- Maintain small per-language token dictionaries for:
  - colors
  - accessory keywords
  - contract/plan keywords
  - “new/used/refurb” indicators (as secondary signals)
- Use GPT‑5‑mini only for **single-variant** listings where critical attrs are missing; skip LLM on multi-variant enumerations.

## Selective hydration: google_immersive_product

### What we need from immersive
From `product_results.stores[]`:
- `name`
- `link` (direct merchant URL)
- optional: `details_and_offers`, `shipping_extracted`, `extracted_total`

### Budget rules (core requirement)
- Never call immersive for every item.
- Default behavior:
  1) Eager hydrate only Top‑1 (or Top‑3) winners for better UX.
  2) Lazy hydrate on CTA click (`/r/offers/{offerId}`).
  3) Cache the result per token and per offer.

### Caching policy
- Cache immersive JSON by token for 7–30 days (tokens change rarely).
- Cache merchant URL by offer id for 7–30 days.
- Always lock hydration per offer id to prevent thundering herd.

## Deduplication at source level
It’s common to get:
- duplicated merchants
- the same product under slightly different titles
- multiple color/storage variants mixed in

Therefore:
- parse attributes from title/features
- compute `match_confidence`
- only attach offer to SKU if confidence passes threshold
- send low-confidence offers to review queue (optional)

## Rate limiting
Apply rate limits per:
- IP / API key (if internal)
- user session (frontend)
- SerpAPI usage (internal budget):
  - global per-minute cap
  - per-country refresh schedule
