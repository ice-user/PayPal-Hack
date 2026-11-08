# Spike 2 result: real public cases

Run 2026-11-07. Files: `cases/public/public_v0.json` (precedents) and
`data/reference/platform_disclosures.json` (context facts, not precedents).

## Verdict: PARTIAL PASS

Pass criterion was "at least three of five cases support meaningfully different
decisions". Five sources were worked; four became cases. They support **two** distinct
decisions, plus one explicit "never do this" rule:

| Source | Became | Decision it supports | Evidence quality |
|---|---|---|---|
| FTC v. Nuvei (2026): 8.5% chargeback rate, volume split across processors | Case p01 | Compliance escalation; splitting volume to dodge monitoring is a red flag | incomplete_report |
| FTC v. BlueSnap (2024): 29-40% of charges disputed as fraud | Case p02 | Fraud pattern: disputes are a symptom of deception, not operations | incomplete_report |
| FTC v. CMS (2020): multiple accounts, sham chargeback-reduction plans | Case p03 | Same as p01: hiding a rate is never a remedy | incomplete_report |
| Shopify merchant thread (2026): contested win rate about 28% to 60% after reason-code-specific evidence | Case p04 | Evidence matched to reason code (fits situation C) | incomplete_report |
| PayPal 10-K 2025 ($1.3B transaction losses, about 0.07% of $1.79T TPV) and Block 10-K 2025 | Reference facts | None: platform-wide totals do not describe a merchant situation or intervention | aggregate_disclosure |

## What we learned
- **No public source gave merchant-level before/after dispute rates.** So there are still
  zero `measured_observational` cases, and the app correctly shows no numeric forecast.
  This is the main data limitation to state in the write-up.
- FTC cases are rich in **numbers about the problem** (rates, counts) but not about a fix.
  They are strong precedents for the fraud and compliance side, and for a gate rule:
  never recommend splitting volume across accounts.
- Merchant self-reports carry obvious **confounders** (case selection, self-reporting);
  p04 records the confound raised in the thread itself.
- 10-K figures are useful **context** (base rates for the pitch), not precedents.
- Public cases have sparse features, so the retriever's coverage penalty keeps them
  below the similarity threshold for the A/B/C demo situations. They surface in fraud
  situations. This is honest behaviour, not a bug.

## Field provenance
Each public case has a `field_provenance` map: `sourced`, `inferred`, `authored` or
`empty` per field. Inferred values (for example p02's fraud share of 0.9 from
"disputed as fraudulent") are flagged there.

## Not done
- EDGAR was not called directly (needs a named User-Agent). Figures came from the
  companies' investor-relations PDFs, with the SEC URL recorded for reference.
- CFPB complaint data not used yet.
