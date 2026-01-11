# Product & scope

## What the product is
Market Compass (iPassport) is a **global iPhone price intelligence** product.

Key positioning:
- **Single vertical focus**: iPhone only
- **Decision-first UI**: show Top‑10 deals and the “winner” immediately
- **Execution support**: short, tactical guides (tax-free, airport steps, compatibility caveats)

## What we ship first
1. Golden SKU pages with:
   - Top‑10 leaderboard for that SKU
   - Comparison: local market vs global winner
   - Guide steps and alerts embedded in each deal card
2. Selective direct-offer links (cost controlled):
   - Winner is clickable immediately
   - Other offers get hydrated **on click** or for Top‑N

## What we deliberately avoid in MVP
- Infinite “all offers” list (UI is Top‑10 by design)
- Manual country guides (LLM + whitelist facts pipeline instead)
- “Full marketplace” behaviors (carts, checkouts, etc.)

## User-facing flows (based on current mock)
- Auto-detect location (or manual location modal)
- Select iPhone model (later: select full SKU)
- See:
  - Local price
  - Global winner deal
  - Top‑10 global deals
- Adjust risk slider (min trust score)
- Expand deal card to see:
  - Hardware alert
  - Guide steps
  - CTA: “Claim Arbitrage” (redirect to merchant link)
