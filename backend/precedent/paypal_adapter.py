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
import time
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

    def _token_value(self) -> str:
        if self._token and self._token[1] > time.time() + 60:
            return self._token[0]
        basic = base64.b64encode(f"{self.client_id}:{self._secret}".encode()).decode()
        status, body = self._transport("POST", "/v1/oauth2/token", headers={
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
        status, resp = self._transport(method, path, headers=headers, data=data)
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

    # ---- execution ----
    def execute(self, action: dict) -> dict:
        """Run one approved action. Returns {mode, detail, paypal_ref?}. Never raises for
        an action PayPal does not allow right now: that becomes a labelled simulation."""
        atype = action["type"]
        if atype == "FLAG_ONLY":
            return {"mode": "real", "detail": "Prepared internally. Nothing sent to PayPal."}
        dispute_ids = action["params"].get("dispute_ids") or []
        if not self.configured:
            return self._sim(action, "PayPal sandbox credentials are not configured.")
        if not self.real_execution:
            return self._sim(action, "real PayPal execution is switched off on this deployment (PRECEDENT_REAL_EXECUTION=0).")
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
        """Ask PayPal to verify the signature. False on any doubt."""
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
        except PayPalError:
            return False
        return resp.get("verification_status") == "SUCCESS"
