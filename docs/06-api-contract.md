# API contract (FastAPI)

This contract is **UI-driven**: it matches the current frontend screen and components
(Leaderboard, CompareCard, ComparisonModal, DealCard, RiskSlider).

## Base URL
- Production: `https://api.example.com`
- Local: `http://localhost:8080`

## Endpoints

### 1) Health
`GET /health`

Response:
```json
{ "ok": true }
```

### 2) UI bootstrap (Home screen)
`GET /v1/ui/home`

Query params:
- `sku` (string, required) — Golden SKU key (e.g. `iphone-16-pro-256gb-black-new`)
- `home` (string, required) — country code (e.g. `DE`)
- `minTrust` (int, optional, default 80) — 0..100
- `lang` (string, optional, default `en`) — language for guides

Response (`HomeResponse`):
```json
{
  "modelKey": "iphone-16-pro",
  "skuKey": "iphone-16-pro-256gb-black-new",
  "minTrust": 80,
  "homeMarket": {
    "countryCode": "DE",
    "country": "Germany",
    "currency": "EUR",
    "localPriceUsd": 1299,
    "simType": "eSIM + nanoSIM",
    "warranty": "EU consumer warranty (varies by retailer)"
  },
  "globalWinnerOfferId": "c06b0b1f-5f19-4a07-a2f1-6c695403c2d1",
  "leaderboard": {
    "deals": [
      {
        "offerId": "c06b0b1f-5f19-4a07-a2f1-6c695403c2d1",
        "rank": 1,
        "countryCode": "JP",
        "country": "Japan",
        "city": "Tokyo",
        "flag": "🇯🇵",
        "shop": "Demo Store",
        "availability": "In stock",
        "priceUsd": 999,
        "taxRefundValue": 80,
        "finalEffectivePrice": 919,
        "localPrice": "¥149,800",
        "trustScore": 92,
        "simType": "eSIM + nanoSIM",
        "warranty": "Retailer warranty (check details)",
        "restrictionAlert": "Check region model compatibility before buying.",
        "guideSteps": [
          { "icon": "passport", "title": "Bring your passport", "desc": "Tax-free eligibility may require passport verification." },
          { "icon": "receipt", "title": "Keep the receipt", "desc": "You may need receipts for validation/refund." },
          { "icon": "plane", "title": "Validate before departure", "desc": "Follow the airport procedure to confirm export." }
        ]
      }
    ],
    "matchCount": 1,
    "lastUpdatedAt": "2026-01-11T10:00:00.000Z"
  }
}
```

Notes:
- `deals` length is **<= 10**
- `finalEffectivePrice` is the ranking field (USD)
- `localPrice` is a **pre-formatted string** for display
- `guideSteps` are short by design (3–7, max 10)

### 3) Redirect (CTA)
`GET /r/offers/{offerId}`

Behavior:
- If direct merchant URL is already known -> `302` to merchant
- Else -> hydrate via `google_immersive_product` **once**, cache, then redirect
- Fallback: redirect to `product_link` (Google) if merchant URL cannot be obtained

Headers:
- should include cache headers where safe (`Cache-Control: private, max-age=60`)

### 4) Optional: Deal details (if we decide not to embed guide steps in Top‑10)
`GET /v1/deals/{offerId}`
- returns the same deal payload (no ranking fields needed)
- can be used to lazy-load expanded content

## Error format
All errors return:
```json
{
  "error": {
    "code": "string",
    "message": "string",
    "detail": { "any": "json" }
  }
}
```

## OpenAPI
FastAPI must publish OpenAPI at:
- `/openapi.json`
- `/docs` (Swagger UI)
