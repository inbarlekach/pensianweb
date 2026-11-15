"""Plain-code pipeline: load → check → calculate → agent → guard → rank.
Every step is recorded; any failure stops the pipeline and is reported as a failure."""
from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import ValidationError

from . import rules
from .agents.base import AnalysisInput, DraftIn, FeeAnalystAgent
from .agents.guard import GuardError, check
from .models import Finding, Profile

SOURCE_ID = "pensianet_2024_now"


def field_label(key: str) -> str:
    from .intake import BY_KEY
    return BY_KEY[key].label if key in BY_KEY else key
PROFILE_KEYS = ("age", "gross_monthly_salary", "accumulated_balance", "accumulation_fee_pct",
                "deposit_fee_pct", "planned_retirement_age")


def run(profile_raw: dict, assumptions: dict, manifest: Optional[dict], snapshot: Optional[dict],
        agent: FeeAnalystAgent, today: date) -> dict:
    steps: list[dict] = []

    def step(name: str, status: str, detail: str = ""):
        steps.append({"step": name, "status": status, "detail": detail})

    def fail(msg: str, kind: str = "failed"):
        return {"status": kind, "error": msg, "steps": steps, "findings": [], "action_plan": []}

    # 1. profile
    try:
        profile = Profile.model_validate(profile_raw)
    except ValidationError as e:
        keys = [".".join(map(str, er["loc"])) for er in e.errors()]
        labels = ", ".join(field_label(k) for k in keys)
        step("בדיקת פרופיל", "failed", f"שדות חסרים או לא תקינים: {labels}")
        out = fail("נתוני הפרופיל חסרים או לא תקינים: " + labels, "invalid_input")
        out["invalid_fields"] = keys
        return out
    caps = {k: assumptions["legal_fee_caps_pct"][k] for k in ("deposit", "accumulation")}
    problems = rules.check_profile(profile, caps)
    if problems:
        step("בדיקת פרופיל", "failed", "; ".join(problems))
        return fail("נתוני הפרופיל אינם עקביים: " + "; ".join(problems), "invalid_input")
    step("בדיקת פרופיל", "ok", "כל השדות הנדרשים קיימים ועקביים")

    # 2. market data
    mstatus = rules.market_status(manifest, snapshot, today,
                                  assumptions["market_data_max_age_months"]["value"])
    if mstatus["usable"] and not mstatus["stale"]:
        step("טעינת נתוני שוק", "ok",
             f"פנסיה-נט, תקופה {mstatus['report_period']}, נאסף {str(mstatus.get('collected_at') or '')[:10]}")
    else:
        step("טעינת נתוני שוק", "warning", " ".join(mstatus["messages"]))

    # 3. calculation & rules
    try:
        ro = rules.build(profile, assumptions, snapshot or {}, mstatus, SOURCE_ID)
    except (ValueError, KeyError) as e:
        step("חישוב", "failed", str(e))
        return fail(f"החישוב נכשל: {e}")
    step("חישוב", "ok", f"{len(ro.calcs)} ערכים חושבו בקוד, {len(ro.drafts)} ממצאים הוגדרו לפי כללים")

    # 4. agent
    inp = AnalysisInput(
        profile_summary={k: getattr(profile, k) for k in PROFILE_KEYS},
        calcs=ro.calcs,
        drafts=[DraftIn(finding_id=d.finding_id, kind=d.kind, certainty=int(d.certainty), risk=d.risk.value,
                        calc_refs=d.calc_refs, source_refs=d.source_refs, facts=d.facts) for d in ro.drafts],
        source_ids=[SOURCE_ID])
    try:
        out = agent.analyze(inp)
    except Exception as e:  # provider failure must surface, not be hidden
        step("ניסוח ממצאים", "failed", f"{type(e).__name__}: {e}")
        return fail("שלב ניסוח הממצאים נכשל. לא מוצגות תוצאות חלקיות.")
    step("ניסוח ממצאים", "ok", f"ספק: {out.provider} ({'טקסט תבנית' if out.generated_by == 'template' else 'מודל AI'})")

    # 5. guard
    try:
        check(inp, out)
    except GuardError as e:
        step("אימות פלט", "failed", str(e))
        return fail("פלט הניסוח לא עבר אימות (מספר או ממצא שאינו מגובה בנתונים). לא מוצגות תוצאות.")
    step("אימות פלט", "ok", "כל המספרים בטקסט מגובים בחישובים או בנתונים")

    # 6. merge & rank
    words = {w.finding_id: w for w in out.findings}
    findings = [Finding(finding_id=d.finding_id, title=words[d.finding_id].title,
                        finding=words[d.finding_id].finding, explanation=words[d.finding_id].explanation,
                        next_step=words[d.finding_id].next_step, certainty=d.certainty, risk=d.risk,
                        calc_refs=d.calc_refs, source_refs=d.source_refs, assumptions=d.assumptions,
                        limitations=d.limitations, ranking_value_ils=d.ranking_value_ils,
                        generated_by=out.generated_by) for d in ro.drafts]
    ranked = rules.rank(findings)
    step("דירוג", "ok", "לפי רמת סיכון, ובתוך כל רמה לפי הפער המצטבר בתרחיש המרכזי")

    status = "insufficient" if any(f.finding_id == "F-insufficient" for f in findings) else "ok"
    scenarios = None
    if ro.alternatives:
        best = ro.alternatives[0]
        scenarios = {
            "compared_fund": best.fund["parent_company"],
            "start_age": profile.age,
            "items": [{
                "scenario": s.scenario,
                "label": assumptions["scenarios"][s.scenario]["label"],
                "annual_real_return": s.annual_return,
                "current_final": round(s.current_final),
                "alternative_final": round(s.alternative_final),
                "gap": round(s.gap_at_retirement),
                "current_yearly": [round(x) for x in s.current_yearly],
                "alternative_yearly": [round(x) for x in s.alternative_yearly],
            } for s in best.comparison.scenarios],
        }
    return {
        "status": status,
        "steps": steps,
        "generated_by": out.generated_by,
        "market": {**{k: v for k, v in mstatus.items() if k != "usable"}, "usable": mstatus["usable"],
                   "context": ro.market_context,
                   "funds": (snapshot or {}).get("funds", []),
                   "coverage": (snapshot or {}).get("coverage")},
        "calcs": {k: v.model_dump() for k, v in ro.calcs.items()},
        "findings": [f.model_dump(mode="json") for f in ranked],
        "action_plan": [{"finding_id": f.finding_id, "title": f.title, "risk": f.risk.value,
                         "value_ils": f.ranking_value_ils} for f in ranked if f.finding_id != "F-insufficient"],
        "scenarios": scenarios,
    }
