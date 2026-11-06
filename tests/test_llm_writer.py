"""The LLM writer may rephrase prose only; anything unsafe falls back to the rules text.
No network: the Anthropic client is faked."""
import json
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from intelligence.cases import load_cases, usable  # noqa: E402
from intelligence.consultant import recommend  # noqa: E402
from intelligence.llm_writer import make_writer  # noqa: E402
from intelligence.retrieve_baseline import retrieve  # noqa: E402

SIT = json.loads((ROOT / "contracts" / "fixtures" / "situations" / "A.json").read_text(encoding="utf-8"))


class FakeClient:
    def __init__(self, reply: dict | None, stop_reason="end_turn", raise_exc=False):
        self.reply, self.stop_reason, self.raise_exc, self.calls = reply, stop_reason, raise_exc, 0
        self.messages = self

    def create(self, **kwargs):
        self.calls += 1
        assert kwargs["model"] == "claude-opus-5-5"
        assert kwargs["output_config"]["format"]["type"] == "json_schema"
        if self.raise_exc:
            raise RuntimeError("network down")
        return SimpleNamespace(stop_reason=self.stop_reason,
                               content=[SimpleNamespace(type="text", text=json.dumps(self.reply))])


def plain():
    return recommend(SIT, retrieve(SIT, usable(load_cases()), k=6))


def run(client):
    return recommend(SIT, retrieve(SIT, usable(load_cases()), k=6), writer=make_writer(SIT, client=client))


def reply_for(rec, detail, rationale="Similar merchants followed this step when one carrier was at fault."):
    return {"diagnosis_detail": detail, "rationales": [{"action_id": a["action_id"], "rationale": rationale} for a in rec["actions"]]}


def test_safe_rewrite_is_applied_and_labelled():
    base = plain()
    r = run(FakeClient(reply_for(base, "Most disputes sit on one carrier while orders still ship on time.")))
    assert r["generated_by"]["engine"] == "llm" and r["diagnosis_detail"].startswith("Most disputes")
    assert [a["type"] for a in r["actions"]] == [a["type"] for a in base["actions"]]
    assert [a["params"] for a in r["actions"]] == [a["params"] for a in base["actions"]]


def test_invented_number_is_rejected():
    base = plain()
    r = run(FakeClient(reply_for(base, "Fixing this will cut disputes by 63% within a week.")))
    assert r == base


def test_causal_language_is_rejected():
    base = plain()
    r = run(FakeClient(reply_for(base, "The carrier caused these disputes.")))
    assert r == base


def test_refusal_and_errors_keep_rules_prose():
    base = plain()
    assert run(FakeClient(reply_for(base, "Fine text."), stop_reason="refusal")) == base
    assert run(FakeClient(None, raise_exc=True)) == base


def test_disabled_without_opt_in(monkeypatch):
    monkeypatch.delenv("PRECEDENT_LLM_WRITER", raising=False)
    assert make_writer(SIT) is None
