"""Load and validate the case library from /cases (any *.json file holding one case or a list)."""
from __future__ import annotations

import json
from pathlib import Path

from .schema import ROOT, errors

CASES_DIR = ROOT / "cases"


def load_cases(directory: Path = CASES_DIR, *, strict: bool = True) -> list[dict]:
    cases: list[dict] = []
    for path in sorted(directory.rglob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        for case in data if isinstance(data, list) else [data]:
            errs = errors("case", case)
            if errs and strict:
                raise ValueError(f"{path.name} {case.get('case_id')}: " + "; ".join(errs[:5]))
            if not errs:
                cases.append(case)
    ids = [c["case_id"] for c in cases]
    dupes = {i for i in ids if ids.count(i) > 1}
    if dupes:
        raise ValueError(f"duplicate case ids: {sorted(dupes)}")
    return cases


def usable(cases: list[dict]) -> list[dict]:
    """Only approved cases are retrievable. Pending live_simulated cases wait for review."""
    return [c for c in cases if c["review_status"] == "approved"]
