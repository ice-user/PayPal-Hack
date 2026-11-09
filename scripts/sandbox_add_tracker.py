"""Add shipment tracking to a PayPal SANDBOX transaction with the Add Tracking API, so
Precedent reads the parcel's state from PayPal (delivered / in transit) when it imports
the dispute. Sandbox only (the adapter refuses any other host). Credentials come from
backend/.env and are never printed.

    python scripts/sandbox_add_tracker.py <seller_transaction_id> DELIVERED
    python scripts/sandbox_add_tracker.py <seller_transaction_id> SHIPPED --tracking 1Z999 --carrier UPS

The seller transaction ID is in the PayPal sandbox business account (Activity), or in the
dashboard's PayPal section once the dispute is imported.
"""
import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from precedent.paypal_adapter import PayPalAdapter, PayPalError  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("transaction_id")
    ap.add_argument("status", choices=["SHIPPED", "DELIVERED", "ON_HOLD", "CANCELLED"])
    ap.add_argument("--tracking", default=None, help="tracking number (default: a generated test number)")
    ap.add_argument("--carrier", default="UPS", help="PayPal carrier code, e.g. UPS, FEDEX, USPS, DHL")
    args = ap.parse_args()
    adapter = PayPalAdapter()
    if not adapter.configured:
        print("PayPal sandbox credentials are missing in backend/.env.")
        return 1
    tracker = {"transaction_id": args.transaction_id, "tracking_number": args.tracking or f"PRC{int(time.time())}",
               "status": args.status, "carrier": args.carrier}
    existing = adapter.trackers(args.transaction_id)
    try:
        if any(t.get("tracking_number") == tracker["tracking_number"] for t in existing):
            tid = f"{args.transaction_id}-{tracker['tracking_number']}"
            adapter._call("PUT", f"/v1/shipping/trackers/{tid}", body=tracker)
            print(f"Updated tracker {tracker['tracking_number']} to {args.status}.")
        else:
            out = adapter._call("POST", "/v1/shipping/trackers-batch", body={"trackers": [tracker]})
            errors = out.get("errors") or []
            if errors:
                print("PayPal rejected the tracker:", json.dumps(errors)[:500])
                return 1
            print(f"Added tracker {tracker['tracking_number']} ({args.carrier}, {args.status}).")
    except PayPalError as e:
        print(f"PayPal returned {e.status}: {', '.join(e.issues) or e.body.get('name')}")
        return 1
    print("Press Refresh in the dashboard's PayPal section to import it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
