# Handoff: Person A (frontend and language ML)

Read first: `docs/BRIEF.md` (decisions and rules), then `docs/DESIGN.md` (sections
3, 5.1, 5.6, 9, 10). This file is your task list.

## 1. The product in three sentences

Precedent is a web dashboard for PayPal merchants. It detects a dispute spike,
finds similar past cases, explains why, proposes typed actions, and, after policy
checks and a human click, executes them through the PayPal Sandbox. It then records
the outcome as a new case. The demo merchant and its orders are synthetic; PayPal
disputes and actions are real in the sandbox wherever Spike 1 confirms they work.

## 2. You own

1. The whole frontend.
2. The case library and the case schema (Spike 2 is yours).
3. The Consultant: the LLM step that turns a situation plus precedents into a
   `Recommendation`.
4. The precedent ablation (rubric and scoring).
5. The demo script and the recording.

Person B owns PayPal, policy gate, executor, API, database, hosting, the order
generator, Situation Builder, Retriever and Outcome Tracker.

## 3. Do these in order

1. **Contracts and fixtures (first hours, with Person B).** Agree the
   `SituationRecord` and `Recommendation` shapes in `docs/DESIGN.md` section 3. Put
   JSON schemas and hand-written fixtures in `/contracts`. Write three fixtures for
   the three demo situations (A one carrier, B many carriers with delays, C delivered
   orders). This lets you build the UI before the backend exists.
2. **Spike 2 (about 2 hours).** Extract five real cases: two FTC payment-processor
   cases, plus PayPal and Block 10-K loss disclosures (EDGAR needs a User-Agent
   header). Fill the case schema, label each field directly sourced, inferred or
   authored, and leave gaps empty. Report which fields you could fill. Pass: at
   least three of five support meaningfully different decisions.
3. **UI skeleton on fixtures.** One main screen first (section 4), then the
   approval flow and timeline.
4. **Case library to 60+ cases** (public, authored, live_simulated), each with
   provenance and `evidence_quality`. Aim for a mix that includes enough measured
   cases for the three situations.
5. **Consultant** (section 5), tested against the fixtures.
6. **Ablation and rubric** (section 7).
7. **Wire the UI to Person B's real API** when it replaces the mock responses.

## 4. UI spec (one main screen)

Three columns plus a timeline:

- **Situation:** volume, dispute rate with baseline and confidence interval, trend,
  reason mix, carrier and SKU concentration, open disputes, an anomaly flag.
- **Precedents:** each case with similarity, `matched_on`, `differs_on`, the
  intervention, observed outcome with its period, a provenance badge (`public`,
  `authored`, `live_simulated`) and an `evidence_quality` badge. A toggle shows the
  recommendation **with and without precedent**.
- **Plan:** each action with its policy tier badge (AUTO, NEEDS APPROVAL, BLOCKED)
  and the rule that decided it. Predicted effect shown only if the recommendation
  includes it. Playbook notes shown as qualitative text. Approve and reject buttons.
- **Timeline:** detected, recommended, approved, executed, measured. Mark simulated
  steps with a visible "simulated" label.

Also: a switcher for the three demo situations; an abstain state that says why;
loading and error states. No generic chatbot panel. Keep wording to "observed" and
"followed", never "caused".

## 5. Consultant spec

- **Input:** a `SituationRecord` and the top-k precedents with `matched_on` and
  `differs_on`.
- **Output:** a `Recommendation`: diagnosis, precedents used, typed actions from a
  fixed enum, `playbook_notes`, confidence, evidence quality, required approval,
  `abstain` with a reason. Validate the output against the JSON schema; reject and
  retry on schema failure.
- **Rules:** the LLM never produces PayPal calls. It never writes a numeric
  predicted effect: Person B's code computes `predicted_effect` and `counterfactual`
  from measured cases only. The Consultant must abstain when fewer than `k_min`
  precedents clear the similarity threshold or the case evidence is too weak.
- **Interface:** a Python function `recommend(situation, precedents) -> Recommendation`
  in `/intelligence`, called by Person B's API.

## 6. Case schema (fields you fill)

Context, trigger signals with numbers, diagnosis, intervention, outcome (before,
after, observed change, measurement period), source reference, licence,
`provenance`, `evidence_quality` (`measured_observational`, `aggregate_disclosure`,
`incomplete_report`, `illustrative`, `simulated`), `causal_claim` (always false),
`confounders_assessed`. Only `measured_observational` cases may drive a numeric
effect. Authored cases are labelled illustrative and are never presented as real.

## 7. Evaluation (you own the ablation)

- **Precedent ablation:** run 15 to 20 situations through System A (no retrieval) and
  System B (with precedents). You and Person B each score every recommendation
  independently on a short rubric: appropriate intervention, grounded in cited
  evidence, unsupported claims, abstains when it should. Agree the rubric before
  you build the Consultant. Report inter-rater agreement.
- Be honest in the write-up: the corpus is small and partly authored, so this shows
  the mechanism, not real-world efficacy. Report the measured versus authored mix.

## 8. Do not

- Invent outcomes or present authored or simulated results as measured.
- Let the Consultant touch PayPal or compute numeric effects.
- Build a chatbot, a knowledge graph, fine-tuning or extra finance domains.
- Commit secrets or API keys.

## 9. Done means

- The main scenario runs end to end in the UI against the real API.
- The with/without-precedent toggle visibly changes the recommendation.
- Three situations show three different recommendations.
- Every simulated element is labelled; every claim cites a case.
- Ablation scores and the rubric are written up.
- A demo script exists and the recording is under 3 minutes.

## 10. Ask Person B for

- A documented mock API (FastAPI auto docs are enough) before the real one.
- The list of dispute actions Spike 1 confirmed, so the UI only offers real ones.
- Retriever output including `matched_on` and `differs_on`.
