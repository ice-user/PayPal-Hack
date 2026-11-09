# TechKart test environment (delivery failure crisis)

This is the demo's testing environment, built from the team's spec
`PRECEDENT_Demo_Case_Delivery_Failure.md` (kept outside the repo). It adds one layer to
MediateAI: **dispute-level triage**. The situation level still diagnoses the cause of a
spike. The new layer decides what to do with each open dispute, based on the parcel's
real shipment state and the dispute's response deadline.

Everything here is synthetic and labelled. TechKart is fictional.

## The merchant

| Metric (spec) | Value |
|---|---|
| Orders | about 160 a day (4,800 a month) |
| Average order | about $85 |
| Dispute rate | 0.5% normal, 2.5% in the 7-day window |
| Disputes on Carrier X | about 65% of the spike |
| Disputes on one product | about 45% of the spike |

Generator: `backend/precedent/techkart.py`. It produces orders (consumed unchanged by the
Situation Builder) plus one record per open item-not-received dispute.

## What each dispute carries

| Field | Meaning |
|---|---|
| `shipment_status` | `delivered`, `in_transit`, `lost` (carrier confirmed) or `unknown` (no tracking) |
| `proof` | strongest delivery proof: `none`, `tracking`, `confirmation`, `gps`, `signature` |
| `expected_delivery` | carrier's estimate, in-transit parcels only |
| `response_due` | seller response deadline. Synthetic: opened + 10 days (an assumption, not a PayPal rule) |
| `amount` | order value |

## Decision paths (from the spec)

| Shipment state | Appropriate response | Action type and gate tier |
|---|---|---|
| Delivered with confirmation | File proof of fulfilment | PROVIDE_EVIDENCE, external |
| Delivered with GPS or signature | Same, and include that documentation | PROVIDE_EVIDENCE, external |
| In transit, arrives before the deadline | Message the buyer with the real delivery window; re-check before the deadline | SEND_MESSAGE, external |
| In transit, deadline comes first | Respond before the deadline with truthful shipment proof and the agreed window; never claim delivery | PROVIDE_EVIDENCE (in-transit note), external |
| Confirmed lost | Resolve with the buyer (refund) and claim from the carrier | ACCEPT_CLAIM, money (approval, $500 cap) |
| No tracking information | Gather records first; take no external action | FLAG_ONLY, prepare |

## How precedent decides (case-based reasoning at the dispute level)

`dispute_cases/dispute_cases_v0.json` holds authored dispute-level cases (labelled
`authored`, `illustrative`). Each case records:
- a dispute fingerprint (status, proof level, whether the deadline comes before delivery,
  days to the deadline, amount);
- the response taken;
- whether that response was appropriate or **backfired**.

`intelligence/triage.py` retrieves the closest cases for each open dispute, using the same
similarity form as the situation level. Only appropriate cases vote for a response;
backfired cases are shown as warnings ("what not to do"). This is the "outcome-aware"
part of the spec.

Disputes with the same chosen response are grouped into one action. The action lists:
- the dispute IDs;
- the total amount;
- the earliest deadline;
- the cases it cites.

The policy gate treats these cases as supporting precedent, like situation-level cases.

## The comparison (spec section 4)

- **System A, generic consultant:** no retrieval. It does what the spec describes: submit
  tracking numbers on every dispute that has one, message buyers, and offer refunds where
  there is no tracking. It does not look at shipment state or deadlines. It is scripted,
  because no LLM key is configured. A Claude-based generic baseline can replace it later
  for a stronger comparison.
- **System B, MediateAI:** situation diagnosis plus dispute-level triage by retrieval.

Both get the same orders, the same disputes, the same action list and the same policy gate.

## Evaluation (spec section 7)

`eval/run_techkart.py` scores both systems on the pre-registered set in
`backend/precedent/techkart.py` (`TK_TEST`). Every dispute's correct path comes from
the generator's ground truth.

| Metric | Scored as |
|---|---|
| Shipment-state handling | share of disputes whose response fits their true state |
| Evidence completeness | delivered with GPS or signature: is that documentation included |
| Recommendation validity | response equals the spec's appropriate path |
| Unsupported claims | any proof-of-fulfilment filed for a parcel that was not delivered, or any delivery claim |
| Deadline compliance | in transit with the deadline first: does it respond before the deadline |
| Appropriate abstention | no tracking: no external action |
| API execution success | measured separately on the sandbox, not by this script |

The test set was written and committed before either system was run on it, and it is
separate from the frozen 9/13 situation-level result.

**Limitation:** the same team wrote the dispute cases, the decision paths and the test
set. Agreement partly reflects internal consistency. This shows the mechanism works as
designed. It does not show real-world win rates.
