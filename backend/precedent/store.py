"""SQLite persistence: actions (executor state), audit log, outcomes, webhook replay guard,
and live_simulated cases awaiting review. Swappable for Postgres later."""
from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_DB = Path(__file__).resolve().parents[1] / "data" / "precedent.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS actions (
  idempotency_key TEXT PRIMARY KEY,
  recommendation_id TEXT NOT NULL,
  action_id TEXT NOT NULL,
  type TEXT NOT NULL,
  params TEXT NOT NULL,
  decision TEXT NOT NULL,
  state TEXT NOT NULL,
  execution_mode TEXT,
  paypal_ref TEXT,
  detail TEXT,
  approved_at TEXT,
  updated_at TEXT NOT NULL,
  UNIQUE (recommendation_id, action_id)
);
CREATE TABLE IF NOT EXISTS audit_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  at TEXT NOT NULL, actor TEXT NOT NULL, event TEXT NOT NULL, payload TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS outcomes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  recommendation_id TEXT NOT NULL, metric TEXT NOT NULL,
  before REAL, after REAL, horizon_days INTEGER, measured_at TEXT NOT NULL, simulated INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS webhook_events (
  transmission_id TEXT PRIMARY KEY, event_type TEXT, received_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS pending_cases (
  case_id TEXT PRIMARY KEY, body TEXT NOT NULL, created_at TEXT NOT NULL
);
"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Store:
    def __init__(self, path: Path | str = DEFAULT_DB):
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self.db = sqlite3.connect(str(path), check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)

    # ---- audit ----
    def audit(self, actor: str, event: str, payload: dict) -> None:
        with self._lock, self.db:
            self.db.execute("INSERT INTO audit_log (at, actor, event, payload) VALUES (?,?,?,?)",
                            (now(), actor, event, json.dumps(payload)))

    def audit_tail(self, limit: int = 50) -> list[dict]:
        rows = self.db.execute("SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r, payload=json.loads(r["payload"])) for r in rows]

    # ---- actions ----
    def get_action(self, rec_id: str, action_id: str) -> dict | None:
        r = self.db.execute("SELECT * FROM actions WHERE recommendation_id=? AND action_id=?",
                            (rec_id, action_id)).fetchone()
        return None if r is None else dict(r, params=json.loads(r["params"]))

    def actions_for(self, rec_id: str) -> list[dict]:
        rows = self.db.execute("SELECT * FROM actions WHERE recommendation_id=?", (rec_id,)).fetchall()
        return [dict(r, params=json.loads(r["params"])) for r in rows]

    def insert_action(self, row: dict) -> bool:
        """Insert once. Returns False if the idempotency key already exists."""
        try:
            with self._lock, self.db:
                self.db.execute(
                    "INSERT INTO actions (idempotency_key, recommendation_id, action_id, type, params, decision, state,"
                    " updated_at) VALUES (?,?,?,?,?,?,?,?)",
                    (row["idempotency_key"], row["recommendation_id"], row["action_id"], row["type"],
                     json.dumps(row["params"]), row["decision"], row["state"], now()))
            return True
        except sqlite3.IntegrityError:
            return False

    def transition(self, key: str, frm: tuple[str, ...], to: str, **fields) -> bool:
        """Compare-and-set state change. Returns False if the action was not in an allowed state."""
        sets = ", ".join(f"{k}=?" for k in fields)
        sql = f"UPDATE actions SET state=?, updated_at=?{', ' + sets if sets else ''} WHERE idempotency_key=? AND state IN ({','.join('?' * len(frm))})"
        with self._lock, self.db:
            cur = self.db.execute(sql, (to, now(), *fields.values(), key, *frm))
        return cur.rowcount == 1

    def count_executed_since(self, since_iso: str) -> int:
        return self.db.execute("SELECT COUNT(*) FROM actions WHERE approved_at >= ? AND state IN"
                               " ('EXECUTING','SUCCEEDED','FAILED')", (since_iso,)).fetchone()[0]

    # ---- outcomes ----
    def add_outcome(self, rec_id: str, metric: str, before: float, after: float, horizon: int, simulated: bool) -> None:
        with self._lock, self.db:
            self.db.execute("INSERT INTO outcomes (recommendation_id, metric, before, after, horizon_days, measured_at,"
                            " simulated) VALUES (?,?,?,?,?,?,?)", (rec_id, metric, before, after, horizon, now(), int(simulated)))

    def outcomes_for(self, rec_id: str) -> list[dict]:
        rows = self.db.execute("SELECT * FROM outcomes WHERE recommendation_id=? ORDER BY id", (rec_id,)).fetchall()
        return [dict(r, simulated=bool(r["simulated"])) for r in rows]

    # ---- webhooks ----
    def seen_webhook(self, transmission_id: str, event_type: str) -> bool:
        """Record a webhook; return True if it was already processed (replay)."""
        try:
            with self._lock, self.db:
                self.db.execute("INSERT INTO webhook_events VALUES (?,?,?)", (transmission_id, event_type, now()))
            return False
        except sqlite3.IntegrityError:
            return True

    # ---- demo reset ----
    def reset_demo(self) -> None:
        """Clear actions, outcomes and pending cases so the demo can be run again.
        The audit log is kept (and records the reset)."""
        with self._lock, self.db:
            self.db.execute("DELETE FROM actions")
            self.db.execute("DELETE FROM outcomes")
            self.db.execute("DELETE FROM pending_cases")

    # ---- pending cases ----
    def add_pending_case(self, case: dict) -> None:
        with self._lock, self.db:
            self.db.execute("INSERT OR REPLACE INTO pending_cases VALUES (?,?,?)",
                            (case["case_id"], json.dumps(case), now()))

    def pending_cases(self) -> list[dict]:
        """All live_simulated cases recorded by the outcome tracker, whatever their review status."""
        return [json.loads(r["body"]) for r in self.db.execute("SELECT body FROM pending_cases ORDER BY created_at")]

    def review_case(self, case_id: str, decision: str) -> dict | None:
        row = self.db.execute("SELECT body FROM pending_cases WHERE case_id=?", (case_id,)).fetchone()
        if row is None:
            return None
        case = json.loads(row["body"])
        case["review_status"] = decision
        case["tags"] = [t for t in case.get("tags", []) if t != "pending_review"] + [f"review_{decision}"]
        with self._lock, self.db:
            self.db.execute("UPDATE pending_cases SET body=? WHERE case_id=?", (json.dumps(case), case_id))
        return case
