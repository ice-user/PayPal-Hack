# PayPal integration

Precedent uses PayPal in both directions. Disputes and shipment tracking come **in** from
the merchant's PayPal account. Case-based reasoning decides what to do. The approved seller
actions go back **out** to PayPal, on the exact dispute they were decided for. Everything
runs against the PayPal **sandbox**: the adapter refuses any other host.

| PayPal capability | Endpoint | What Precedent does with it | Code |
|---|---|---|---|
| OAuth 2.0 client credentials | `POST /v1/oauth2/token` | App token, cached until expiry | `paypal_adapter.py` |
| Disputes API: list disputes | `GET /v1/customer/disputes` | Imports every dispute on the account | `paypal_feed.py` |
| Disputes API: show dispute details | `GET /v1/customer/disputes/{id}` | Reason, amount, response deadline, disputed transaction, and the seller actions PayPal allows now (HATEOAS links). Re-read right before every action. | `paypal_feed.py`, `paypal_adapter.py` |
| Add Tracking API: list trackers | `GET /v1/shipping/trackers?transaction_id=` | The parcel's state: `DELIVERED` → delivered (carrier confirmation); `SHIPPED` / `ON_HOLD` → in transit; none → no tracking | `paypal_feed.py` |
| Disputes API: provide evidence | `POST /v1/customer/disputes/{id}/provide-evidence` | Proof of delivery, or shipment proof without claiming delivery | `paypal_adapter.py` |
| Disputes API: send message | `POST /v1/customer/disputes/{id}/send-message` | Tells the buyer the real delivery window | `paypal_adapter.py` |
| Disputes API: make offer / accept claim | `POST .../make-offer`, `POST .../accept-claim` | Refunds for lost parcels: money tier, approval and a $500 cap | `paypal_adapter.py` |
| Webhooks: verify signature | `POST /v1/notifications/verify-webhook-signature` | Verified, de-duplicated dispute event history | `webhooks.py`, `api.py` |

## How it shows in the demo

- **Situation T (TechKart):** each dispute on the sandbox account that is waiting for the
  seller's response is triaged next to the synthetic TechKart disputes. They use the same
  dispute-level cases, are judged against today's date, and are marked **PayPal**. Each one
  gets its own action group, and its actions carry that dispute's real ID (`params.dispute_ids`).
- **Action cards** name the PayPal dispute they will act on. The confirm step says whether
  this deployment sends that action type for real.
- **PayPal section:** the connected account (every dispute, its PayPal status, the parcel's
  state from PayPal tracking, and what PayPal lets the seller do now), plus a live log of
  every request the server made to PayPal (method, path, HTTP status, latency). No tokens,
  bodies or personal data are logged.

## Safety on the public site (`render.yaml`)

- `PRECEDENT_REAL_ACTIONS=SEND_MESSAGE,PROVIDE_EVIDENCE`: only these run for real. Refunds
  and offers stay simulated and labelled.
- `PRECEDENT_REAL_CALLS_PER_HOUR=20`: a cap across all visitors.
- Every real action re-reads the dispute first. If PayPal no longer allows the action (for
  example, another visitor already filed evidence), it becomes a labelled simulation that
  says why.
- Imports are cached for 60 seconds (`PRECEDENT_PAYPAL_TTL`) and shared by all visitors.
  Refresh is limited to once every 10 seconds.

## Preparing sandbox data

1. In the PayPal developer dashboard, use a sandbox **personal** (buyer) account to pay the
   sandbox **business** account for goods, then open a dispute: "item not received".
2. Optionally give the parcel a state that PayPal knows about:
   `python scripts/sandbox_add_tracker.py <seller_transaction_id> DELIVERED` (or `SHIPPED`).
3. Press **Refresh** in the dashboard's PayPal section. The dispute appears there and, on
   situation T, in the triage with its own proposed action.

Run the dashboard locally against the sandbox, read-only:
`python scripts/run_local_demo.py --paypal`.

**Limits.** PayPal trackers have no "lost" status, so a lost parcel is never inferred from
PayPal. Imported disputes that are in transit have no delivery estimate, so Precedent treats
the deadline as coming first and does not wait. The situation-level spike numbers still come
from the synthetic TechKart order feed.
