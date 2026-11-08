# Integration update: 8 November 2026

Work extends remote main `ff631eb` in its existing directory structure. The older
local scaffold remains in stash `pre-integration-local-scaffold-2026-11-08`.

## Retrieval

`intelligence/retrieve_hybrid.py` is connected to `backend/precedent/service.py`.
The default combines structured ranks (90%) and lexical TF-IDF narrative ranks
(10%) using reciprocal-rank fusion. Structured similarity remains the policy
score; weak matches cannot displace eligible matches. Only reviewed cases enter
the hybrid retriever. Optional offline SentenceTransformer integration exists;
real model weights and semantic evaluation are still pending.

## Overlapping signals and abstention

The known development failure recommended only a fulfilment remedy for a planted
carrier-plus-fulfilment scenario. Aggregated dispute features concealed uncertainty.
The order feed now checks a separate cohort: parcels dispatched within 48 hours
that nevertheless have not-received disputes without delivery scans. The comparison
uses a one-sided Fisher exact test against promptly dispatched baseline orders.

The review trigger requires an overall anomalous spike, median dispatch >= 36h,
at least 100 current and 500 baseline eligible orders, at least 3 current missing
parcels, and p < 0.10. This deliberately uses a weaker exploratory cutoff than the
0.01 anomaly detector because it can only withhold action and request human review.
It does not establish a second cause or identify a responsible carrier.

These choices were developed after inspecting the known development failure.
That scenario has 3/529 qualifying current orders versus 12/7790 baseline orders
(p approximately 0.0657); the evidence is weak. The guard may miss other mixtures
and may request unnecessary reviews. A fresh evaluation set is needed before
claiming generalization. Frozen held-out results were not rerun or rewritten.

The optional `SituationRecord.features.diagnostic_conflict` object carries cohort
counts, method, cutoff and p-value. Its JSON schema and TypeScript consumer are
updated together. Existing records without this field still validate. Person A
should review this additive contract change before the shared API is frozen.

Both Consultant modes abstain before calling the prose writer. The result has
no executable actions or numerical forecast. The API rejects approval and time
advance; the timeline shows skipped steps. Demo D exposes the known case in both
fixture and API modes. A/B/C retain their original diagnoses and plans.

## Verification

`python eval/compare_retrieval.py` on the 18 known development scenarios:

| Metric | Structured + new guard | Hybrid TF-IDF + new guard |
|---|---:|---:|
| Recall@3, scenarios with a target family | 15/15 | 15/15 |
| Correct family when action is expected | 12/13 | 12/13 |
| Unsafe actions | 0/18 | 0/18 |
| Abstentions | 6/18 | 6/18 |

Before the guard, both modes had 1/18 unsafe actions and 5/18 abstentions. These
are regression results on known authored data, not independent validation.

Tests cover exact statistical calculations, cohort/sample boundaries, irrelevant
dispute reasons, confirmed deliveries, stable baseline rates, pure development
scenarios, both recommendation modes, contract validation, and API action blocking.
The local browser check exercises simulated approval, outcome replay, case review,
and the review-only D scenario. No PayPal calls are made by the isolated demo runner.

## Remaining work

Webhook ingestion now stores verified metadata and audit records atomically,
deduplicates stable event IDs, protects snapshots from stale updates, and exposes
dispute history with contextual real-action links. It never promotes execution
state or treats a generic dispute event as action confirmation. See
[webhook integration](WEBHOOKS.md) for local tests, migration behavior and live
sandbox setup. No live PayPal calls were made for this addition.

- Provision and evaluate a real local embedding model.
- Validate the new review trigger on fresh cases with varied overlapping causes.
- Verify supported seller actions on a fresh sandbox dispute.
- Register and test real webhook delivery and verify real event/action timing.
- Confirm policy thresholds with both collaborators.
- Deploy with persistent storage, complete independent ratings, and record the demo.
