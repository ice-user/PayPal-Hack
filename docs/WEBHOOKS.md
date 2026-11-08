# PayPal sandbox webhook integration

The receiver is `POST /api/paypal/webhook`. It sends the original parsed event
and transmission headers to PayPal's signature-verification API. There is no
local bypass. No webhook triggers a seller action or marks an action successful.

## Local verification

From the repository root in PowerShell:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_webhooks.py tests/test_api.py -q -p no:cacheprovider
```

These tests use a fake PayPal transport; they do not establish real signature
verification or live delivery. They cover duplicate events with new delivery IDs,
malformed requests, verification outages and retry, out-of-order updates,
concurrent delivery, atomic rollback, old database upgrade, restart persistence,
and isolation from execution and simulated actions.

## Behavior and storage

- Events require a nonempty `id`, `event_type`, timezone-aware `create_time`,
  and an object `resource`. Bodies over 1 MiB return 413; malformed envelopes
  and invalid signatures return 400.
- Missing receiver configuration or an unavailable/erroring verification API
  returns 503. Nothing is marked processed, so delivery can be retried.
- Verified `event.id` is the deduplication key. The first delivery returns
  `{"ok":true,"replay":false}`; redelivery returns `{"ok":true,"replay":true}`.
  Every delivery, including a duplicate, still requires a valid signature.
- `CUSTOMER.DISPUTE.CREATED`, `.UPDATED`, and `.RESOLVED` require `dispute_id`.
  Other event types are acknowledged and audited as ignored.
- Event metadata, the dispute snapshot, and its audit entry commit together.
  A database write failure rolls back ingestion and returns a server error.
- Snapshots require `resource.status` and `resource.update_time`. Only a strictly
  newer resource timestamp replaces a snapshot; equal or older updates remain
  in history. Partial events without state/time remain in history too. Event
  creation time is not substituted for resource update time. Equal-time conflicts
  need an operator read of PayPal's current dispute; the first snapshot is retained.
- Stored fields are IDs, event/delivery times, type, status, state and lifecycle
  stage. Buyer details, messages, raw envelopes, signatures and credentials are
  not retained. The snapshot reflects the latest eligible received event, not a
  guaranteed current PayPal view.
- New `verified_webhook_events` and `paypal_dispute_snapshots` tables are created
  automatically. The old transmission-only `webhook_events` table is preserved;
  it cannot deduplicate old events by event ID. Old deliveries first seen after
  the upgrade may therefore be recorded once in the new history.
- The normal API stores SQLite at `backend/data/precedent.db`. Persist that
  directory across deployments (container path `/app/backend/data`). The isolated
  demo runner has an in-memory database and no verification credentials.

## Inspecting events and related actions

```text
GET /api/paypal/disputes/{dispute_id}/events?limit=50
GET /api/audit
```

The history endpoint returns `snapshot`, `events`, and `related_actions`. Its
limit is 1–500; results are ordered by event creation time descending. It reads
local storage only. `GET /api/paypal/disputes/{dispute_id}` separately reads PayPal.

Related actions match exact dispute IDs in real execution's successful
`paypal_ref` values, including only the real members of a partially simulated
batch. They mean **same dispute**, not proof that an action caused an update or
resolved a dispute. Audit links capture what was known on receipt; the history
endpoint resolves links again so events arriving before execution finishes can
be associated later. Demo reset clears actions, so current history links then
disappear; the original event and audit history remain.

## Live sandbox delivery still to verify

1. Configure sandbox `PAYPAL_CLIENT_ID` and `PAYPAL_CLIENT_SECRET` locally in
   `backend/.env` or as deployment secrets. Keep `PRECEDENT_REAL_EXECUTION=0`
   while testing delivery. Start the normal API, not `run_local_demo.py`:
   `python -m uvicorn precedent.api:app --app-dir backend --port 8000`.
2. Choose an HTTPS host or tunnel. Route `/api/paypal/webhook` to the API. For a
   tunnel, expose only this webhook path; the existing demo/operator API has no
   authentication and should stay private. Persist the database on a hosted API.
3. Register the HTTPS callback in the same PayPal sandbox REST app, subscribing
   to `CUSTOMER.DISPUTE.CREATED`, `CUSTOMER.DISPUTE.UPDATED`, and
   `CUSTOMER.DISPUTE.RESOLVED`. Save its assigned ID as `PAYPAL_WEBHOOK_ID` and
   restart the API. `/api/health` should show both configuration flags true.
4. With a fresh sandbox dispute and approval for any seller operation, cause a
   supported dispute update. Inspect the registered app's webhook delivery log
   for HTTP 200 and inspect local history/audit for the event ID and dispute ID.
   A hand-written curl payload cannot replace this signature-verification test.
5. Redeliver that same event from PayPal's delivery log. Expect `replay:true`,
   one event row, and one `webhook_received` audit entry. Restart the API with
   the same database and repeat to check persistence.
6. Compare the snapshot with a direct sandbox dispute read. Record the actual
   event type, status and test outcome without copying credentials or buyer data.

Public delivery, real signature verification, and event-to-action timing have
not yet been verified against PayPal. These require a registered HTTPS endpoint
and a fresh sandbox event; the local tests do not claim that validation.
