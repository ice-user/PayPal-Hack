# Handoff: Person B (backend and retrieval ML)

Read first: `docs/BRIEF.md` (decisions and rules), then `docs/DESIGN.md` (sections
2, 3, 5, 7, 7a, 8, 9). This file is your task list.

## 1. The product in three sentences

Precedent is a web dashboard for PayPal merchants. It detects a dispute spike, finds
similar past cases, explains why, proposes typed actions, and, after policy checks
and a human click, executes them through the PayPal Sandbox. It then records the
outcome as a new case. The demo merchant and its orders are synthetic; PayPal
disputes and actions are real in the sandbox wherever Spike 1 confirms they work.

## 2. You own

1. PayPal sandbox setup, adapter and webhooks (Spike 1 is yours).
2. Policy Gate (three tiers), Executor, audit log.
3. API layer, database, hosting, README, licence.
4. The synthetic order and fulfilment generator and the Situation Builder.
5. The Retriever and the Outcome Tracker (simulated clock).
6. Policy and execution tests, and the Recall@3 harness.

Person A owns the frontend, case library and schema, the Consultant (LLM step), the
ablation, and the demo script and recording.

## 3. Do these in order

1. **Contracts and fixtures (first hours, with Person A).** Agree the
   `SituationRecord` and `Recommendation` shapes in `docs/DESIGN.md` section 3.
   Schemas and fixtures live in `/contracts`.
2. **Spike 1 (about 1 to 2 hours).**
   1. Developer account; sandbox business and buyer accounts; REST app (note client
      ID and secret); confirm the Disputes setup and scopes.
   2. Make a sandbox purchase from the buyer to the business.
   3. Create a dispute through the sandbox-only endpoint (`DISPUTE_CREATE` scope,
      buyer-side setup, `PayPal-Auth-Assertion` header).
   4. Read it back and inspect its status and allowed actions.
   5. Try the seller actions it allows: provide evidence, send message, make offer,
      accept claim. Note lifecycle limits and funds needed.
   6. If time permits: sandbox status update or settle, and a webhook with signature
      verification.
   7. Report exact working calls, setup, errors and limits. An endpoint in the docs
      is not proof our app can use it. Docs in `docs/DESIGN.md` section 7a.
   **Pass:** a dispute is created and at least one seller action works. **If it
   fails:** drive the adapter from simulated dispute events through the same
   interface, and keep the limitation visible.
3. **Mock API from fixtures** so Person A can build the UI (FastAPI with auto docs).
4. **PayPal adapter and webhook receiver** with signature verification.
5. **Order and fulfilment generator** (SKU, carrier, ship and delivery times,
   delays) producing the three demo situations (one carrier / many carriers with
   delays / delivered orders). It also gives ground truth for the detector.
6. **Situation Builder** (section 5), then **Retriever** (section 6).
7. **Policy Gate, Executor, audit log** (sections 3 and 4 below).
8. **Outcome Tracker** with a simulated time-advance control, labelled simulated.
9. **Hosting, README, licence, tests**, then swap the mock API for the real one.

## 4. Policy Gate and Executor

- **Tiers:** prepare-only (drafts, analysis) is AUTO; external actions (submit
  evidence, message buyer) need one-click approval; money or claim actions (refund,
  offer, accept claim) need explicit approval and are BLOCKED above a hard cap.
- **Also checked:** action type in the tenant allowlist; at least `k_min`
  precedents above the similarity threshold; no abstain; confidence floor; rate
  limit on actions per window.
- Deterministic: same input, same decision. Log every decision with the rules that
  fired.
- **Executor state machine:** PROPOSED, GATED, AWAITING_APPROVAL, EXECUTING,
  SUCCEEDED, FAILED, CANCELLED. Idempotency key per action. Re-check dispute state
  before executing. Confirm through PayPal's response and webhook, never from the
  client.
- The LLM only proposes typed actions from a fixed enum; it never builds a PayPal
  call.

## 5. Situation Builder

Compare the 7-day dispute rate with the merchant's 30-day baseline using a binomial
test and Wilson confidence intervals; flag an anomaly only above a minimum sample
size. Features from the order feed: carrier and SKU concentration, number of
carriers elevated, fulfilment delay, share of disputed orders with confirmed
delivery, median days since transaction. Output a `SituationRecord`.

## 6. Retriever and effect computation

- Hybrid: weighted distance over normalised structured features, plus text
  embedding of the narrative, fused by reciprocal rank, plus a modest boost for
  cases with measured outcomes.
- Return `matched_on` and `differs_on` for each case.
- Compute `predicted_effect` and `counterfactual` **only from
  `measured_observational` cases**, with `n_measured_cases`. If fewer than two
  matching cases are measured, omit the numbers and pass only qualitative playbook
  notes. The UI never shows an effect that was not computed this way.
- Corpus is small (hundreds at most): in-memory vectors are fine, SQLite storage.

## 7. API for the frontend (proposed; agree with Person A, then freeze)

- `GET /api/merchants/{id}/situation`
- `GET /api/situations/{id}/recommendation`
- `POST /api/actions/{id}/approve` and `POST /api/actions/{id}/reject`
- `GET /api/merchants/{id}/timeline`
- `POST /api/sim/advance` (simulated clock)
- `GET /api/cases/{id}`
- `POST /api/merchants/{id}/scenario` (load one of the three demo situations)

Publish documented mock responses first; keep response shapes identical to the
contracts.

## 8. Tests you must have

- Policy rules, including limit boundaries and prohibited actions.
- Duplicate approval does not execute twice; replayed webhook is ignored.
- Webhook with a bad signature is rejected.
- Retriever Recall@3 on held-out cases.
- Detector fires on seeded spikes and stays quiet on normal variation.
- A scripted end-to-end scenario against the sandbox.

## 9. Do not

- Put credentials in the frontend or the repo.
- Trust frontend state as proof of payment or success.
- Let anything except the Executor call PayPal.
- Present simulated outcomes as real.
- Add multi-tenant, fine-tuning, a knowledge graph or extra domains unless the
  3-day checkpoint says the core scenario already runs.

## 10. Done means

- A real sandbox dispute is read and at least one approved action executes, or the
  simulated fallback is clearly labelled.
- The gate shows AUTO, NEEDS APPROVAL and BLOCKED in the demo with reasons.
- All tests in section 8 pass; the app is hosted or runs with one command.
- README has setup and run instructions; a licence is visible; no secrets committed.

## 11. Ask Person A for

- The case schema and the first batch of cases so the retriever has data.
- The `recommend(situation, precedents)` function signature and a fixture
  `Recommendation` to test the gate against.
- The abstain and threshold values they expect, so the gate and Consultant agree.
