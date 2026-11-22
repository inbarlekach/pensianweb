"""Explicit, deterministic decision rules. The AI layer never decides certainty, risk,
ranking or money amounts — it only words what these rules produced."""
from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from datetime import date
from typing import Optional

from .calc.fees import FeeTerms
from .calc.scenarios import Comparison, compare
from .models import CalcResult, Certainty, Profile, Risk


class AnalysisError(Exception):
    """Raised when the analysis cannot produce a trustworthy result. Never swallowed."""


# --- input checks ---------------------------------------------------------------

def check_profile(p: Profile, caps: dict[str, float]) -> list[str]:
    """Consistency problems that make a fee analysis meaningless. Empty list = OK."""
    problems = []
    if p.planned_retirement_age <= p.age:
        problems.append("גיל הפרישה המתוכנן אינו גבוה מהגיל הנוכחי")
    if p.deposit_fee_pct > caps["deposit"]:
        problems.append(f"דמי ניהול מההפקדות ({p.deposit_fee_pct}%) גבוהים מהתקרה החוקית ({caps['deposit']}%) – ייתכן שהנתון שגוי")
    if p.accumulation_fee_pct > caps["accumulation"]:
        problems.append(f"דמי ניהול מהצבירה ({p.accumulation_fee_pct}%) גבוהים מהתקרה החוקית ({caps['accumulation']}%) – ייתכן שהנתון שגוי")
    if p.spouse_age is not None and p.spouse_age < 0:
        problems.append("גיל בן/בת הזוג שלילי")
    return problems


def months_lag(report_period: int, today: date) -> int:
    y, m = divmod(report_period, 100)
    return (today.year * 12 + today.month) - (y * 12 + m)


def market_status(manifest: Optional[dict], snapshot: Optional[dict], today: date,
                  max_age_months: int) -> dict:
    """Describes the market data state. `usable` False => no numeric comparison."""
    st = {"usable": False, "stale": False, "last_refresh_failed": False, "messages": []}
    if manifest and manifest.get("last_attempt", {}).get("status") == "failed":
        st["last_refresh_failed"] = True
        st["messages"].append(f"ניסיון הרענון האחרון ({manifest['last_attempt'].get('at')}) נכשל; מוצגים הנתונים מהאיסוף המוצלח הקודם.")
    if not snapshot:
        st["messages"].append("אין נתוני שוק זמינים. לא ניתן לבצע השוואה.")
        return st
    period = snapshot.get("latest_report_period")
    if not isinstance(period, int):
        st["messages"].append("לנתוני השוק אין תקופת דיווח תקינה.")
        return st
    lag = months_lag(period, today)
    st.update(report_period=period, lag_months=lag, collected_at=snapshot.get("collected_at"))
    if lag < 0:
        st["messages"].append("תקופת הדיווח בנתוני השוק מאוחרת מהתאריך הנוכחי – נתונים לא עקביים.")
        return st
    if lag > max_age_months:
        st["stale"] = True
        st["messages"].append(f"נתוני השוק מתייחסים לתקופה {period}, לפני {lag} חודשים – ישנים מהסף שהוגדר ({max_age_months}).")
    comparable = [f for f in snapshot.get("funds", []) if f.get("comparable")]
    if not comparable:
        st["messages"].append("אין בנתוני השוק קרנות ברות-השוואה.")
        return st
    st["usable"] = True
    return st


# --- comparison & findings ------------------------------------------------------

@dataclass
class Alternative:
    key: str
    fund: dict
    terms: FeeTerms
    comparison: Comparison


@dataclass
class FindingDraft:
    """Everything decided by code. The agent adds only wording."""
    finding_id: str
    kind: str  # "fee_gap_negotiate" | "fee_gap_switch" | "verify_fees" | "no_material_gap" | "insufficient"
    certainty: Certainty
    risk: Risk
    calc_refs: list[str]
    source_refs: list[str]
    facts: dict
    assumptions: list[str]
    limitations: list[str]
    ranking_value_ils: Optional[float] = None


@dataclass
class RuleOutput:
    calcs: dict[str, CalcResult] = field(default_factory=dict)
    alternatives: list[Alternative] = field(default_factory=list)
    median: Optional[Alternative] = None
    drafts: list[FindingDraft] = field(default_factory=list)
    market_context: dict = field(default_factory=dict)


def _r(x: float, nd: int = 0) -> float:
    return round(x, nd)


def build(profile: Profile, assumptions: dict, snapshot: dict, mstatus: dict,
          source_id: str) -> RuleOutput:
    out = RuleOutput()
    scen = {k: assumptions["scenarios"][k]["annual_real_return"]
            for k in ("conservative", "central", "optimistic")}
    rate = assumptions["contribution_rate"]["value"]
    growth = assumptions["salary_growth_real_annual"]["value"]
    threshold = assumptions["materiality_threshold_first_year_ils"]["value"]
    current = FeeTerms(profile.deposit_fee_pct, profile.accumulation_fee_pct)

    common_assumptions = [
        f"שיעור הפקדה {rate * 100:.1f}% מהשכר ברוטו (הנחה)",
        f"צמיחת שכר ריאלית {growth * 100:.1f}% לשנה (הנחה)",
        "תשואה ריאלית לפי שלושה תרחישים (הנחה, לא תחזית)",
        "דמי ניהול מהצבירה נגבים חודשית כ-1/12 מהשיעור השנתי (הנחת מודל)",
        "דמי הניהול נשארים קבועים עד הפרישה (הנחה)",
    ]
    avg_limit = "נתון השוק הוא ממוצע שנגבה בפועל בקרן – לא הצעה עבורך. התנאים שתקבל בפועל עשויים להיות שונים."

    def add(c: CalcResult):
        out.calcs[c.calc_id] = c

    add(CalcResult(calc_id="cur_dep", label="דמי ניהול מההפקדות (נוכחי)", value=profile.deposit_fee_pct,
                   unit="pct", kind="fact", formula="נתון פרופיל"))
    add(CalcResult(calc_id="cur_acc", label="דמי ניהול מהצבירה (נוכחי)", value=profile.accumulation_fee_pct,
                   unit="pct", kind="fact", formula="נתון פרופיל"))

    if not mstatus["usable"] or mstatus["stale"]:
        out.drafts.append(FindingDraft(
            finding_id="F-insufficient", kind="insufficient", certainty=Certainty.INSUFFICIENT,
            risk=Risk.LOW, calc_refs=["cur_dep", "cur_acc"], source_refs=[source_id] if snapshot else [],
            facts={"reasons": mstatus["messages"]}, assumptions=[],
            limitations=mstatus["messages"]))
        return out

    funds = [f for f in snapshot["funds"] if f.get("comparable")]
    kw = dict(age=profile.age, retirement_age=profile.planned_retirement_age,
              salary=profile.gross_monthly_salary, balance=profile.accumulated_balance,
              contribution_rate=rate, salary_growth=growth, scenario_returns=scen)

    alts = []
    for i, f in enumerate(funds):
        t = FeeTerms(f["deposit_fee_pct"], f["accumulation_fee_pct"])
        alts.append(Alternative(f"m{i}", f, t, compare(current=current, alternative=t, **kw)))
    alts.sort(key=lambda a: -a.comparison.by_name("central").gap_at_retirement)

    # Median fund by computed total cost for this profile (a real fund, not a synthetic mix).
    med = alts[len(alts) // 2]
    out.median = med
    cheaper = sum(1 for a in alts if a.comparison.by_name("central").gap_at_retirement > 0)
    above_all = cheaper == len(alts)
    # Plain-language verdict level, decided by code from the computed total cost for this profile.
    if above_all:
        verdict = "higher_than_all"
    elif cheaper * 2 >= len(alts):
        verdict = "higher_than_most"
    elif cheaper > 0:
        verdict = "mixed"
    else:
        verdict = "lower"
    out.market_context = {
        "verdict": verdict,
        "funds_cheaper_than_you": cheaper,
        "funds_compared": len(alts),
        "deposit_fee_median": statistics.median(f["deposit_fee_pct"] for f in funds),
        "accumulation_fee_median": statistics.median(f["accumulation_fee_pct"] for f in funds),
        "deposit_fee_range": [min(f["deposit_fee_pct"] for f in funds), max(f["deposit_fee_pct"] for f in funds)],
        "accumulation_fee_range": [min(f["accumulation_fee_pct"] for f in funds), max(f["accumulation_fee_pct"] for f in funds)],
        "costlier_than_all": above_all,
        "report_period": mstatus["report_period"],
    }
    add(CalcResult(calc_id="monthly_deposit", label="הפקדה חודשית משוערת",
                   value=_r(alts[0].comparison.monthly_deposit, 2), unit="ILS", kind="estimate",
                   formula=f"שכר ברוטו × {rate}"))
    c0 = alts[0].comparison
    y1_formula = "סימולציה חודשית של 12 החודשים הקרובים, תרחיש מרכזי, בתנאים הנוכחיים"
    add(CalcResult(calc_id="cur_y1_dep_fees", label="דמי ניהול מההפקדות בשנה הקרובה (נוכחי)",
                   value=_r(c0.first_year_current_deposit_fees), unit="ILS", kind="estimate", formula=y1_formula))
    add(CalcResult(calc_id="cur_y1_acc_fees", label="דמי ניהול מהצבירה בשנה הקרובה (נוכחי)",
                   value=_r(c0.first_year_current_accumulation_fees), unit="ILS", kind="estimate", formula=y1_formula))
    add(CalcResult(calc_id="cur_y1_total_fees", label="סך דמי הניהול בשנה הקרובה (נוכחי)",
                   value=_r(c0.first_year_current_deposit_fees) + _r(c0.first_year_current_accumulation_fees),
                   unit="ILS", kind="estimate",
                   formula="דמי ניהול מההפקדות + דמי ניהול מהצבירה (מעוגלים לשקל, כך שהסכום תואם את הרכיבים שמוצגים)"))
    add(CalcResult(calc_id="cur_dep_per_1000", label="דמי ניהול מכל 1,000 ₪ שמופקדים",
                   value=round(profile.deposit_fee_pct * 10, 2), unit="ILS", kind="fact",
                   formula="אחוז דמי הניהול מההפקדות × 1,000"))
    add(CalcResult(calc_id="cur_acc_per_100k", label="דמי ניהול בשנה מכל 100,000 ₪ צבירה",
                   value=round(profile.accumulation_fee_pct * 1000, 2), unit="ILS", kind="fact",
                   formula="אחוז דמי הניהול מהצבירה × 100,000"))

    def register(a: Alternative, prefix: str):
        f = a.fund
        add(CalcResult(calc_id=f"{prefix}_dep", label=f"דמי ניהול ממוצעים מההפקדות – {f['parent_company']}",
                       value=f["deposit_fee_pct"], unit="pct", kind="fact", formula=f"פנסיה-נט, תקופה {f['report_period']}"))
        add(CalcResult(calc_id=f"{prefix}_acc", label=f"דמי ניהול ממוצעים מהצבירה – {f['parent_company']}",
                       value=f["accumulation_fee_pct"], unit="pct", kind="fact", formula=f"פנסיה-נט, תקופה {f['report_period']}"))
        add(CalcResult(calc_id=f"{prefix}_y1", label="חיסכון משוער בדמי ניהול בשנה הראשונה",
                       value=_r(a.comparison.first_year_fee_saving), unit="ILS", kind="estimate",
                       formula="סימולציה חודשית 12 חודשים, תרחיש מרכזי: דמי ניהול נוכחיים − חלופיים"))
        for s in a.comparison.scenarios:
            add(CalcResult(calc_id=f"{prefix}_gap_{s.scenario}", label=f"פער מצטבר בצבירה בגיל {profile.planned_retirement_age} ({assumptions['scenarios'][s.scenario]['label']})",
                           value=_r(s.gap_at_retirement), unit="ILS", kind="estimate",
                           formula="צבירה בגיל הפרישה בתנאים החלופיים − בתנאים הנוכחיים"))

    out.alternatives = alts[:3]
    for i, a in enumerate(out.alternatives, 1):
        register(a, f"alt{i}")
    register(med, "median")

    best = out.alternatives[0]
    best_y1 = best.comparison.first_year_fee_saving
    if best_y1 < threshold:
        out.drafts.append(FindingDraft(
            finding_id="F-no-gap", kind="no_material_gap", certainty=Certainty.INDICATION, risk=Risk.LOW,
            calc_refs=["cur_dep", "cur_acc", "alt1_y1"], source_refs=[source_id],
            facts={"threshold": threshold}, assumptions=common_assumptions, limitations=[avg_limit]))
        return out

    src = [source_id]
    # Negotiation target = the median fund's average terms; only if that is itself material.
    if med.comparison.first_year_fee_saving >= threshold:
      out.drafts.append(FindingDraft(
        finding_id="F-negotiate", kind="fee_gap_negotiate", certainty=Certainty.INDICATION, risk=Risk.LOW,
        calc_refs=["cur_dep", "cur_acc", "median_dep", "median_acc", "median_y1",
                   "median_gap_conservative", "median_gap_central", "median_gap_optimistic"],
        source_refs=src,
        facts={"median_fund": med.fund["parent_company"], "costlier_than_all": above_all,
               "funds_compared": len(alts)},
        assumptions=common_assumptions,
        limitations=[avg_limit, "לא ידוע אם הקרן הנוכחית שלך תסכים להפחתה."],
        ranking_value_ils=_r(med.comparison.by_name("central").gap_at_retirement)))
    out.drafts.append(FindingDraft(
        finding_id="F-verify", kind="verify_fees", certainty=Certainty.INDICATION, risk=Risk.LOW,
        calc_refs=["cur_dep", "cur_acc"], source_refs=[],
        facts={}, assumptions=[],
        limitations=["דמי הניהול בפרופיל הם נתוני הדגמה ולא נבדקו מול דוח אמיתי."],
        ranking_value_ils=None))
    for i, a in enumerate(out.alternatives, 1):
        out.drafts.append(FindingDraft(
            finding_id=f"F-switch-{i}", kind="fee_gap_switch", certainty=Certainty.INDICATION, risk=Risk.HIGH,
            calc_refs=["cur_dep", "cur_acc", f"alt{i}_dep", f"alt{i}_acc", f"alt{i}_y1",
                       f"alt{i}_gap_conservative", f"alt{i}_gap_central", f"alt{i}_gap_optimistic"],
            source_refs=src,
            facts={"fund": a.fund["parent_company"]},
            assumptions=common_assumptions,
            limitations=[avg_limit,
                         "מעבר קרן עשוי להשפיע על הכיסוי הביטוחי (נכות ושארים) ועל תקופות אכשרה – לא נבדק בגרסה זו.",
                         "ההשוואה מתייחסת לדמי ניהול בלבד, לא לתשואות, לשירות או לאיתנות הקרן."],
            ranking_value_ils=_r(a.comparison.by_name("central").gap_at_retirement)))
    return out


RISK_ORDER = {Risk.LOW: 0, Risk.HIGH: 1}


def rank(items: list) -> list:
    """Risk first (low before high); within a level, larger money value first; findings
    without a money value come last within their level. Works on objects with `.risk`
    and `.ranking_value_ils`."""
    return sorted(items, key=lambda d: (RISK_ORDER[d.risk],
                                        0 if d.ranking_value_ils is not None else 1,
                                        -(d.ranking_value_ils or 0)))
