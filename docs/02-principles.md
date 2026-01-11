# Core principles

## 1) Top‑10 only
The UI never requires the user to scroll through a long list.
Backend must:
- return a ranked Top‑10 list
- optionally return a larger pool (Top‑30/Top‑50) **internally** for filtering, but
  the UI payload must remain Top‑10.

## 2) Golden SKU canonicalization
Each canonical page corresponds to exactly one configuration (“Golden SKU”).
The dedup engine matches raw results to Golden SKU(s) deterministically when possible.

## 3) SerpAPI cost control
- `google_shopping` is the **primary** data feed (bulk results, includes price + tokens)
- `google_immersive_product` is **selective**:
  - eager hydration: Top‑1 (and optionally Top‑3)
  - lazy hydration: on CTA click via redirect endpoint
- every expensive call is cached and de-duplicated with locks to avoid storms

## 4) Trust & transparency
- Trust Score is explicit in UI and used in ranking
- “Risk tolerance” is user-controlled (minTrust slider)
- Every deal should be explainable:
  - why it’s ranked
  - why it’s flagged (alerts)
  - how “effective price” was computed (at least in metadata)

## 5) Guides are compact and factual
Guides are not long articles.
They are:
- generated from **Country Facts** (structured, versioned)
- updated from a **whitelist of sources**
- output as 3–7 steps + 0–2 critical alerts

## 6) Stable contracts
Backend must ship a stable response schema tailored to the frontend’s needs:
- one “bootstrap” endpoint for the Home screen
- redirect endpoint for “Claim Arbitrage”
- consistent currency normalization (USD for ranking; local formatting for display)

## 7) Observability and reproducibility
- raw SerpAPI responses are stored (or at least sampled) for auditing
- every ranked list has `last_updated_at` and `data_version`
- guide facts have `facts_version` and `last_verified_at`
