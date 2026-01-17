# Security & reliability

## Secrets
- never commit API keys
- store in Vercel/Railway env vars
- rotate keys regularly

## CORS
- allow only frontend origin(s)
- disallow wildcard in production

## Redirect safety
Redirect endpoint must:
- only redirect to URLs that come from SerpAPI hydration or stored offers
- optionally validate URL scheme (https) and block javascript/data URLs
- include click logging for analytics and fraud detection

## Abuse prevention
- rate limit `/r/offers/{id}` (click endpoint)
- lock hydration per offer id
- global caps for SerpAPI calls (budget enforcement)

## Data quality
- store match confidence
- quarantine low-confidence offers
- maintain merchant allow/block lists

## LLM safety (optional features)
If we introduce an LLM (e.g. GPT‑5‑mini) for parsing/matching/scoring signals:
- Treat LLM output as **untrusted input**:
  - validate strict JSON against a schema
  - clamp numeric ranges (e.g. trust 0..100, confidence 0..1)
  - reject/ignore unknown fields
- Prevent prompt injection:
  - never pass user-provided free text beyond the minimal product fields (title/snippet)
  - never allow the model to call tools or fetch URLs
  - forbid the model from emitting URLs used for redirects
- Data minimization:
  - do not send personal data (normally none in SerpAPI shopping payloads, but enforce anyway)
  - avoid storing raw prompts/responses long-term; prefer hashes + small reason codes
  - if storing raw for debugging, gate behind a debug flag and short retention

## Compliance
- don’t store personal data
- do not fingerprint users
- only store aggregated usage metrics
