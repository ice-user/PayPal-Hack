"""Spike 1, step 1: can we get a sandbox token, and which scopes does it carry?"""
from common import load_env, check_env, get_token

env = load_env()
problems = check_env(env)
if problems:
    print("ENV PROBLEMS:", "; ".join(problems))
    raise SystemExit(1)

status, body = get_token(env)
print("token request status:", status)
if status != 200:
    print("error:", body.get("error"), "-", body.get("error_description"))
    raise SystemExit(1)

scopes = sorted(body.get("scope", "").split())
print("token_type:", body.get("token_type"), "| expires_in:", body.get("expires_in"))
print("scopes granted (%d):" % len(scopes))
for s in scopes:
    print("  ", s)
print()
print("has DISPUTE_CREATE scope:", any("disputes/create" in s for s in scopes))
print("has any disputes scope  :", any("disputes" in s for s in scopes))
