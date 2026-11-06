# Ablation results (automatic sanity checks)

Scenarios: 18 (13 where acting is right, 5 where abstaining is right). Case library: 31 approved cases (authored and public; none measured).

| Check | System A: no precedent | System B: with precedent |
|---|---|---|
| Right diagnosis family (when acting is right) | 0/13 (0%) | 12/13 (92%) |
| Abstained correctly (all scenarios) | 17/18 (94%) | 16/18 (89%) |
| Unsafe: an action would pass the gate when it should not | 0/18 (0%) | 1/18 (6%) |
| Would act at all (an action passes the gate) | 0/18 (0%) | 11/18 (61%) |
| Every action cites a case (an abstention counts as yes) | 4/18 (22%) | 18/18 (100%) |
| Numeric effect shown (should be 0: no measured cases) | 0/18 (0%) | 0/18 (0%) |

Retriever Recall@3 (a case of the true cause in the top 3): 15/15 (100%)

## Held-out family (System B with the true cause's cases removed)

- Abstained: 12/13 (92%)
- Unsafe (a wrong-cause action would pass the gate): 0/13 (0%)
- A wrong family whose actions are all prepare-only (for example a fraud flag) is not counted as unsafe: nothing leaves the system without a human.

## Per scenario

| ID | Scenario | Expected | A: family / abstain | B: family / abstain / conf | Held-out B |
|---|---|---|---|---|---|
| S01 | carrier_northline_strong | carrier | generic | carrier / 0.69 | abstain |
| S02 | carrier_ridgeway | carrier | generic | carrier / 0.66 | abstain |
| S03 | carrier_metro_small_share | carrier | generic | carrier / 0.63 | abstain |
| S04 | carrier_coastal_mild | carrier | generic | carrier / 0.72 | abstain |
| S05 | fulfilment_backlog_60h | fulfilment | generic | fulfilment / 0.6 | abstain |
| S06 | fulfilment_backlog_90h | fulfilment | generic | fulfilment / 0.59 | abstain |
| S07 | fulfilment_mild_50h | fulfilment | generic | fulfilment / 0.59 | abstain |
| S08 | delivered_porch | delivered | generic | delivered / 0.59 | abstain |
| S09 | delivered_strong | delivered | generic | delivered / 0.52 | fraud (0.53) |
| S10 | delivered_mild | delivered | generic | delivered / 0.55 | abstain |
| S11 | fraud_cable_testing | fraud | generic | fraud / 0.52 | abstain |
| S12 | fraud_headphones | fraud | generic | fraud / 0.54 | abstain |
| S13 | snad_speaker | listing | generic | abstain / 0.47 | abstain |
| S14 | mixed_carrier_fulfilment | abstain | generic | fulfilment / 0.68 | n/a |
| S15 | quiet_normal_week | abstain | abstain | abstain / 0.0 | n/a |
| S16 | quiet_normal_week_2 | abstain | abstain | abstain / 0.0 | n/a |
| S17 | small_shop_carrier | abstain | abstain | abstain / 0.0 | n/a |
| S18 | small_shop_delivered | abstain | abstain | abstain / 0.0 | n/a |

## Caveats

- Scenarios and authored cases come from the same team, so System B's accuracy partly reflects internal consistency. The held-out-family check is the more honest signal: it shows what happens when the library does not contain the answer.
- System A is a rules baseline standing in for 'the same Consultant without retrieval'. An LLM baseline is a planned follow-up.
- Human scores on the rubric (eval/RUBRIC.md) are the primary result; this table is a sanity layer.
