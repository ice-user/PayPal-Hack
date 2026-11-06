# Precedent: one-page brief (working title)

**Pitch:** a finance-agnostic AI operations consultant for businesses. It can support
multiple financial workflows—initially disputes/chargebacks, cash flow, and invoicing—
while using a focused PayPal merchant workflow to demonstrate the product. It detects
a risk or opportunity, retrieves relevant precedents, explains its reasoning, proposes
a remedy, and—only with appropriate human approval and policy checks—executes
supported actions through PayPal or connected financial systems. It then tracks the
observed outcome and adds it to the case library.

**Hackathon scope:** build the reusable, finance-agnostic foundation, but do not try to
fully implement all three domains for the demo. The demo video should tell one coherent
story that shows the full workflow end to end. The current recommended scenario is an
item-not-received dispute spike concentrated around one carrier/SKU.

**One-line test for every idea we discuss:** does it make the precedent visibly
change the action, make PayPal more central, or materially improve trust,
explainability, and safe human oversight? If not, defer or cut it.

Full design: `docs/DESIGN.md`.

## 1. Decide together (current recommendations)

| # | Decision | Current direction | Why / implementation guidance |
|---|---|---|---|
| 1 | Product scope / wedge | **Finance-agnostic architecture; support disputes/chargebacks, cash flow, and invoicing as target domains. Start with the disputes workflow for the PayPal demo.** | The product should not be conceptually locked to chargebacks. Keep the core situation → precedent → recommendation → approval → action → outcome loop reusable, with domain-specific data adapters and action policies. Do not attempt to fully build all three domains for the hackathon. |
| 2 | Demo scenario | **Use the item-not-received spike concentrated around one carrier/SKU as the demo-video scenario, provided merchant-side order/fulfilment data is available.** | This is a concrete story that can demonstrate the complete workflow: detect, diagnose, retrieve precedents, explain, recommend, approve, execute, and track. It is a demo scenario, not a limitation on the product's overall scope. |
| 3 | Case sources | **Hybrid: public sources + clearly labelled authored operational cases + sandbox-generated cases/events.** | Public sources provide provenance and real-world context but may not contain actionable merchant-level intervention outcomes. Authored cases can exercise the structured decision workflow, but must never be presented as observed real-world evidence. Sandbox cases demonstrate API execution, not real-world business impact. Every case must carry provenance and evidence quality. |
| 4 | PayPal capabilities / real vs simulated | **Use the capabilities actually available and verified in the PayPal sandbox. Prioritize real sandbox dispute reads and supported dispute actions; simulate only what cannot be genuinely measured or executed.** | PayPal documents sandbox support for creating disputes and sandbox-only status updates/settlement, plus dispute retrieval and seller response operations such as providing evidence, messaging, making an offer, and accepting a claim. Availability depends on dispute stage, account permissions, scopes, and the actions exposed for that dispute. Verify each operation in our own sandbox spike before promising it in the demo. The outcome clock and any unobserved business impact remain explicitly simulated. |
| 5 | Approval, safety, and explainability | **Human-in-the-loop by default for consequential actions. No exploitative, deceptive, or unsafe behaviour. Make reasoning, evidence, permissions, and action history visible.** | Financial workflows require trust. Default to read-only analysis and prepared recommendations. Require explicit human approval before externally visible or money-/account-state-changing actions. Enforce hard policy limits in code; block actions that are unauthorized, unsupported, outside configured limits, or insufficiently evidenced. Show why the system recommends an action, which precedents support it, what is uncertain, what will happen, and what happened afterward. Keep an auditable record. |
| 6 | PayPal tool layer | **Direct PayPal REST API through a backend adapter first. Consider MCP/Agent Toolkit only if it adds value after the core path works.** | Direct REST gives us control over authentication, permissions, validation, error handling, and the policy gate. MCP is an optional interface/extension, not a prerequisite for being agentic. Do not let tool abstraction delay proving the sandbox workflow. |
| 7 | Cut list / scope control | **Decide dynamically based on progress. No permanent ban on fine-tuning, multi-tenancy, or a knowledge graph, but defer them unless a demonstrated need justifies the cost.** | Reassess at implementation checkpoints. Protect the core workflow, safety, PayPal integration, evaluation, and demo reliability first. Add optional complexity only when the working system shows a clear need and there is enough time to validate it. |

### PayPal sandbox capability notes (verify in Spike 1)

PayPal's current Disputes API documentation describes these relevant capabilities:

- **Read:** list disputes and retrieve details.
- **Create test disputes:** sandbox-only dispute creation, requiring buyer-side setup/credentials and the `DISPUTE_CREATE` scope; PayPal documentation notes additional setup and buyer consent requirements.
- **Respond:** depending on dispute stage and available actions, the API supports operations such as providing evidence, sending a message during the inquiry stage, making an offer, accepting a claim, and acknowledging a returned item.
- **Sandbox-only lifecycle testing:** creating disputes, updating dispute status, and settling disputes are identified as sandbox-only test operations.
- **Webhooks:** dispute events can be delivered to a configured listener; the application must verify the webhook source/signature before acting on events.

Do not assume every action is available for every dispute. Inspect the dispute's current status and allowed/HATEOAS actions, and verify each operation with the actual sandbox app and account. Some operations require particular scopes, account permissions, lifecycle stages, or sufficient sandbox funds.

Useful official documentation:
- [Use the Disputes API](https://developer.paypal.com/platforms/disputes/handle-disputes/use-disputes-api/)
- [Integrate Disputes APIs and sandbox setup](https://developer.paypal.com/platforms/disputes/integrate-disputes/)
- [Test and go live](https://developer.paypal.com/disputes/test-go-live/)
- [Set up accounts and environment](https://developer.paypal.com/platforms/disputes/set-up/)
- [Dispute reasons and evidence](https://developer.paypal.com/disputes/reasons-evidence/)

**Important:** the existence of an endpoint in documentation is not proof that our particular sandbox app/account can use it. Spike 1 must record the exact successful calls, required setup, errors, and limitations.

## 2. The contract (do not change without telling the other person)

Two JSON shapes, defined in `docs/DESIGN.md` section 3:

- `SituationRecord`: features (dispute rate, trend, reason mix, concentration,
  open disputes, response time) plus a short narrative. **A produces.**
- `Recommendation`: diagnosis, precedents with `matched_on`, typed actions
  (fixed enum), predicted effect **derived cautiously from precedent outcomes**,
  counterfactual, confidence, evidence quality, explanation, required approval,
  and `abstain`. **A produces; B's gate consumes it.**

Hard rules:

- The LLM never makes raw PayPal calls.
- Policy enforcement, action validation, and execution are ordinary code.
- Credentials stay on the backend.
- Consequential actions require explicit human approval.
- The system must explain the evidence and reasoning behind recommendations.
- Observed association must not be described as causal impact unless a valid causal
  design supports that claim.
- The system must abstain when evidence is insufficient or the requested action is
  unsafe, unsupported, or unauthorized.

## 3. Two spikes, run in parallel before anything else

**Spike 1: PayPal dispute path (Person B), about 1 to 2 hours**

1. Create a PayPal developer account; make a sandbox business and a sandbox
   buyer account; create a REST app and note the client ID and secret.
2. Confirm the Customer Disputes feature/add-on and required scopes are enabled.
3. Make a sandbox purchase from the buyer to the business account.
4. Attempt to create a dispute through the sandbox-only create-dispute endpoint.
   Confirm buyer-side credentials/consent, `DISPUTE_CREATE` scope, and required
   `PayPal-Auth-Assertion` header/setup.
5. Read the dispute back.
6. Test the relevant seller actions that are available for that dispute, such as
   provide-evidence, send-message, make-offer, and accept-claim. Check lifecycle
   restrictions and required funds/permissions.
7. If time permits, test a sandbox-only status update/settlement and a webhook
   event, including webhook signature/source verification.
8. Report: which calls worked, which did not, exact setup requirements and errors.

**Spike 2: case extraction (Person A), about 2 hours**

1. Pick five real sources: two FTC payment-processor cases, and the PayPal and
   Block 10-K loss disclosures (EDGAR needs a User-Agent header).
2. For each, fill the case schema: context, trigger signals with numbers,
   diagnosis, actions, outcome (metric and time frame), source and licence.
3. Label each field as directly sourced, inferred, or authored; do not invent
   missing outcomes.
4. Report: for each case, which of the six fields you could fill and which you
   had to leave empty or author.

**Pass criteria:** Spike 1 passes if a dispute can be created and at least one
appropriate seller-side action works in the sandbox. Spike 2 passes if at least three
of five cases have enough information to support meaningfully different decisions,
with evidence provenance recorded.

**If a spike fails:** Spike 1 failing means B drives the adapter from simulated
dispute events through the same interface, while keeping the limitation visible.
Spike 2 failing means we change the source mix or narrow the case schema to what
the evidence can genuinely support.

## 4. Split

| Person A: intelligence | Person B: PayPal and product |
|---|---|
| Case library, Situation Builder | Sandbox seeding, PayPal adapter |
| Retriever, Consultant, Outcome Tracker | Policy Gate, Executor, webhooks |
| Evaluation (Recall@3, ablation, recommendation quality, abstention) | UI, hosting, README, licence, demo video |

## 5. Ground rules

- Every recommendation claim cites the cases and evidence that support it.
- Every case carries provenance (`public`, `authored`, `live_simulated`) and an
  evidence-quality label.
- Distinguish observed outcomes, simulated outcomes, predictions, and causal claims.
- Anything simulated is labelled simulated in the UI, the README and the video.
- Human approval is required before consequential external or financial actions.
- The UI explains the diagnosis, matched precedents, uncertainty, proposed action,
  policy decision, and execution result.
- No deceptive, exploitative, or unauthorized action.
- Not investment advice: decision support with cited precedents.
- Keep the repo public-ready from the start: no secrets committed, licence added.

## 6. Open items to check (not yet verified in our own environment)

- Which documented dispute operations are enabled for our specific sandbox app,
  account, scopes, and dispute lifecycle states.
- Whether sandbox dispute creation works with the required buyer-side setup and
  consent.
- Whether evidence, messaging, offers, claim acceptance, status updates, and
  settlement work for the test dispute(s).
- Webhook event names, delivery, and signature/source verification.
- Transaction Search or Reporting API availability and useful fields; fallback is
  our own event store.
- How merchant order, SKU, carrier, and fulfilment data will enter the system.
- Which additional PayPal APIs are useful for future cash-flow and invoicing domains.
- Which listed payment firms break out dispute or chargeback losses.
- Licences of any Kaggle or UCI datasets we use.

## 7. Our answers

| # | Decision | Final answer |
|---|---|---|
| 1 | Product scope / wedge | Finance-agnostic architecture targeting disputes/chargebacks, cash flow, and invoicing. Start with the disputes workflow for the PayPal hackathon demo; do not attempt to fully implement all three domains now. |
| 2 | Demo scenario | Use the item-not-received spike concentrated around one carrier/SKU as the demo-video scenario, provided merchant-side order/fulfilment data is available. The video should show the complete workflow end to end. |
| 3 | Case sources | Hybrid public + authored operational cases + sandbox-generated cases/events. Label provenance and evidence quality; never present authored or simulated results as real-world measured outcomes. |
| 4 | PayPal capabilities / real vs simulated | Use only capabilities verified in our own PayPal sandbox. Prioritize real sandbox dispute retrieval and supported seller actions. Use simulated events/outcome timing only where genuine execution or measurement is unavailable, and label it clearly. |
| 5 | Approval, safety, and explainability | Human-in-the-loop for consequential actions. Default to analysis/preparation; require explicit approval before external or financial state changes. Hard-block unsafe, exploitative, unauthorized, unsupported, over-limit, or insufficiently evidenced actions. Explain recommendations and maintain an audit trail. |
| 6 | PayPal tool layer | Direct REST API behind a backend adapter and policy gate first. Consider MCP/Agent Toolkit only after the core integration works and if it adds practical value. |
| 7 | Cut list / scope control | Revisit based on development progress. Defer optional complexity when it threatens the core workflow, integration, safety, evaluation, or demo reliability; add it only when justified by demonstrated need. |

Spike 1 result:

Spike 2 result:
