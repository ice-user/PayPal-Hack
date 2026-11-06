"""Shared helpers for the Spike 1 scripts. Sandbox only. Never prints secrets."""
import base64
import json
import os
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(HERE, "..", ".env")
SANDBOX_HOST = "https://api-m.sandbox.paypal.com"


def load_env():
    env = {}
    with open(ENV_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def check_env(env):
    """Return a list of problems. Never includes values."""
    problems = []
    for key in ("PAYPAL_CLIENT_ID", "PAYPAL_CLIENT_SECRET", "PAYPAL_BASE_URL"):
        val = env.get(key, "")
        if not val:
            problems.append(f"{key} is empty")
        elif val.startswith("PASTE_"):
            problems.append(f"{key} still has the placeholder")
    if env.get("PAYPAL_BASE_URL", "") != SANDBOX_HOST:
        problems.append("PAYPAL_BASE_URL must be exactly the sandbox host")
    return problems


def request(method, path, token=None, body=None, headers=None, form=None, basic=None):
    """Call the sandbox API. Refuses any host except the sandbox."""
    url = SANDBOX_HOST + path
    h = {"Accept": "application/json"}
    data = None
    if form is not None:
        data = urllib.parse.urlencode(form).encode()
        h["Content-Type"] = "application/x-www-form-urlencoded"
    elif body is not None:
        data = json.dumps(body).encode()
        h["Content-Type"] = "application/json"
    if basic:
        h["Authorization"] = "Basic " + base64.b64encode(f"{basic[0]}:{basic[1]}".encode()).decode()
    if token:
        h["Authorization"] = "Bearer " + token
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, data=data, headers=h, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read().decode()
            return r.status, (json.loads(raw) if raw else {}), dict(r.headers)
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            return e.code, json.loads(raw), dict(e.headers)
        except ValueError:
            return e.code, {"raw": raw[:500]}, dict(e.headers)


def auth_assertion_jwt(client_id, buyer_email):
    """Unsigned JWT (alg none) identifying the sandbox buyer, per PayPal's sandbox docs."""
    def b64(obj):
        raw = json.dumps(obj, separators=(",", ":")).encode()
        return base64.urlsafe_b64encode(raw).decode().rstrip("=")
    return b64({"alg": "none", "typ": "JWT"}) + "." + b64({"iss": client_id, "email": buyer_email}) + "."


def request_multipart(method, path, token, input_json, headers=None):
    """POST a multipart/form-data body with a single JSON part named 'input'."""
    boundary = "----precedent" + base64.b16encode(os.urandom(8)).decode()
    payload = (
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="input"\r\n'
        "Content-Type: application/json\r\n\r\n"
        f"{json.dumps(input_json)}\r\n"
        f"--{boundary}--\r\n"
    ).encode()
    h = {
        "Accept": "application/json",
        "Authorization": "Bearer " + token,
        "Content-Type": f"multipart/form-data; boundary={boundary}",
    }
    if headers:
        h.update(headers)
    req = urllib.request.Request(SANDBOX_HOST + path, data=payload, headers=h, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read().decode()
            return r.status, (json.loads(raw) if raw else {}), dict(r.headers)
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            return e.code, json.loads(raw), dict(e.headers)
        except ValueError:
            return e.code, {"raw": raw[:500]}, dict(e.headers)


def get_token(env):
    status, body, _ = request(
        "POST", "/v1/oauth2/token",
        basic=(env["PAYPAL_CLIENT_ID"], env["PAYPAL_CLIENT_SECRET"]),
        form={"grant_type": "client_credentials"},
    )
    return status, body
