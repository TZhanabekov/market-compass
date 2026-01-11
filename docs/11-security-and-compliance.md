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

## Compliance
- don’t store personal data
- do not fingerprint users
- only store aggregated usage metrics
