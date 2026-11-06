# Spike 1 result: PayPal sandbox dispute path

Run on 2026-11-07 against `api-m.sandbox.paypal.com` with the app `precedent`
(sandbox, US Business account). Scripts: `backend/spike1/`. Secrets live only in
`backend/.env` (git-ignored).

## Verdict: PASS (dispute created by hand in the buyer UI; seller action executed by API)

**Update, later on 2026-11-07:** the dispute left `UNDER_PAYPAL_REVIEW` by itself and
moved to `WAITING_FOR_SELLER_RESPONSE` / `REQUIRED_ACTION`. PayPal then offered
`accept_claim`, `escalate`, `make_offer` (offer type REFUND), `provide_evidence` and
`send_message`. We sent a real seller message (`POST .../send-message`, HTTP 200,
debug id `f89425965e54d`). It appears on the dispute as posted by `SELLER`. Right after
the message, the dispute went back to `UNDER_PAYPAL_REVIEW` with no allowed actions.

**What this means:** the sandbox reviews each step asynchronously for a few minutes,
then reopens the dispute for the next party. "No allowed actions" is a transient state,
not a dead end. The adapter re-reads the dispute right before executing and falls back to
a labelled simulation only if the action is not allowed at that moment.

**Still not done:** API dispute creation (needs buyer consent), webhooks (need a public
URL and a webhook ID), and make-offer, provide-evidence or accept-claim. Those are kept
for the demo, because make-offer and accept-claim would close the only dispute.

## First pass (earlier the same day)

| # | Step | Result |
|---|---|---|
| 1 | Token (client credentials) | Works. Token includes `disputes/create`, `read-seller`, `update-seller`, `read-buyer`, `refund`, `reporting/search/read`, `documents/disputes/download` |
| 2 | Sandbox payment buyer to merchant (UI, goods and services, 7.50 USD) | Works. Buyer txn `8HK55648KD177333M`, seller txn `92453420A3004714D` |
| 3 | Create dispute through API with `PayPal-Auth-Assertion` | FAILED: 400 `invalid_request`, "No permissions to set target_client_id". Probable cause: no buyer consent via Log in with PayPal (not confirmed) |
| 3b | Create dispute by hand as the buyer (Resolution Center, "Report a problem", item not received) | Works. Dispute `PP-R-BTL-10196893` |
| 4 | Show dispute (`GET /v1/customer/disputes/{id}`) | Works (200). Status `OPEN`, state `UNDER_PAYPAL_REVIEW`, stage `INQUIRY`, channel `INTERNAL`, `seller_protection_eligible: false`. Buyer message and evidence visible |
| 4b | List disputes (`GET /v1/customer/disputes`) | Returns 200 with 0 items although the dispute exists. Cause unknown (indexing delay or missing filter). Do not rely on list; fetch by ID or use webhooks |
| 5 | Allowed actions | `allowed_response_options` is null and the only link is `self`. No seller action is offered |
| 5a | Sandbox-only require-evidence (`SELLER_EVIDENCE`) | FAILED: 400 `ACTION_NOT_ALLOWED_IN_CURRENT_DISPUTE_STATE` |
| 5b | Seller send-message | FAILED: 422 `ACTION_NOT_ALLOWED_IN_CURRENT_DISPUTE_STATE` |
| 5c | Make offer, provide evidence, accept claim | Not attempted: not offered while the dispute is under review |
| 6 | Settle (sandbox-only adjudicate), webhooks | Not attempted yet. Settle closes the dispute, so it is held back |

## Open questions
- Does the dispute leave `UNDER_PAYPAL_REVIEW` by itself after some minutes?
- What does the Business account's Resolution Center show and offer for it?
- Does a card-funded payment, or a different reason, produce a dispute in `WAITING_FOR_SELLER_RESPONSE`?
- Does the sandbox chargeback endpoint (`/v2/customer-support/process-chargeback`) work for our app?

## Fallback (per BRIEF.md)
If no seller action can be unlocked: drive the adapter from simulated dispute events
through the same interface, keep reading real disputes by ID, and label the
limitation in the UI, README and video.
