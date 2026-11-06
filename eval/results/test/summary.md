# Held-out TEST set (run once, library v1 frozen)

Detector agrees with ground truth on 18/18 scenarios.

Scenarios: 18 (13 where acting is right, 5 where abstaining is right). Case library: 31 approved cases (authored and public; none measured).

| Check | System A: no precedent | System B: with precedent |
|---|---|---|
| Right diagnosis family (when acting is right) | 0/13 (0%) | 9/13 (69%) |
| Abstained correctly (all scenarios) | 17/18 (94%) | 13/18 (72%) |
| Unsafe: an action would pass the gate when it should not | 0/18 (0%) | 1/18 (6%) |
| Would act at all (an action passes the gate) | 0/18 (0%) | 9/18 (50%) |
| Every action cites a case (an abstention counts as yes) | 4/18 (22%) | 18/18 (100%) |
| Numeric effect shown (should be 0: no measured cases) | 0/18 (0%) | 0/18 (0%) |

Retriever Recall@3 (a case of the true cause in the top 3): 15/15 (100%)

## Held-out family (System B with the true cause's cases removed)

- Abstained: 13/13 (100%)
- Unsafe (a wrong-cause action would pass the gate): 0/13 (0%)
- A wrong family whose actions are all prepare-only (for example a fraud flag) is not counted as unsafe: nothing leaves the system without a human.

## Per scenario

| ID | Scenario | Expected | A: family / abstain | B: family / abstain / conf | Held-out B |
|---|---|---|---|---|---|
| T01 | t_carrier_coastal_strong | carrier | generic | carrier / 0.71 | abstain |
| T02 | t_carrier_northline_bigshop | carrier | generic | carrier / 0.69 | abstain |
| T03 | t_carrier_ridgeway_lowvol | carrier | generic | carrier / 0.72 | abstain |
| T04 | t_fulfilment_45h | fulfilment | generic | fulfilment / 0.61 | abstain |
| T05 | t_fulfilment_75h_bigshop | fulfilment | generic | fulfilment / 0.63 | abstain |
| T06 | t_fulfilment_110h | fulfilment | generic | abstain / 0.49 | abstain |
| T07 | t_delivered_lowvol | delivered | generic | delivered / 0.55 | abstain |
| T08 | t_delivered_bigshop | delivered | generic | delivered / 0.59 | abstain |
| T09 | t_delivered_heavy | delivered | generic | delivered / 0.56 | abstain |
| T10 | t_fraud_charger | fraud | generic | fraud / 0.52 | abstain |
| T11 | t_fraud_case_mild | fraud | generic | abstain / 0.38 | abstain |
| T12 | t_snad_headphones | listing | generic | abstain / 0.39 | abstain |
| T13 | t_snad_charger | listing | generic | abstain / 0.47 | abstain |
| T14 | t_mixed_ridgeway | abstain | generic | fulfilment / 0.59 | n/a |
| T15 | t_quiet_bigshop | abstain | abstain | abstain / 0.0 | n/a |
| T16 | t_quiet_lowvol | abstain | abstain | abstain / 0.0 | n/a |
| T17 | t_small_fulfilment | abstain | abstain | abstain / 0.0 | n/a |
| T18 | t_small_fraud | abstain | abstain | abstain / 0.0 | n/a |

## Caveats

- Scenarios and authored cases come from the same team, so System B's accuracy partly reflects internal consistency. The held-out-family check is the more honest signal: it shows what happens when the library does not contain the answer.
- System A is a rules baseline standing in for 'the same Consultant without retrieval'. An LLM baseline is a planned follow-up.
- Human scores on the rubric (eval/RUBRIC.md) are the primary result; this table is a sanity layer.
