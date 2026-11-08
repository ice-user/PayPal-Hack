# Devpost submission (draft)

> Draft for the team to edit. Every number here comes from `eval/results/summary.md`,
> `docs/SPIKE1_RESULT.md` or `docs/SPIKE2_RESULT.md`. Do not add a number that is not in
> those files.

## Precedent: a dispute consultant for PayPal merchants that cites past cases before it acts

### Inspiration
Doctors and lawyers reason from precedent: what happened last time a case looked like
this, and what was done. Merchants facing a spike in PayPal disputes get a dashboard that
says the rate went up, but not why, and not what worked before. They end up applying
generic advice, refunding everyone, or doing nothing. We wanted an assistant that reasons
like a good operations consultant. It works out the cause, shows its precedents, proposes
safe actions, and lets a human decide.

### What it does
- **Detects** a dispute spike against the merchant's own baseline, with a binomial test
  and confidence intervals, and refuses to call small samples.
- **Diagnoses** the cause from order and fulfilment signals: one carrier, slow shipping
  across carriers, or parcels that were delivered anyway.
- **Retrieves precedents** and shows why each one matches and where it differs. Every case
  carries its provenance (public, authored or sandbox-simulated) and its evidence quality.
- **Proposes typed actions** (provide evidence, message buyers, make an offer, accept a
  claim, prepare-only notes). Every action cites the cases behind it.
- **A deterministic policy gate** decides what runs automatically (prepare-only), what needs
  one click (anything a buyer or PayPal sees) and what needs explicit approval or is blocked
  (money, above a hard cap).
- **Executes through the PayPal Disputes API** (sandbox). The backend re-reads the dispute
  before acting, and only makes calls PayPal currently allows. Otherwise it records a
  labelled simulation and says why.
- **Records the outcome** on a simulated clock. The result becomes a new case that a human
  reviews before it joins the library.
- **Refuses to invent forecasts.** A numeric expected effect is shown only when at least two
  matching cases have measured before/after numbers. Today none do, so the app says so.

The same symptom (an item-not-received spike) produces three different plans in the
demo. With precedent retrieval switched off, the same system gives one generic plan, and
the policy gate blocks it.

### How we built it
- **Backend:** Python, FastAPI, SQLite.
  - The executor is a state machine with idempotency keys, so a double click cannot
    execute twice.
  - The policy gate is re-run at approval time.
  - Every step goes to an audit log.
- **PayPal:**
  - REST adapter for OAuth and the Customer Disputes API: read dispute, send message,
    provide evidence, make offer, accept claim.
  - Webhook receiver with signature verification through PayPal's verification endpoint.
  - The adapter refuses any non-sandbox host.
- **Intelligence:**
  - The Consultant is a rules engine: precedents vote on interventions, weighted by
    similarity and evidence quality.
  - Actions come only from a fixed enum and fixed templates.
  - An optional Claude writer may reword the explanations only. Its text is rejected if
    it adds any number not in the data, or uses causal language.
- **Data:**
  - A seeded synthetic order-and-fulfilment feed plants known causes.
  - The case library has 31 approved cases. Four are public: three FTC actions against
    payment processors and one merchant report. The other 27 are authored playbook cases,
    labelled as such.
- **Frontend:** React and Vite. JSON-schema contracts are shared with the backend.
- **Tests:** 62 automated tests cover:
  - policy tiers;
  - duplicate approvals;
  - webhook signatures and replays;
  - the detector on planted spikes;
  - the LLM guards.

### Evaluation
- **Ablation:** synthetic scenarios with a planted cause, each run with and without precedent
  retrieval.
- **Held-out test set:** 18 scenarios, committed before the run and run once after the case
  library was frozen.
  - Right cause, when acting is right: without precedent 0 of 13; with precedent 9 of 13.
  - All four misses were abstentions, so the system proposed nothing rather than the wrong fix.
  - Removing every case of the true cause made it abstain in 13 of 13.
  - The detector matched ground truth in 18 of 18.
- **Development set:** 12 of 13 right causes. We tuned on it, so we report the test set as the
  headline.
- **Retriever:** a case of the true cause was in the top 3 in 15 of 15 test scenarios.
- **Honest caveats:**
  - The same team wrote the scenarios and the authored cases, so agreement partly reflects
    internal consistency.
  - The one unsafe act, in both sets, is a scenario with two simultaneous causes. It is read
    as a single cause.
- **Human rating:** a two-rater blind rubric is prepared (`eval/RUBRIC.md`).
  [Fill in the scores and inter-rater agreement once rated.]

### Challenges we ran into
- **Sandbox disputes:** creating disputes through the API needs buyer consent our app does
  not have. We created the demo dispute as the buyer in the sandbox UI instead. PayPal also
  puts each dispute under review for a few minutes after every step, so the adapter
  re-checks the dispute's allowed actions before every call instead of assuming.
- **No measured precedents in public data:** FTC filings give detailed numbers about the
  problem but not about fixes. We chose to show no forecast rather than an invented one.

### Accomplishments that we're proud of
- A real seller action executed through the PayPal Disputes API, behind a human click and
  a deterministic gate.
- Every claim on screen is either computed, cited or labelled simulated.

### What we learned
- Grounding changes behaviour more than wording does. Without precedents the plan collapses
  to one generic answer.
- Abstaining is a feature: when its playbook was missing, the system declined instead of
  guessing.

### What's next
- Measured precedents from merchants who opt in. This is the one thing that would unlock
  honest numeric forecasts.
- Hybrid retrieval with text embeddings.
- Webhooks end to end.
- More domains on the same loop: cash flow and invoicing.

### Built with
python · fastapi · sqlite · react · typescript · vite · paypal-disputes-api · paypal-rest-api · json-schema · claude (optional prose writer)

### Try it
[Live URL once deployed] · [Repo URL] · [Video URL]
