"""Spike 1, step 5a: sandbox-only 'update dispute status' to ask the seller for evidence.

Usage: python s04_require_evidence.py <dispute_id> [SELLER_EVIDENCE|BUYER_EVIDENCE]
Sandbox only. Changes the state of a TEST dispute. Then re-reads it and prints the
status, stage and the actions PayPal now allows.
"""
import json
import sys

from common import check_env, get_token, load_env, request

if len(sys.argv) < 2:
    raise SystemExit("usage: python s04_require_evidence.py <dispute_id> [action]")
dispute_id = sys.argv[1]
action = sys.argv[2] if len(sys.argv) > 2 else "SELLER_EVIDENCE"

env = load_env()
problems = check_env(env)
if problems:
    raise SystemExit("ENV PROBLEMS: " + "; ".join(problems))
status, tok = get_token(env)
if status != 200:
    raise SystemExit(f"token failed: {status}")
token = tok["access_token"]

status, resp, hdrs = request(
    "POST", f"/v1/customer/disputes/{dispute_id}/require-evidence",
    token=token, body={"action": action},
)
print("require-evidence status:", status, "| debug id:", hdrs.get("Paypal-Debug-Id") or hdrs.get("paypal-debug-id"))
print(json.dumps(resp, indent=2)[:1500])

status, d, _ = request("GET", f"/v1/customer/disputes/{dispute_id}", token=token)
print("\nre-read status:", status)
for key in ("status", "dispute_state", "dispute_life_cycle_stage", "seller_response_due_date"):
    print(f"{key}: {d.get(key)}")
print("allowed_response_options:", json.dumps(d.get("allowed_response_options"), indent=1)[:2500])
print("links:", [(l.get("method"), l.get("rel")) for l in d.get("links", [])])
