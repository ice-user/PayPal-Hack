"""Load the shared JSON schemas from /contracts and validate documents against them."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parent.parent
CONTRACTS = ROOT / "contracts"
SCHEMAS = CONTRACTS / "schemas"

SCHEMA_FILES = {
    "situation": "situation_record.schema.json",
    "recommendation": "recommendation.schema.json",
    "policy_decision": "policy_decision.schema.json",
    "case": "case.schema.json",
    "bundle": "bundle.schema.json",
}


@lru_cache(maxsize=1)
def _registry() -> Registry:
    resources = []
    for fname in SCHEMA_FILES.values():
        doc = json.loads((SCHEMAS / fname).read_text(encoding="utf-8"))
        res = Resource.from_contents(doc)
        resources.append((fname, res))
        resources.append((doc["$id"], res))
    return Registry().with_resources(resources)


@lru_cache(maxsize=None)
def validator(kind: str) -> Draft202012Validator:
    doc = json.loads((SCHEMAS / SCHEMA_FILES[kind]).read_text(encoding="utf-8"))
    return Draft202012Validator(doc, registry=_registry())


def errors(kind: str, obj: dict) -> list[str]:
    """Return human-readable validation errors (empty list means valid)."""
    out = []
    for e in sorted(validator(kind).iter_errors(obj), key=lambda e: list(e.absolute_path)):
        where = "/".join(str(p) for p in e.absolute_path) or "(root)"
        out.append(f"{where}: {e.message}")
    return out


def validate(kind: str, obj: dict) -> None:
    errs = errors(kind, obj)
    if errs:
        raise ValueError(f"{kind} failed schema validation:\n  " + "\n  ".join(errs[:20]))


@lru_cache(maxsize=1)
def thresholds() -> dict:
    return json.loads((CONTRACTS / "thresholds.json").read_text(encoding="utf-8"))
