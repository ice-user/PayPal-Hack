# PayPal Hack — API Contracts

This directory contains the JSON schemas and fixtures that define the contract between Person A (frontend/consultant) and Person B (backend/policy gate).

## Schemas

- `SituationRecord.schema.json` — Describes the current dispute spike context. Produced by Person A's Situation Builder, consumed by the Consultant and UI.
- `Recommendation.schema.json` — The Consultant's output (diagnosis, precedents, typed action, confidence, approval tier). Consumed by Person B's Policy Gate.

## Fixtures (3 demo scenarios)

Each fixture conforms to the `SituationRecord` schema and represents one of the three hackathon demo scenarios:

| Fixture | Scenario | Description |
|---------|----------|-------------|
| `situation_A.json` | `one_carrier_delays` | Single carrier (FastShip) concentration around one SKU (Widget-Pro-X1). Dispute rate tripling from baseline. |
| `situation_B.json` | `many_carriers_delays` | Multiple carriers (FastShip + SpeedyPost) across multiple SKUs. Dispute rate quadrupling from baseline. |
| `situation_C.json` | `delivered_orders` | Stable rate near baseline, mixed reasons, no concentration. Minor uptick in one SKU. |

## Usage

1. **Person A** loads a fixture (or builds a `SituationRecord` from the Situation Builder) and passes it to the Consultant LLM step.
2. The Consultant outputs a `Recommendation` validated against `Recommendation.schema.json`.
3. Person B's Policy Gate consumes the Recommendation and decides on approval tier (AUTO / NEEDS_APPROVAL / BLOCKED).
4. The UI displays the situation, precedents, and recommendation with the with/without-precedent toggle.

## Adding New Fixtures

Create a new JSON file in `contracts/fixtures/` that conforms to `SituationRecord.schema.json`. Name it to reflect the scenario (e.g., `situation_D.json`).

## Policy Approval Tiers

| Tier | When Used | Who Approves |
|------|-----------|--------------|
| `AUTO` | Analysis/draft actions only | System, no human needed |
| `NEEDS_APPROVAL` | External actions (submit evidence, message buyer) | One-click human approval |
| `BLOCKED` | Money/claim actions (refund, offer, accept claim) | Explicit human approval required |

## License

See root `LICENSE` for licensing information. No secrets or API keys committed.