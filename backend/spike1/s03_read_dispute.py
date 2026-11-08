"""Spike 1, step 4: list disputes and show one in detail, with allowed actions.

Usage: python s03_read_dispute.py [dispute_id]
Sandbox only, read-only.
"""
import json
import sys

from common import check_env, get_token, load_env, request

env = load_env()
problems = check_env(env)
if problems:
    raise SystemExit("ENV PROBLEMS: " + "; ".join(problems))
status, tok = get_token(env)
if status != 200:
    raise SystemExit(f"token failed: {status}")
token = tok["access_token"]

status, lst, _ = request("GET", "/v1/customer/disputes?page_size=20", token=token)
print("list status:", status)
items = lst.get("items", [])
print("disputes found:", len(items))
for d in items:
    print("  ", d.get("dispute_id"), "|", d.get("status"), "|", d.get("reason"),
          "|", d.get("dispute_state"), "|", (d.get("dispute_amount") or {}).get("value"))

dispute_id = sys.argv[1] if len(sys.argv) > 1 else (items[0]["dispute_id"] if items else None)
if not dispute_id:
    raise SystemExit("no dispute to show")

status, d, hdrs = request("GET", f"/v1/customer/disputes/{dispute_id}", token=token)
print("\nshow dispute status:", status, "| debug id:", hdrs.get("Paypal-Debug-Id") or hdrs.get("paypal-debug-id"))
if status != 200:
    print(json.dumps(d, indent=2)[:2000])
    raise SystemExit(1)

for key in ("dispute_id", "reason", "status", "dispute_state", "dispute_life_cycle_stage",
            "dispute_channel", "create_time", "update_time", "seller_response_due_date",
            "buyer_response_due_date"):
    print(f"{key}: {d.get(key)}")
print("dispute_amount:", d.get("dispute_amount"))
print("disputed_transactions:", json.dumps(d.get("disputed_transactions"), indent=1)[:800])
print("\nallowed_response_options:")
print(json.dumps(d.get("allowed_response_options"), indent=1)[:2500])
print("\nlinks (HATEOAS actions):")
for link in d.get("links", []):
    print("  ", link.get("method"), link.get("rel"))
print("\nevidences:", json.dumps(d.get("evidences"), indent=1)[:800])
print("messages:", json.dumps(d.get("messages"), indent=1)[:800])
