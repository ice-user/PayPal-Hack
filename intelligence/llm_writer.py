"""Optional LLM prose writer for the Consultant (opt-in).

The rules engine decides everything: diagnosis, actions, amounts, citations,
confidence. This writer may only rephrase two prose fields (diagnosis_detail and
each action's rationale) so they read naturally. Its output is rejected, and the
rules text kept, when:
  - the SDK, credentials or opt-in flag are missing, or the call fails;
  - the model refuses or the reply is not valid against the schema;
  - the text contains any number that is not already in the rules draft or the
    situation (so it cannot invent a figure);
  - the text uses causal language ("caused", "will reduce", "guarantees").

Enable with PRECEDENT_LLM_WRITER=1 and Anthropic credentials (ANTHROPIC_API_KEY or an
`ant auth login` profile). Fixtures and the ablation never use it, so they stay
deterministic.
"""
from __future__ import annotations

import json
import os
import re
from typing import Callable

MODEL = "claude-opus-5-5"
NUM = re.compile(r"\d+(?:\.\d+)?")
CAUSAL = re.compile(r"\b(caused|causes|will (?:reduce|fix|stop|eliminate)|guarantee[sd]?|proven)\b", re.I)

SYSTEM = (
    "You rewrite short explanations for a dispute-management dashboard used by small online merchants. "
    "Keep every fact, number and case reference exactly as given; do not add new facts, numbers, "
    "forecasts or advice. Describe precedents as what was observed or followed, never as causes. "
    "Plain English, one or two sentences per field, no marketing tone."
)

SCHEMA = {
    "type": "object",
    "properties": {
        "diagnosis_detail": {"type": "string"},
        "rationales": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"action_id": {"type": "string"}, "rationale": {"type": "string"}},
                "required": ["action_id", "rationale"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["diagnosis_detail", "rationales"],
    "additionalProperties": False,
}


def _numbers(text: str) -> set[str]:
    return {n.rstrip("0").rstrip(".") if "." in n else n for n in NUM.findall(text)}


def guard(draft: dict, situation_text: str, out: dict) -> dict | None:
    """Return the writer output if it is safe, else None (keep the rules prose)."""
    allowed = _numbers(json.dumps(draft) + " " + situation_text)
    texts = [out.get("diagnosis_detail", "")] + [r.get("rationale", "") for r in out.get("rationales", [])]
    for t in texts:
        if not isinstance(t, str) or not t.strip():
            return None
        if not _numbers(t) <= allowed or CAUSAL.search(t):
            return None
    ids = {a["action_id"] for a in draft["actions"]}
    rationales = {r["action_id"]: r["rationale"] for r in out.get("rationales", []) if r.get("action_id") in ids}
    return {"diagnosis_detail": out["diagnosis_detail"], "rationales": rationales, "model": MODEL}


def make_writer(situation: dict, client=None) -> Callable[[dict], dict] | None:
    """Build a writer for this situation, or None when the LLM is not enabled."""
    if os.environ.get("PRECEDENT_LLM_WRITER") != "1" and client is None:
        return None
    if client is None:
        try:
            import anthropic
            client = anthropic.Anthropic()
        except Exception:  # noqa: BLE001 - SDK missing or no credentials: stay on rules prose
            return None
    situation_text = json.dumps(situation.get("features", {})) + " " + situation.get("narrative", "")

    def writer(draft: dict) -> dict:
        payload = {
            "situation_narrative": situation.get("narrative", ""),
            "diagnosis": draft["diagnosis"],
            "diagnosis_detail": draft.get("diagnosis_detail", ""),
            "actions": [{"action_id": a["action_id"], "title": a.get("title", ""), "rationale": a["rationale"],
                         "cited_cases": a["supporting_cases"]} for a in draft["actions"]],
        }
        try:
            response = client.messages.create(
                model=MODEL,
                max_tokens=2000,
                system=SYSTEM,
                output_config={"effort": "low", "format": {"type": "json_schema", "schema": SCHEMA}},
                messages=[{"role": "user", "content": "Rewrite the prose fields of this plan:\n" + json.dumps(payload)}],
            )
        except Exception:  # noqa: BLE001 - any API failure keeps the rules prose
            return {}
        if getattr(response, "stop_reason", None) != "end_turn":
            return {}  # refusal, max_tokens or anything unexpected
        text = next((b.text for b in response.content if getattr(b, "type", "") == "text"), "")
        try:
            out = json.loads(text)
        except ValueError:
            return {}
        return guard(draft, situation_text, out) or {}

    return writer
