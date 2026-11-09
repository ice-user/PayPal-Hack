# TechKart evaluation: System A (generic) vs System B (Precedent)

Scenarios: 20. Open item-not-received disputes scored: 452.

| Metric | System A, generic | System B, Precedent |
|---|---|---|
| Recommendation validity (exact spec path) | 0/452 (0%) | 452/452 (100%) |
| Fits the parcel's true state | 173/452 (38%) | 452/452 (100%) |
| Evidence completeness (GPS or signature included) | 0/78 (0%) | 78/78 (100%) |
| Deadline compliance (responds before the deadline without claiming delivery) | 0/44 (0%) | 44/44 (100%) |
| Appropriate abstention (no tracking: no external action) | 0/68 (0%) | 68/68 (100%) |
| Unsupported claims (lower is better) | 211/452 (47%) | 0/452 (0%) |
| Missed a deadline by waiting (lower is better) | 0/44 (0%) | 0/44 (0%) |
| Spike scenarios: right cause | 0/18 (0%) | 6/18 (33%) |
| Quiet scenarios: plan abstains | 2/2 (100%) | 2/2 (100%) |

System B triage actions through the policy gate: {'NEEDS_APPROVAL': 92, 'AUTO': 19}. Refund actions over the $500 cap: 0.

## Per scenario

| Scenario | Disputes | A valid | B valid | A unsupported | B unsupported | B plan |
|---|---|---|---|---|---|---|
| tk01_default_mix | 24 | 0 | 24 | 12 | 0 | carrier |
| tk02_mostly_delivered | 14 | 0 | 14 | 3 | 0 | abstains |
| tk03_mostly_in_transit_short | 30 | 0 | 30 | 17 | 0 | carrier |
| tk04_mostly_in_transit_long | 16 | 0 | 16 | 10 | 0 | carrier |
| tk05_lost_heavy | 19 | 0 | 19 | 13 | 0 | abstains |
| tk06_no_tracking_heavy | 30 | 0 | 30 | 9 | 0 | abstains |
| tk07_old_disputes_tight_deadlines | 19 | 0 | 19 | 11 | 0 | abstains |
| tk08_new_disputes_loose_deadlines | 24 | 0 | 24 | 14 | 0 | abstains |
| tk09_other_carrier_and_product | 29 | 0 | 29 | 14 | 0 | abstains |
| tk10_high_volume | 33 | 0 | 33 | 16 | 0 | abstains |
| tk11_low_volume_strong_spike | 22 | 0 | 22 | 10 | 0 | abstains |
| tk12_documented_deliveries | 29 | 0 | 29 | 6 | 0 | abstains |
| tk13_even_mix | 32 | 0 | 32 | 9 | 0 | abstains |
| tk14_transit_mixed_windows | 20 | 0 | 20 | 12 | 0 | carrier |
| tk15_dock_product_focus | 24 | 0 | 24 | 10 | 0 | abstains |
| tk16_carrier_focus_weaker | 24 | 0 | 24 | 10 | 0 | abstains |
| tk17_parcelway_lost_wave | 23 | 0 | 23 | 15 | 0 | carrier |
| tk18_late_window_transit | 27 | 0 | 27 | 16 | 0 | carrier |
| tk19_quiet_month_no_spike | 3 | 0 | 3 | 0 | 0 | abstains |
| tk20_quiet_high_volume | 10 | 0 | 10 | 4 | 0 | abstains |

## Reading this

- System A is the spec's generic consultant, scripted: it submits tracking on every dispute that has it and offers refunds where there is none. It is not an LLM; a Claude baseline would be a stronger test.
- The same team wrote the dispute cases, the decision paths and this test set, so agreement partly reflects internal consistency. This shows the mechanism works as designed, not real-world win rates.
- Situation-level rows use the existing Consultant; quiet scenarios have no spike, but their open disputes are still triaged.
- API execution success is measured separately on the PayPal sandbox.
