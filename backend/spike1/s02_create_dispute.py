"""Spike 1, step 3: try to create a sandbox dispute through the API (buyer-side).

Usage: python s02_create_dispute.py <buyer_transaction_id> [amount]
Sandbox only. Prints status and PayPal's response; never prints the token or JWT.
"""
import json
import sys

from common import auth_assertion_jwt, check_env, get_token, load_env, request_multipart

if len(sys.argv) < 2:
    raise SystemExit("usage: python s02_create_dispute.py <buyer_transaction_id> [amount]")
txn = sys.argv[1]
amount = sys.argv[2] if len(sys.argv) > 2 else "7.50"

env = load_env()
problems = check_env(env)
if problems or not env.get("BUYER_EMAIL"):
    raise SystemExit("ENV PROBLEMS: " + "; ".join(problems or ["BUYER_EMAIL is empty"]))

status, tok = get_token(env)
if status != 200:
    raise SystemExit(f"token failed: {status}")
token = tok["access_token"]

jwt = auth_assertion_jwt(env["PAYPAL_CLIENT_ID"], env["BUYER_EMAIL"])
body = {
    "disputed_transactions": [{"buyer_transaction_id": txn}],
    "reason": "MERCHANDISE_OR_SERVICE_NOT_RECEIVED",
    "dispute_amount": {"currency_code": "USD", "value": amount},
    "extensions": {
        "merchant_contacted": True,
        "merchant_contacted_outcome": "NO_RESPONSE",
        "merchandize_dispute_properties": {"issue_type": "PRODUCT"},
    },
}
status, resp, hdrs = request_multipart(
    "POST", "/v1/customer/disputes", token, body, headers={"PayPal-Auth-Assertion": jwt}
)
print("create dispute status:", status)
print("paypal-debug-id:", hdrs.get("Paypal-Debug-Id") or hdrs.get("paypal-debug-id"))
print(json.dumps(resp, indent=2)[:3000])
