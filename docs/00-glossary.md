# Glossary

## Golden SKU
A **canonical iPhone configuration** that uniquely identifies a sellable unit:
`model + storage + color + condition + (optional) sim_variant + lock_state + region_variant`.

A page in the product is built around **one Golden SKU**.

## Offer
A merchant listing for a Golden SKU (or a candidate offer to be matched to a Golden SKU).
An offer contains price, currency, merchant identity, availability, trust signals, and deep link.

## Top‑10 leaderboard
The UI displays **exactly up to 10** best offers per context (global, country, or filtered by risk).

## Effective price
A computed price used for ranking:
`effective = item_price + shipping - tax_refund_estimate - other_known_credits + known_fees`.

## Trust Score
A 0–100 score used both for ranking and filtering (risk slider):
- merchant reputation signals
- anomaly detection (too-cheap)
- reviews count/rating when available
- internal allow/block lists

## Hydration
Fetching additional data for an offer/product:
- primary feed: SerpAPI `google_shopping`
- selective enrichment: SerpAPI `google_immersive_product` (mainly for **direct merchant link**)

## Country Facts
Structured, versioned facts about buying and tax-free/refund procedures for a country,
maintained via a whitelist-source retrieval pipeline.

## Guide Steps
A compact UI representation (3–7 steps) generated from Country Facts and SKU caveats.
