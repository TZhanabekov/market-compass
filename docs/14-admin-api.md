# Admin API (`/v1/admin/*`) — endpoint documentation

This document describes the current admin endpoints exposed by the FastAPI backend (`services/api`).

> **Security note**: as of today these endpoints are intended for internal use. Production should require an admin token (see `docs/13-admin-console.md`).

## Base URL

- Local: `http://localhost:8080`
- Production (Railway): use your Railway backend URL

Examples below assume:

```bash
export API_BASE_URL="http://localhost:8080"
```

---

## Ingestion

### `POST /v1/admin/ingest`

Trigger ingestion for a specific Golden SKU + country. This calls SerpAPI, upserts `raw_offers`, and writes matching offers into `offers`.

**Request body**

- `sku_key` (string, required)
- `country_code` (string, required)
- `min_confidence` (string, optional): `"high" | "medium" | "low"` (default `"medium"`)
- `skip_low_confidence` (bool, optional) (default `true`)
- `update_existing` (bool, optional) (default `true`)

**Example**

```bash
curl -sS "$API_BASE_URL/v1/admin/ingest" \
  -H "Content-Type: application/json" \
  -d '{
    "sku_key": "iphone-16-pro-256gb-black-new",
    "country_code": "JP",
    "min_confidence": "medium",
    "skip_low_confidence": true,
    "update_existing": true
  }'
```

**Example response**

```json
{
  "success": true,
  "stats": {
    "query": "iPhone 16 Pro 256GB",
    "country_code": "JP",
    "total_results": 50,
    "filtered_accessories": 10,
    "low_confidence": 5,
    "no_sku_match": 25,
    "duplicates": 3,
    "new_offers": 7,
    "updated_offers": 0,
    "errors": 0
  }
}
```

**Errors**
- `400`: unsupported `country_code`
- `500`: ingestion failed

---

### `GET /v1/admin/ingest/countries`

List supported ingestion countries.

**Example**

```bash
curl -sS "$API_BASE_URL/v1/admin/ingest/countries"
```

**Example response**

```json
{
  "countries": ["JP", "US", "HK", "AE", "DE", "GB", "FR", "SG", "KR", "AU", "CA"],
  "default": "US"
}
```

---

## Reconcile (raw_offers → offers)

### `POST /v1/admin/reconcile`

Promote eligible `raw_offers` into `offers`. By default it should be run as a dry-run (`dry_run=true`) and then rerun with `dry_run=false` when you’re confident.

**Request body**

- `limit` (int, optional) (default `500`, max `5000`)
- `dry_run` (bool, optional) (default `true`)
- `country_code` (string, optional) (filters scan)

**Example**

```bash
curl -sS "$API_BASE_URL/v1/admin/reconcile" \
  -H "Content-Type: application/json" \
  -d '{
    "limit": 500,
    "dry_run": true,
    "country_code": "JP"
  }'
```

**Example response**

```json
{
  "success": true,
  "run_id": "2a2b88a3-9d41-4b4a-a9d7-0d2c1b33c2b7",
  "dry_run": true,
  "country_code": "JP",
  "stats": {
    "scanned": 500,
    "skipped_multi_variant": 3,
    "skipped_contract": 12,
    "skipped_missing_attrs": 25,
    "skipped_no_sku": 90,
    "skipped_fx": 0,
    "dedup_conflict": 1,
    "matched_existing_offer": 40,
    "created_offers": 45,
    "updated_raw_matches": 85,
    "llm_budget": 100,
    "llm_external_calls": 0,
    "llm_reused": 0,
    "llm_skipped_budget": 0
  },
  "debug": {
    "created_offer_ids": ["..."],
    "matched_raw_offer_ids": ["..."],
    "sample_reason_codes": ["DETERMINISTIC_SKU_MATCH", "SKIP_CONTRACT"]
  }
}
```

**Errors**
- `500`: reconciliation failed

---

## Raw offers explain

### `GET /v1/admin/raw-offers/{raw_offer_ref}`

Explain how a `raw_offers` row would be parsed/matched. `raw_offer_ref` can be either:
- numeric DB `id` (e.g. `123`)
- `raw_offer_id` UUID (string)

Query parameters:
- `include_candidates` (bool, default `false`)

**Example**

```bash
curl -sS "$API_BASE_URL/v1/admin/raw-offers/123?include_candidates=true"
```

**Example response**

```json
{
  "rawOffer": {
    "id": 123,
    "rawOfferId": "c2d4a1c5-8c74-4b9b-9a6b-7b0c2c0f9b5d",
    "source": "serpapi_google_shopping",
    "sourceProductId": "1234567890",
    "countryCode": "JP",
    "titleRaw": "Apple iPhone 16 Pro 256GB ...",
    "merchantName": "Example Store",
    "secondHandCondition": null,
    "priceLocal": 149800.0,
    "currency": "JPY",
    "matchedSkuId": null,
    "matchConfidence": null,
    "matchReasonCodes": ["SKU_NOT_IN_CATALOG"]
  },
  "deterministic": {
    "extractedAttrs": {
      "model": "iphone-16-pro",
      "storage": "256gb",
      "color": "black"
    },
    "confidence": "high",
    "normalizedCondition": "new",
    "computedSkuKey": "iphone-16-pro-256gb-black-new"
  },
  "catalog": {
    "computedSkuKeyExists": true
  },
  "llm": {
    "enabled": false,
    "attempted": false,
    "chosenSkuKey": null,
    "matchConfidence": null,
    "candidatesCount": null,
    "candidatesFingerprint": null,
    "wouldCallNow": false
  },
  "debug": {
    "flags": {
      "is_contract": false,
      "is_multi_variant": false,
      "condition_hint": null,
      "condition_hint_phrases": []
    },
    "parsedAttrsSnapshot": {},
    "candidates": ["..."]
  }
}
```

**Errors**
- `404`: RawOffer not found

---

## Golden SKUs

### `GET /v1/admin/skus`

List Golden SKUs.

Query parameters:
- `limit` (int, default `50`, max `100`)

**Example**

```bash
curl -sS "$API_BASE_URL/v1/admin/skus?limit=10"
```

**Example response**

```json
{
  "count": 2,
  "skus": [
    {
      "sku_key": "iphone-16-pro-256gb-black-new",
      "model": "iphone-16-pro",
      "storage": "256gb",
      "color": "black",
      "display_name": "Iphone 16 Pro 256GB Black"
    }
  ]
}
```

---

### `GET /v1/admin/skus/{sku_key}`

Get details for a single Golden SKU.

**Example**

```bash
curl -sS "$API_BASE_URL/v1/admin/skus/iphone-16-pro-256gb-black-new"
```

**Example response**

```json
{
  "sku_key": "iphone-16-pro-256gb-black-new",
  "model": "iphone-16-pro",
  "storage": "256gb",
  "color": "black",
  "condition": "new",
  "display_name": "Iphone 16 Pro 256GB Black",
  "msrp_usd": 999.0,
  "created_at": "2026-01-17T00:00:00Z"
}
```

**Errors**
- `404`: Golden SKU not found

---

### `POST /v1/admin/skus`

Create a Golden SKU.

**Request body**

- `model` (string, required) e.g. `"iphone-16-pro"`
- `storage` (string, required) e.g. `"256gb"`
- `color` (string, required) e.g. `"black"`
- `condition` (string, optional) `"new" | "refurbished" | "used"` (default `"new"`)
- optional variant fields: `sim_variant`, `lock_state`, `region_variant`
- optional: `display_name`, `msrp_usd`

**Example**

```bash
curl -sS "$API_BASE_URL/v1/admin/skus" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "iphone-17-pro",
    "storage": "256gb",
    "color": "black",
    "condition": "new",
    "msrp_usd": 999
  }'
```

**Example response**

```json
{
  "success": true,
  "sku_key": "iphone-17-pro-256gb-black-new",
  "message": "Golden SKU created: iphone-17-pro-256gb-black-new"
}
```

---

## Debug endpoints

### `GET /v1/admin/debug/serpapi`

List saved SerpAPI debug response files (only created when `SERPAPI_DEBUG=true`).

**Example**

```bash
curl -sS "$API_BASE_URL/v1/admin/debug/serpapi?limit=10"
```

**Example response**

```json
{
  "count": 1,
  "files": [
    {
      "filename": "shopping_20260117_120000_jp_iphone-16-pro.json",
      "created_at": "2026-01-17T12:00:00Z",
      "size_bytes": 12345
    }
  ]
}
```

---

### `GET /v1/admin/debug/serpapi/{filename}`

Fetch the full JSON content of a saved SerpAPI debug file.

**Example**

```bash
curl -sS "$API_BASE_URL/v1/admin/debug/serpapi/shopping_20260117_120000_jp_iphone-16-pro.json"
```

**Example response**
- Full SerpAPI JSON payload (large)

---

### `GET /v1/admin/debug/fx`

Sanitized OpenExchangeRates debug snapshot.

**Example**

```bash
curl -sS "$API_BASE_URL/v1/admin/debug/fx"
```

**Example response**

```json
{
  "ok": true,
  "base": "USD",
  "timestamp": 1700000000,
  "rates_count": 170,
  "eur_raw": 0.92,
  "eur_parsed": 0.92,
  "sample_rate_keys": ["AED", "AUD", "CAD"],
  "error_payload": null
}
```

---

### `GET /v1/admin/debug/llm`

Sanitized LLM config snapshot (does not reveal secrets).

**Example**

```bash
curl -sS "$API_BASE_URL/v1/admin/debug/llm"
```

**Example response**

```json
{
  "ok": true,
  "llm_enabled": false,
  "openai_key_set": false,
  "openai_base_url_host": "api.openai.com",
  "openai_model_parse": "gpt-5-mini",
  "llm_max_calls_per_reconcile": 50,
  "llm_max_fraction_per_reconcile": 0.2
}
```

---

## Pattern phrases (contract + condition)

Phrases are matched as **literal substrings** against `title` and also `product_link` (host/path/query hint).

Kinds:
- `contract`
- `condition_new`
- `condition_used`
- `condition_refurbished`

### `GET /v1/admin/patterns`

List all pattern phrases (enabled and disabled).

**Example**

```bash
curl -sS "$API_BASE_URL/v1/admin/patterns"
```

**Example response**

```json
{
  "ok": true,
  "kinds": ["contract", "condition_new", "condition_used", "condition_refurbished"],
  "patterns": [
    {
      "id": 1,
      "kind": "contract",
      "phrase": "with contract",
      "enabled": true,
      "source": "manual",
      "notes": null
    }
  ]
}
```

---

### `POST /v1/admin/patterns`

Create or update (upsert) a phrase by `(kind, phrase)`.

**Example**

```bash
curl -sS "$API_BASE_URL/v1/admin/patterns" \
  -H "Content-Type: application/json" \
  -d '{
    "kind": "contract",
    "phrase": "with installments",
    "enabled": true,
    "source": "manual",
    "notes": "common EN wording"
  }'
```

**Example response**

```json
{
  "ok": true,
  "pattern": {
    "id": 12,
    "kind": "contract",
    "phrase": "with installments",
    "enabled": true,
    "source": "manual",
    "notes": "common EN wording"
  }
}
```

**Errors**
- `400`: unsupported `kind` or invalid `phrase`

---

### `DELETE /v1/admin/patterns/{pattern_id}`

Soft-disable a phrase (sets `enabled=false`).

**Example**

```bash
curl -sS -X DELETE "$API_BASE_URL/v1/admin/patterns/12"
```

**Example response**

```json
{ "ok": true }
```

**Errors**
- `404`: pattern not found

---

## LLM suggestions for patterns

### `POST /v1/admin/patterns/suggest`

Read a recent sample of `raw_offers` (title + product_link) and ask the LLM to propose phrases to add for:
- contract detection
- condition hints (new/used/refurbished)

**Requirements**
- `LLM_ENABLED=true`
- `OPENAI_API_KEY` set

**Operational notes**
- Batches are executed with **bounded parallelism** (to reduce wall time without spamming OpenAI).
- Tune concurrency via `PATTERN_SUGGEST_MAX_CONCURRENCY` (default `2`).
- The service logs OpenAI `x-ratelimit-*` headers for each call so you can see real limits in runtime logs.

**Request body**
- `sample_limit` (int, default `2000`, max `2000`)
- `llm_batches` (int, default `3`, max `4`)
- `items_per_batch` (int, default `80`, max `80`)
- `force_refresh` (bool, default `false`) — bypass Redis cache and force LLM calls

**Example**

```bash
curl -sS "$API_BASE_URL/v1/admin/patterns/suggest" \
  -H "Content-Type: application/json" \
  -d '{
    "sample_limit": 2000,
    "llm_batches": 3,
    "items_per_batch": 80,
    "force_refresh": true
  }'
```

**Example response**

```json
{
  "ok": true,
  "cached": false,
  "llm_calls": 3,
  "llm_successful_calls": 2,
  "sample_size": 2000,
  "errors": ["LLM upstream HTTP 502"],
  "suggestions": {
    "contract": [
      {
        "phrase": "monthly payments",
        "llm_confidence": 0.86,
        "match_count": 42,
        "examples": [
          {
            "title": "iphone 16 pro ... monthly payments ...",
            "link": "example.com/path?param=..."
          }
        ]
      }
    ],
    "condition_new": [],
    "condition_used": [],
    "condition_refurbished": []
  }
}
```

### `GET /v1/admin/patterns/suggestions`

List persisted suggestions (stored from previous `patterns/suggest` runs), including match frequency.

Query parameters:
- `kind` (optional)
- `limit` (default `100`, max `500`)
- `min_match_count` (default `1`)

**Example**

```bash
curl -sS "$API_BASE_URL/v1/admin/patterns/suggestions?kind=contract&limit=50&min_match_count=2"
```

**Example response**

```json
{
  "ok": true,
  "count": 2,
  "suggestions": [
    {
      "id": 10,
      "kind": "contract",
      "phrase": "monthly payments",
      "match_count_last": 42,
      "sample_size_last": 2000,
      "match_count_max": 42,
        "llm_confidence_last": 0.86,
        "llm_confidence_max": 0.86,
      "applied": false,
      "last_run_id": "b61b0c0d9f8b4c6a9a3d",
      "last_seen_at": "2026-01-18T08:00:00+00:00"
    }
  ]
}
```

**Errors**
- `400`: LLM not enabled/configured OR another suggest run is already running

