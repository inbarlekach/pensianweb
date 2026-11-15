"""Pipeline, rules, market parsing and guard tests (categories 02–05, 07–10)."""
from datetime import date

import pytest

from app.agents.base import AgentOutput
from app.agents.mock_provider import TemplateAgent
from app.calc.fees import FeeTerms
from app.calc.scenarios import compare
from app.market import parse_records
from app.rules import months_lag

from .helpers import (CAPS, DROP, TODAY, analyze, assumptions, fund, profile, rec, snapshot)

SCN = pytest.mark.cat("02 תחזית שלושה תרחישים")
SEN = pytest.mark.cat("03 רגישות לשינויי קלט")
MIS = pytest.mark.cat("04 נתונים חסרים")
INC = pytest.mark.cat("05 נתונים לא עקביים")
EDGE = pytest.mark.cat("07 מקרי קצה וקלט לא תקין")
STALE = pytest.mark.cat("08 מקורות לא מעודכנים")
ELIG = pytest.mark.cat("09 זכאות לא ניתנת לאימות")
NOCMP = pytest.mark.cat("10 אין השוואה אמינה")
CRIT = pytest.mark.critical

BASE = dict(age=38, retirement_age=67, salary=18_000, balance=420_000,
            contribution_rate=0.185, salary_growth=0.0, scenario_returns={"central": 0.035})
CUR, ALT = FeeTerms(2.0, 0.30), FeeTerms(1.25, 0.11)


def gap(**over):
    kw = {**BASE, **{k: v for k, v in over.items() if k not in ("current", "alternative")}}
    c = compare(current=over.get("current", CUR), alternative=over.get("alternative", ALT), **kw)
    return c


# --- 02 scenarios via the pipeline ----------------------------------------------

@SCN
def test_pipeline_returns_three_scenarios_in_order():
    """ניתוח עידו ← שלושה תרחישים: שמרני, מרכזי, אופטימי"""
    r = analyze()
    assert [i["label"] for i in r["scenarios"]["items"]] == ["שמרני", "מרכזי", "אופטימי"]


@SCN
def test_pipeline_yearly_series_length():
    """גיל 38→67 ← 29 נקודות שנתיות לכל סדרה"""
    r = analyze()
    for i in r["scenarios"]["items"]:
        assert len(i["current_yearly"]) == 29 == len(i["alternative_yearly"])


@SCN
@CRIT
def test_pipeline_gap_equals_difference():
    """בכל תרחיש ← פער = צבירה חלופית − צבירה נוכחית (בעיגול לשקל)"""
    for i in analyze()["scenarios"]["items"]:
        assert abs(i["gap"] - (i["alternative_final"] - i["current_final"])) <= 1


@SCN
def test_pipeline_compared_fund_is_top_alternative():
    """הקרן בגרף ← הקרן של ממצא המעבר הראשון (הפער הגדול ביותר)"""
    r = analyze()
    top = next(f for f in r["findings"] if f["finding_id"] == "F-switch-1")
    assert r["scenarios"]["compared_fund"] in top["title"]


@SCN
def test_pipeline_retirement_60_shortens_series():
    """גיל פרישה 60 ← 22 נקודות שנתיות"""
    r = analyze(profile(planned_retirement_age=60))
    assert len(r["scenarios"]["items"][0]["current_yearly"]) == 22


@SCN
def test_pipeline_balance_increases_with_return():
    """צבירה בתנאים נוכחיים ← שמרני < מרכזי < אופטימי"""
    v = [i["current_final"] for i in analyze()["scenarios"]["items"]]
    assert v[0] < v[1] < v[2]


@SCN
def test_pipeline_central_return_from_assumptions():
    """שינוי התשואה המרכזית בקובץ ההנחות ← שינוי בפער המרכזי"""
    a = analyze()["scenarios"]["items"][1]["gap"]
    b = analyze(assm=assumptions(scenarios__central__annual_real_return=0.045))["scenarios"]["items"][1]["gap"]
    assert b > a


# --- 03 sensitivity ---------------------------------------------------------------

def _central(c):
    return c.by_name("central").gap_at_retirement


@SEN
def test_higher_salary_bigger_gap():
    """שכר גבוה יותר ← פער גדול יותר"""
    assert _central(gap(salary=25_000)) > _central(gap())


@SEN
def test_higher_balance_bigger_gap():
    """צבירה גבוהה יותר ← פער גדול יותר"""
    assert _central(gap(balance=800_000)) > _central(gap())


@SEN
def test_later_retirement_bigger_gap():
    """פרישה מאוחרת יותר ← פער גדול יותר"""
    assert _central(gap(retirement_age=70)) > _central(gap())


@SEN
def test_older_age_smaller_gap():
    """גיל מבוגר יותר (אותה צבירה) ← פער קטן יותר"""
    assert _central(gap(age=50)) < _central(gap())


@SEN
def test_higher_contribution_bigger_deposit_saving():
    """שיעור הפקדה 20.5% ← חיסכון גדול יותר ברכיב ההפקדות"""
    assert gap(contribution_rate=0.205).first_year_deposit_fee_saving > gap().first_year_deposit_fee_saving


@SEN
def test_salary_growth_bigger_gap():
    """צמיחת שכר ריאלית 1% ← פער גדול יותר"""
    assert _central(gap(salary_growth=0.01)) > _central(gap())


@SEN
@CRIT
def test_equal_deposit_fee_only_accumulation_component():
    """דמי הפקדה זהים ← החיסכון ברכיב ההפקדות כמעט 0 (רק השפעה עקיפה של הצבירה)"""
    c = gap(alternative=FeeTerms(2.0, 0.11))
    assert c.first_year_deposit_fee_saving == pytest.approx(0.0)
    assert c.first_year_accumulation_fee_saving > 0


@SEN
def test_smaller_accumulation_diff_smaller_gap():
    """פער קטן יותר בדמי הצבירה ← פער מצטבר קטן יותר"""
    assert _central(gap(alternative=FeeTerms(1.25, 0.25))) < _central(gap())


@SEN
@CRIT
def test_double_deposit_diff_doubles_deposit_saving():
    """הכפלת ההפרש בדמי ההפקדה ← הכפלת החיסכון ברכיב ההפקדות"""
    a = gap(alternative=FeeTerms(1.5, 0.30)).first_year_deposit_fee_saving
    b = gap(alternative=FeeTerms(1.0, 0.30)).first_year_deposit_fee_saving
    assert b == pytest.approx(2 * a)


@SEN
def test_gap_monotonic_in_return():
    """תשואות 0%..6% ← פער עולה באופן מונוטוני"""
    gaps = [_central(gap(scenario_returns={"central": r})) for r in (0.0, 0.02, 0.04, 0.06)]
    assert gaps == sorted(gaps)


# --- 04 missing data --------------------------------------------------------------

@MIS
@CRIT
@pytest.mark.parametrize("field", ["age", "deposit_fee_pct", "accumulation_fee_pct",
                                   "gross_monthly_salary", "accumulated_balance"])
def test_missing_profile_field_blocks_analysis(field):
    """שדה פרופיל חסר ← invalid_input, אין ממצאים, השדה מזוהה ומוזכר בעברית בשגיאה"""
    from app.intake import BY_KEY
    r = analyze(profile(**{field: DROP}))
    assert r["status"] == "invalid_input"
    assert r["findings"] == []
    assert field in r["invalid_fields"]
    assert BY_KEY[field].label in r["error"]


@MIS
@CRIT
def test_no_snapshot_is_insufficient():
    """אין נתוני שוק ← insufficient, ממצא יחיד ברמת ודאות 3, אין תרחישים"""
    r = analyze(snap=None, manifest=None)
    assert r["status"] == "insufficient"
    assert [f["finding_id"] for f in r["findings"]] == ["F-insufficient"]
    assert r["findings"][0]["certainty"] == 3
    assert r["scenarios"] is None


@MIS
def test_empty_funds_is_insufficient():
    """snapshot ללא קרנות ← insufficient"""
    assert analyze(snap=snapshot(funds=[]))["status"] == "insufficient"


@MIS
def test_snapshot_without_period_is_insufficient():
    """snapshot בלי תקופת דיווח ← insufficient"""
    s = snapshot()
    s["latest_report_period"] = None
    assert analyze(snap=s)["status"] == "insufficient"


@MIS
def test_parse_rejects_missing_fees():
    """רשומה ללא דמי ניהול ← נפסלת עם סיבה, לא נכללת"""
    res = parse_records([rec(1, "קרן", d=None)], CAPS)
    assert res.funds == []
    assert res.rejected[0].reason == "דמי ניהול חסרים במקור"


@MIS
def test_parse_rejects_missing_fund_id():
    """רשומה ללא FUND_ID ← נפסלת"""
    r = rec(None, "קרן")
    res = parse_records([r], CAPS)
    assert res.funds == [] and "שדות חסרים" in res.rejected[0].reason


# --- 05 inconsistent data ---------------------------------------------------------

@INC
def test_retirement_not_after_age():
    """גיל 67, פרישה 67 ← invalid_input"""
    assert analyze(profile(age=67, planned_retirement_age=67))["status"] == "invalid_input"


@INC
@CRIT
def test_deposit_fee_above_cap():
    """דמי הפקדה 7% (מעל התקרה) ← invalid_input, לא ממצא"""
    r = analyze(profile(deposit_fee_pct=7.0))
    assert r["status"] == "invalid_input" and r["findings"] == []


@INC
@CRIT
def test_accumulation_fee_above_cap():
    """דמי צבירה 0.6% (מעל התקרה) ← invalid_input"""
    assert analyze(profile(accumulation_fee_pct=0.6))["status"] == "invalid_input"


@INC
def test_negative_salary():
    """שכר שלילי ← invalid_input"""
    assert analyze(profile(gross_monthly_salary=-1))["status"] == "invalid_input"


@INC
def test_parse_tracks_with_different_fees_not_comparable():
    """שני מסלולים של אותה קרן עם דמי ניהול שונים ← הקרן לא ברת-השוואה"""
    res = parse_records([rec(1, "קרן", d=1.2), rec(2, "קרן", d=1.4)], CAPS)
    assert res.funds[0].comparable is False and res.funds[0].issues


@INC
def test_parse_duplicate_row_rejected():
    """אותו מסלול ואותה תקופה פעמיים ← הכפילות נפסלת"""
    res = parse_records([rec(1, "קרן"), rec(1, "קרן")], CAPS)
    assert any("כפולה" in r.reason for r in res.rejected)
    assert res.funds[0].track_count == 1


@INC
def test_parse_invalid_period_rejected():
    """תקופת דיווח 202613 ← נפסלת"""
    res = parse_records([rec(1, "קרן", period=202613)], CAPS)
    assert res.rejected[0].reason == "תקופת דיווח לא תקינה"


@INC
def test_future_period_not_usable():
    """תקופת דיווח עתידית ← הנתונים לא בשימוש, insufficient"""
    assert analyze(snap=snapshot(period=202701))["status"] == "insufficient"


# --- 07 edge: guard ----------------------------------------------------------------

class _Tamper(TemplateAgent):
    def __init__(self, fn):
        self.fn = fn

    def analyze(self, inp):
        out = super().analyze(inp)
        self.fn(out)
        return out


@EDGE
def test_guard_blocks_dropped_finding():
    """הסוכן משמיט ממצא ← הניתוח נכשל, לא מוצגות תוצאות"""
    r = analyze(agent=_Tamper(lambda o: o.findings.pop()))
    assert r["status"] == "failed" and r["findings"] == []


@EDGE
def test_guard_blocks_empty_field():
    """הסוכן מחזיר הסבר ריק ← הניתוח נכשל"""
    def f(o):
        o.findings[0].explanation = " "
    assert analyze(agent=_Tamper(f))["status"] == "failed"


# --- 08 stale sources --------------------------------------------------------------

@STALE
def test_two_month_lag_is_fresh():
    """תקופה 09/2026, היום 11/2026 ← פיגור 2, ניתוח מלא"""
    assert months_lag(202609, TODAY) == 2
    assert analyze()["status"] == "ok"


@STALE
def test_lag_equal_threshold_is_fresh():
    """פיגור של 4 חודשים (בדיוק הסף) ← עדיין עדכני"""
    assert analyze(snap=snapshot(period=202607))["status"] == "ok"


@STALE
@CRIT
def test_lag_above_threshold_is_stale():
    """פיגור 5 חודשים ← insufficient, ודאות 3"""
    r = analyze(snap=snapshot(period=202606))
    assert r["status"] == "insufficient" and r["findings"][0]["certainty"] == 3


@STALE
@CRIT
def test_stale_shows_no_money():
    """נתונים ישנים ← אין תרחישים ואין סכומים בתוכנית הפעולה"""
    r = analyze(snap=snapshot(period=202606))
    assert r["scenarios"] is None and r["action_plan"] == []


@STALE
def test_lag_across_year_boundary():
    """תקופה 11/2026, היום 01/2027 ← פיגור 2"""
    assert months_lag(202611, date(2027, 1, 10)) == 2


@STALE
def test_parse_rejects_track_missing_latest_period():
    """מסלול שלא דווח בתקופה האחרונה ← נפסל ולא נכלל"""
    res = parse_records([rec(1, "קרן", period=202609), rec(2, "קרן", period=202606)], CAPS)
    assert res.funds[0].track_count == 1
    assert "לא דווח בתקופה האחרונה" in res.rejected[0].reason


@STALE
def test_stale_message_names_period():
    """נתונים ישנים ← ההודעה מציינת את תקופת הדיווח"""
    r = analyze(snap=snapshot(period=202606))
    assert "202606" in " ".join(r["market"]["messages"])


# --- 09 eligibility cannot be verified -----------------------------------------------

@ELIG
@CRIT
def test_never_certainty_one():
    """נתוני שוק = ממוצעים ← אף ממצא אינו ברמת ודאות 1"""
    assert all(f["certainty"] >= 2 for f in analyze()["findings"])


@ELIG
def test_switch_limitations_say_not_an_offer():
    """ממצא מעבר ← המגבלות מציינות שזה ממוצע ולא הצעה"""
    for f in analyze()["findings"]:
        if f["finding_id"].startswith("F-switch"):
            assert any("לא הצעה" in x for x in f["limitations"])


@ELIG
def test_switch_text_says_not_an_offer():
    """ממצא מעבר ← ההסבר עצמו אומר 'לא הצעה עבורך'"""
    for f in analyze()["findings"]:
        if f["finding_id"].startswith("F-switch"):
            assert "לא הצעה עבורך" in f["explanation"]


@ELIG
@CRIT
def test_risk_levels():
    """פנייה לקרן הנוכחית ← סיכון נמוך; מעבר קרן ← סיכון גבוה"""
    f = {x["finding_id"]: x for x in analyze()["findings"]}
    assert f["F-negotiate"]["risk"] == "low" and f["F-verify"]["risk"] == "low"
    assert all(v["risk"] == "high" for k, v in f.items() if k.startswith("F-switch"))


@ELIG
@CRIT
def test_low_risk_ranked_first_even_if_less_money():
    """פעולה בסיכון נמוך עם סכום קטן ← מדורגת לפני פעולה בסיכון גבוה עם סכום גדול"""
    fs = analyze()["findings"]
    risks = [f["risk"] for f in fs]
    assert risks == sorted(risks, key=lambda r: r != "low")
    neg = next(f for f in fs if f["finding_id"] == "F-negotiate")
    sw = next(f for f in fs if f["finding_id"] == "F-switch-1")
    assert sw["ranking_value_ils"] > neg["ranking_value_ils"]
    assert fs.index(neg) < fs.index(sw)


# --- 10 no reliable comparison ------------------------------------------------------

@NOCMP
def test_all_funds_not_comparable():
    """כל הקרנות לא ברות-השוואה ← insufficient"""
    s = snapshot(funds=[fund("א", None, None, comparable=False)])
    assert analyze(snap=s)["status"] == "insufficient"


@NOCMP
@pytest.mark.alarm_check
def test_cheaper_than_market_no_opportunity():
    """עידו משלם 0.5%/0.05% (זול מכולם) ← 'לא נמצא פער', בלי המלצת מעבר"""
    r = analyze(profile(deposit_fee_pct=0.5, accumulation_fee_pct=0.05))
    assert [f["finding_id"] for f in r["findings"]] == ["F-no-gap"]


@NOCMP
@pytest.mark.alarm_check
def test_identical_to_market_no_opportunity():
    """שוק עם קרן אחת בתנאים זהים לעידו ← 'לא נמצא פער'"""
    r = analyze(snap=snapshot(funds=[fund("א", 2.0, 0.30)]))
    assert [f["finding_id"] for f in r["findings"]] == ["F-no-gap"]


@NOCMP
@CRIT
def test_guard_blocks_invented_number():
    """הסוכן מוסיף סכום שלא חושב (999,999 ₪) ← הניתוח נכשל, אין תוצאות"""
    def f(o):
        o.findings[0].explanation += " ייתכן חיסכון של 999,999 ₪."
    r = analyze(agent=_Tamper(f))
    assert r["status"] == "failed" and r["findings"] == []


@NOCMP
def test_agent_exception_fails_cleanly():
    """ספק הניסוח זורק שגיאה ← הניתוח נכשל, לא מוצגת תוצאה חלקית"""
    class Boom(TemplateAgent):
        def analyze(self, inp):
            raise TimeoutError("provider down")
    r = analyze(agent=Boom())
    assert r["status"] == "failed" and r["findings"] == []
