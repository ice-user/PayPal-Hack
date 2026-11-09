"""PayPal sandbox adapter. The ONLY module that talks to PayPal.

- Sandbox host only: any other base URL is refused.
- Reads disputes for real.
- Executes seller actions for real when the dispute currently allows them; otherwise
  falls back to a simulated execution and says why. Every result carries
  `mode: "real" | "simulated"` so the UI, README and video can label it.
- Credentials come from backend/.env and are never logged or returned.
"""
from __future__ import annotations

import base64
import json
import os
import re
import threading
import time
from collections import deque
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

SANDBOX = "https://api-m.sandbox.paypal.com"
ENV_PATH = Path(__file__).resolve().parents[1] / ".env"

# Which HATEOAS link / allowed option a seller action needs.
ACTION_LINK = {
    "PROVIDE_EVIDENCE": "provide_evidence",
    "SEND_MESSAGE": "send_message",
    "MAKE_OFFER": "make_offer",
    "ACCEPT_CLAIM": "accept_claim",
}


def load_env(path: Path = ENV_PATH) -> dict:
    env = dict(os.environ)
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    return env


class PayPalError(Exception):
    def __init__(self, status: int, body: dict):
        super().__init__(f"PayPal {status}: {body.get('name') or body.get('error')}")
        self.status, self.body = status, body

    @property
    def issues(self) -> list[str]:
        return [d.get("issue", "") for d in self.body.get("details", [])]


class PayPalAdapter:
    def __init__(self, env: dict | None = None, transport=None):
        env = env if env is not None else load_env()
        self.client_id = env.get("PAYPAL_CLIENT_ID", "")
        self._secret = env.get("PAYPAL_CLIENT_SECRET", "")
        self.base = env.get("PAYPAL_BASE_URL", SANDBOX)
        self.webhook_id = env.get("PAYPAL_WEBHOOK_ID", "")
        # Public deployments set PRECEDENT_REAL_EXECUTION=0 so anonymous visitors can only
        # trigger labelled simulations. Reads stay real.
        self.real_execution = env.get("PRECEDENT_REAL_EXECUTION", "1") != "0"
        # Optionally narrow real execution to some action types (a public demo keeps money
        # actions simulated) and cap real seller actions per hour across all visitors.
        raw_types = env.get("PRECEDENT_REAL_ACTIONS", "").strip()
        self.real_types = {t.strip().upper() for t in raw_types.split(",") if t.strip()} or None
        self.max_real_per_hour = int(env.get("PRECEDENT_REAL_CALLS_PER_HOUR", "0") or 0)
        self._real_sent: deque[float] = deque()
        # The last PayPal requests (method, path, status, time), shown in the dashboard so the
        # integration is visible. Paths carry sandbox IDs only; no tokens, bodies or personal data.
        self.activity: deque[dict] = deque(maxlen=60)
        self._lock = threading.Lock()
        if self.base != SANDBOX:
            raise ValueError("Refusing to run against a non-sandbox PayPal host.")
        self._token: tuple[str, float] | None = None
        self._transport = transport or self._http

    @property
    def configured(self) -> bool:
        return bool(self.client_id and self._secret and not self.client_id.startswith("PASTE_"))

    # ---- transport ----
    def _http(self, method: str, path: str, *, headers: dict, data: bytes | None) -> tuple[int, dict]:
        req = urllib.request.Request(self.base + path, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                raw = r.read().decode()
                return r.status, (json.loads(raw) if raw else {})
        except urllib.error.HTTPError as e:
            raw = e.read().decode()
            try:
                return e.code, json.loads(raw)
            except ValueError:
                return e.code, {"raw": raw[:300]}

    def _logged(self, method: str, path: str, **kw) -> tuple[int, dict]:
        t0 = time.monotonic()
        try:
            status, body = self._transport(method, path, **kw)
        except Exception:
            self._record(method, path, 0, t0)
            raise
        self._record(method, path, status, t0)
        return status, body

    def _record(self, method: str, path: str, status: int, t0: float) -> None:
        self.activity.appendleft({"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "method": method,
                                  "path": path, "status": status, "ms": round((time.monotonic() - t0) * 1000)})

    def _token_value(self) -> str:
        if self._token and self._token[1] > time.time() + 60:
            return self._token[0]
        basic = base64.b64encode(f"{self.client_id}:{self._secret}".encode()).decode()
        status, body = self._logged("POST", "/v1/oauth2/token", headers={
            "Authorization": f"Basic {basic}", "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json"}, data=b"grant_type=client_credentials")
        if status != 200:
            raise PayPalError(status, body)
        self._token = (body["access_token"], time.time() + int(body.get("expires_in", 300)))
        return self._token[0]

    def _call(self, method: str, path: str, body: dict | None = None, multipart_input: dict | None = None) -> dict:
        headers = {"Authorization": f"Bearer {self._token_value()}", "Accept": "application/json"}
        data = None
        if multipart_input is not None:
            boundary = "----precedent" + base64.b16encode(os.urandom(6)).decode()
            data = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"input\"\r\n"
                    f"Content-Type: application/json\r\n\r\n{json.dumps(multipart_input)}\r\n--{boundary}--\r\n").encode()
            headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
        elif body is not None:
            data = json.dumps(body).encode()
            headers["Content-Type"] = "application/json"
        status, resp = self._logged(method, path, headers=headers, data=data)
        if status >= 400:
            raise PayPalError(status, resp)
        return resp

    # ---- reads ----
    def get_dispute(self, dispute_id: str) -> dict:
        d = self._call("GET", f"/v1/customer/disputes/{urllib.parse.quote(dispute_id)}")
        return {
            "dispute_id": d.get("dispute_id"), "reason": d.get("reason"), "status": d.get("status"),
            "dispute_state": d.get("dispute_state"), "stage": d.get("dispute_life_cycle_stage"),
            "amount": d.get("dispute_amount"), "update_time": d.get("update_time"),
            "allowed": sorted(l.get("rel") for l in d.get("links", []) if l.get("rel") != "self"),
            "allowed_response_options": d.get("allowed_response_options"),
        }

    def list_disputes(self, page_size: int = 20) -> list[dict]:
        """Disputes on the connected sandbox account, newest first (summary fields only)."""
        return self._call("GET", f"/v1/customer/disputes?page_size={int(page_size)}").get("items", [])

    def dispute_details(self, dispute_id: str) -> dict:
        return self._call("GET", f"/v1/customer/disputes/{urllib.parse.quote(dispute_id)}")

    def trackers(self, transaction_id: str) -> list[dict]:
        """Shipment trackers the seller added to a transaction (Add Tracking API)."""
        q = urllib.parse.urlencode({"transaction_id": transaction_id})
        return self._call("GET", f"/v1/shipping/trackers?{q}").get("trackers", [])

    def real_allowed(self, atype: str) -> str | None:
        """Why a real call of this type may not be made on this deployment, or None."""
        if not self.configured:
            return "PayPal sandbox credentials are not configured."
        if not self.real_execution:
            return "real PayPal execution is switched off on this deployment (PRECEDENT_REAL_EXECUTION=0)."
        if self.real_types is not None and atype not in self.real_types:
            return (f"this public demo keeps {atype} simulated; it runs only "
                    f"{', '.join(sorted(self.real_types))} for real.")
        return None

    def _take_real_slot(self) -> bool:
        if not self.max_real_per_hour:
            return True
        with self._lock:
            now = time.time()
            while self._real_sent and now - self._real_sent[0] > 3600:
                self._real_sent.popleft()
            if len(self._real_sent) >= self.max_real_per_hour:
                return False
            self._real_sent.append(now)
            return True

    # ---- execution ----
    def execute(self, action: dict) -> dict:
        """Run one approved action. Returns {mode, detail, paypal_ref?}. Never raises for
        an action PayPal does not allow right now: that becomes a labelled simulation."""
        atype = action["type"]
        if atype == "FLAG_ONLY":
            return {"mode": "real", "detail": "Prepared internally. Nothing sent to PayPal."}
        dispute_ids = action["params"].get("dispute_ids") or []
        blocked = self.real_allowed(atype)
        if blocked:
            return self._sim(action, blocked)
        if not dispute_ids:
            return self._sim(action, "No real sandbox dispute is linked to this action (the order feed is synthetic).")
        results, sims = [], []
        for did in dispute_ids:
            try:
                live = self.get_dispute(did)  # re-check state right before executing
            except PayPalError as e:
                sims.append(f"{did}: could not read dispute ({e.status})")
                continue
            if ACTION_LINK.get(atype) not in live["allowed"]:
                sims.append(f"{did}: PayPal does not allow {atype} while the dispute is "
                            f"{live['dispute_state'] or live['status']}")
                continue
            if not self._take_real_slot():
                sims.append(f"{did}: this demo's limit of {self.max_real_per_hour} real PayPal actions an hour is reached")
                continue
            try:
                self._send(atype, did, action)
                results.append(did)
            except PayPalError as e:
                sims.append(f"{did}: PayPal refused ({', '.join(e.issues) or e.status})")
        if results:
            return {"mode": "real", "paypal_ref": ",".join(results),
                    "detail": f"Executed on sandbox dispute(s) {', '.join(results)}." +
                              (f" Simulated for: {'; '.join(sims)}." if sims else "")}
        return self._sim(action, "; ".join(sims))

    def _send(self, atype: str, did: str, action: dict) -> None:
        p = action["params"]
        path = f"/v1/customer/disputes/{urllib.parse.quote(did)}"
        if atype == "SEND_MESSAGE":
            self._call("POST", f"{path}/send-message", body={"message": p.get("message") or action.get("title", "Update on your order.")})
        elif atype == "PROVIDE_EVIDENCE":
            ev = {"evidence_type": p.get("evidence_type", "PROOF_OF_FULFILLMENT"), "notes": action.get("rationale", "")[:2000]}
            if p.get("tracking_info"):
                ev["evidence_info"] = {"tracking_info": p["tracking_info"]}
            self._call("POST", f"{path}/provide-evidence", multipart_input={"evidences": [ev]})
        elif atype == "MAKE_OFFER":
            amt = p["amount"]
            self._call("POST", f"{path}/make-offer", body={
                "note": action.get("title", "Offer"), "offer_type": p.get("offer_type", "REFUND"),
                "offer_amount": {"currency_code": amt["currency_code"], "value": f"{float(amt['value']):.2f}"}})
        elif atype == "ACCEPT_CLAIM":
            self._call("POST", f"{path}/accept-claim", body={"note": action.get("title", "Accepting claim")})
        else:
            raise PayPalError(400, {"name": f"unsupported action {atype}"})

    @staticmethod
    def _sim(action: dict, why: str) -> dict:
        return {"mode": "simulated", "detail": f"Simulated: {why}"}

    # ---- webhooks ----
    def verify_webhook(self, headers: dict, event: dict) -> bool:
        """Ask PayPal to verify. False means invalid; unavailable verification raises.

        Callers must retry on errors without recording the event as processed.
        """
        if not (self.configured and self.webhook_id):
            return False
        h = {k.lower(): v for k, v in headers.items()}
        body = {
            "auth_algo": h.get("paypal-auth-algo"), "cert_url": h.get("paypal-cert-url"),
            "transmission_id": h.get("paypal-transmission-id"), "transmission_sig": h.get("paypal-transmission-sig"),
            "transmission_time": h.get("paypal-transmission-time"), "webhook_id": self.webhook_id, "webhook_event": event,
        }
        if not all(body.values()):
            return False
        try:
            resp = self._call("POST", "/v1/notifications/verify-webhook-signature", body=body)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise PayPalError(503, {"name": "WEBHOOK_VERIFICATION_UNAVAILABLE"}) from exc
        if not isinstance(resp, dict) or resp.get("verification_status") not in ("SUCCESS", "FAILURE"):
            raise PayPalError(503, {"name": "WEBHOOK_VERIFICATION_UNAVAILABLE"})
        return resp.get("verification_status") == "SUCCESS"
