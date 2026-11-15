"""Validates agent output before anything is shown. A failed check blocks the result;
it is never silently 'fixed'."""
from __future__ import annotations

import re

from .base import AgentOutput, AnalysisInput

NUM_RE = re.compile(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?")


class GuardError(Exception):
    pass


def _numbers(text: str) -> list[float]:
    return [float(t.replace(",", "")) for t in NUM_RE.findall(text)]


def allowed_numbers(inp: AnalysisInput) -> set[float]:
    allowed: set[float] = set()
    for c in inp.calcs.values():
        v = abs(c.value)
        allowed.update({v, float(round(v)), round(v, 2), round(v, 1)})
    for v in inp.profile_summary.values():
        if isinstance(v, (int, float)):
            allowed.update({abs(float(v)), round(abs(float(v)), 2)})
    for d in inp.drafts:
        allowed.update(_numbers(str(d.facts)))
    return allowed


def check(inp: AnalysisInput, out: AgentOutput) -> None:
    errors = []
    if out.generated_by not in ("template", "llm"):
        errors.append("מקור הפלט לא מזוהה")
    want = [d.finding_id for d in inp.drafts]
    got = [f.finding_id for f in out.findings]
    if sorted(want) != sorted(got):
        errors.append(f"הממצאים שהוחזרו ({got}) אינם תואמים לממצאים שהוגדרו ({want})")
    allowed = allowed_numbers(inp)
    for f in out.findings:
        for field in ("title", "finding", "explanation", "next_step"):
            text = getattr(f, field)
            if not text or not text.strip():
                errors.append(f"{f.finding_id}: השדה {field} ריק")
                continue
            for n in _numbers(text):
                if not any(abs(n - a) < 0.006 for a in allowed):
                    errors.append(f"{f.finding_id}: המספר {n} בשדה {field} אינו מגובה בחישוב או בנתון")
    if errors:
        raise GuardError("; ".join(errors))
