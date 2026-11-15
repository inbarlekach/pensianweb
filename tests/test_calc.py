"""Calculation tests. Expected values come from closed-form formulas written independently
of the month-by-month loop in app/calc/fees.py, not from running the engine."""
import pytest

from app.calc.fees import FeeTerms, SimInput, simulate, monthly_rate, months_to_retirement, monthly_deposit
from app.calc.scenarios import compare

NO_FEES = FeeTerms(0, 0)
FEE = pytest.mark.cat("01 חישובי דמי ניהול")
SCN = pytest.mark.cat("02 תחזית שלושה תרחישים")
EDGE = pytest.mark.cat("07 מקרי קצה וקלט לא תקין")
CRIT = pytest.mark.critical
IDO_KW = dict(age=38, retirement_age=67, salary=18_000, balance=420_000,
              contribution_rate=0.185, salary_growth=0.0)
THREE = {"conservative": 0.02, "central": 0.035, "optimistic": 0.05}


def closed_form(B, dep, n, annual_r, d_pct, a_pct):
    """b_k = (b_{k-1} + dep(1-d)) * g,  g = (1+r_m)(1-a/12)."""
    rm = (1 + annual_r) ** (1 / 12) - 1
    g = (1 + rm) * (1 - a_pct / 100 / 12)
    net = dep * (1 - d_pct / 100)
    if abs(g - 1) < 1e-15:
        return B + net * n
    return B * g ** n + net * g * (g ** n - 1) / (g - 1)


# --- 01 fee calculations --------------------------------------------------------

@FEE
@CRIT
def test_no_return_no_fees_is_sum_of_deposits():
    """תשואה 0, ללא דמי ניהול ← צבירה = צבירה התחלתית + סכום ההפקדות"""
    r = simulate(SimInput(420_000, 3330, 348, 0.0), NO_FEES)
    assert r.final_balance == pytest.approx(420_000 + 3330 * 348)
    assert r.total_fees == 0


@FEE
@CRIT
def test_deposit_fee_only_zero_return():
    """1,000 ₪ × 12, דמי הפקדה 2% ← דמי ניהול 240 ₪, צבירה 11,760 ₪"""
    r = simulate(SimInput(0, 1000, 12, 0.0), FeeTerms(2.0, 0))
    assert r.total_deposit_fees == pytest.approx(240.0)
    assert r.final_balance == pytest.approx(11_760.0)


@FEE
@CRIT
def test_deposit_fee_at_legal_max():
    """דמי הפקדה 6% (תקרה), 1,000 ₪ × 12 ← צבירה 11,280 ₪"""
    r = simulate(SimInput(0, 1000, 12, 0.0), FeeTerms(6.0, 0))
    assert r.final_balance == pytest.approx(11_280.0)


@FEE
@CRIT
def test_accumulation_fee_only_no_deposits():
    """100,000 ₪, דמי צבירה 0.30%, שנה ← 100,000 × (1−0.003/12)^12"""
    r = simulate(SimInput(100_000, 0, 12, 0.0), FeeTerms(0, 0.30))
    assert r.final_balance == pytest.approx(100_000 * (1 - 0.003 / 12) ** 12)
    assert r.total_accumulation_fees == pytest.approx(100_000 - r.final_balance)


@FEE
@CRIT
def test_accumulation_fee_at_legal_max():
    """דמי צבירה 0.5% (תקרה), 200,000 ₪, שנה ← 200,000 × (1−0.005/12)^12"""
    r = simulate(SimInput(200_000, 0, 12, 0.0), FeeTerms(0, 0.5))
    assert r.final_balance == pytest.approx(200_000 * (1 - 0.005 / 12) ** 12)


@FEE
def test_monthly_rate_compounds_to_annual():
    """תשואה חודשית שקולה ל-3.5% שנתי ← (1+r_m)^12 = 1.035"""
    assert (1 + monthly_rate(0.035)) ** 12 == pytest.approx(1.035)


@FEE
@CRIT
def test_return_no_fees_matches_annuity_formula():
    """50,000 ₪ + 2,000 ₪ לחודש, 10 שנים, 4% ← נוסחת אנונה סגורה"""
    r = simulate(SimInput(50_000, 2000, 120, 0.04), NO_FEES)
    assert r.final_balance == pytest.approx(closed_form(50_000, 2000, 120, 0.04, 0, 0), rel=1e-12)


@FEE
@CRIT
@pytest.mark.parametrize("B,dep,n,ret,d,a", [
    (420_000, 3330, 348, 0.02, 2.0, 0.30),
    (420_000, 3330, 348, 0.035, 2.0, 0.30),
    (420_000, 3330, 348, 0.05, 2.0, 0.30),
    (420_000, 3330, 348, 0.035, 1.39, 0.10),
    (0, 5000, 240, 0.03, 6.0, 0.5),
    (1_000_000, 0, 60, 0.04, 0, 0.25),
    (10_000, 1, 12, -0.05, 1.0, 0.1),
])
def test_full_engine_matches_closed_form(B, dep, n, ret, d, a):
    """מנוע מלא (הפקדה + צבירה + תשואה) ← תואם נוסחה סגורה בדיוק 1e-12"""
    r = simulate(SimInput(B, dep, n, ret), FeeTerms(d, a))
    assert r.final_balance == pytest.approx(closed_form(B, dep, n, ret, d, a), rel=1e-12)


@FEE
def test_one_month_by_hand():
    """חודש אחד: 1,000 + 100×0.99, תשואה 12% שנתי, צבירה 0.12% ← חישוב ידני"""
    r = simulate(SimInput(1000, 100, 1, 0.12), FeeTerms(1.0, 0.12))
    expected = (1000 + 99) * (1.12 ** (1 / 12)) * (1 - 0.0012 / 12)
    assert r.final_balance == pytest.approx(expected, rel=1e-12)


@FEE
def test_zero_months_keeps_balance():
    """0 חודשים ← הצבירה לא משתנה ואין דמי ניהול"""
    r = simulate(SimInput(5000, 100, 0, 0.05), FeeTerms(2, 0.3))
    assert r.final_balance == 5000 and r.total_fees == 0


@FEE
def test_fees_reconcile_with_balance_when_zero_return():
    """תשואה 0 ← צבירה סופית + סך דמי ניהול = צבירה התחלתית + סך הפקדות"""
    r = simulate(SimInput(420_000, 3330, 348, 0.0), FeeTerms(2.0, 0.30))
    assert r.final_balance + r.total_fees == pytest.approx(420_000 + r.total_deposits)


@FEE
def test_total_fees_is_sum_of_components():
    """סך דמי ניהול = רכיב הפקדות + רכיב צבירה"""
    r = simulate(SimInput(420_000, 3330, 60, 0.03), FeeTerms(2.0, 0.30))
    assert r.total_fees == pytest.approx(r.total_deposit_fees + r.total_accumulation_fees)


@FEE
def test_salary_growth_raises_deposit_yearly():
    """הפקדה 1,000 ₪, צמיחת שכר 10% ← שנה ב׳ מפקידה 1,100 ₪ לחודש"""
    r = simulate(SimInput(0, 1000, 24, 0.0, salary_growth_annual=0.10), NO_FEES)
    assert r.total_deposits == pytest.approx(12 * 1000 + 12 * 1100)


@FEE
def test_yearly_balances_length():
    """348 חודשים ← 29 ערכי צבירה שנתיים, האחרון = הצבירה הסופית"""
    r = simulate(SimInput(0, 100, 348, 0.03), NO_FEES)
    assert len(r.yearly_balances) == 29
    assert r.yearly_balances[-1] == pytest.approx(r.final_balance)


@FEE
def test_yearly_balance_matches_closed_form_at_year_10():
    """צבירה בסוף שנה 10 ← נוסחה סגורה עם n=120"""
    r = simulate(SimInput(420_000, 3330, 348, 0.035), FeeTerms(2.0, 0.30))
    assert r.yearly_balances[9] == pytest.approx(closed_form(420_000, 3330, 120, 0.035, 2.0, 0.30), rel=1e-12)


@FEE
@CRIT
def test_ido_monthly_deposit_and_horizon():
    """שכר 18,000 ₪ × 18.5% ← הפקדה 3,330 ₪; גיל 38→67 ← 348 חודשים"""
    assert monthly_deposit(18_000, 0.185) == pytest.approx(3330.0)
    assert months_to_retirement(38, 67) == 348


@FEE
@CRIT
def test_ido_first_year_deposit_fee_saving_vs_alternative():
    """2.00%→1.39% מההפקדות ← חיסכון 3,330×12×0.61% = 243.756 ₪; רכיב הצבירה שלילי קטן"""
    c = compare(**IDO_KW, scenario_returns={"central": 0.035},
                current=FeeTerms(2.0, 0.30), alternative=FeeTerms(1.39, 0.30))
    assert c.first_year_deposit_fee_saving == pytest.approx(243.756)
    # Same accumulation rate, but the balance is larger (more net deposit), so slightly
    # MORE accumulation fee is paid in shekels: the saving is small and negative.
    assert -1.0 < c.first_year_accumulation_fee_saving < 0
    assert c.first_year_fee_saving == pytest.approx(
        c.first_year_deposit_fee_saving + c.first_year_accumulation_fee_saving)


@FEE
@CRIT
def test_first_year_deposit_saving_one_point():
    """2.00%→1.00% מההפקדות ← חיסכון בשנה הראשונה 399.6 ₪ ברכיב ההפקדות"""
    c = compare(**IDO_KW, scenario_returns={"central": 0.035},
                current=FeeTerms(2.0, 0.30), alternative=FeeTerms(1.0, 0.30))
    assert c.first_year_deposit_fee_saving == pytest.approx(399.6)


@FEE
@CRIT
def test_accumulation_saving_without_deposits():
    """420,000 ₪ ללא הפקדות, 0.30%→0.15%, תשואה 0 ← הפרש לפי נוסחה סגורה"""
    cur = simulate(SimInput(420_000, 0, 12, 0.0), FeeTerms(0, 0.30))
    alt = simulate(SimInput(420_000, 0, 12, 0.0), FeeTerms(0, 0.15))
    expected = 420_000 * ((1 - 0.0015 / 12) ** 12 - (1 - 0.003 / 12) ** 12)
    assert alt.final_balance - cur.final_balance == pytest.approx(expected, rel=1e-10)


# --- 02 scenarios ---------------------------------------------------------------

@SCN
@pytest.mark.alarm_check
def test_identical_terms_give_zero_gap():
    """תנאים זהים ← פער 0 בכל שלושת התרחישים"""
    t = FeeTerms(2.0, 0.30)
    c = compare(**IDO_KW, scenario_returns=THREE, current=t, alternative=t)
    assert c.first_year_fee_saving == 0
    assert all(s.gap_at_retirement == 0 for s in c.scenarios)


@SCN
@CRIT
def test_cheaper_terms_gap_positive_and_grows_with_return():
    """תנאים זולים יותר ← פער חיובי, שמרני < מרכזי < אופטימי"""
    c = compare(**IDO_KW, scenario_returns=THREE, current=FeeTerms(2.0, 0.30), alternative=FeeTerms(1.39, 0.10))
    gaps = [c.by_name(n).gap_at_retirement for n in ("conservative", "central", "optimistic")]
    assert all(g > 0 for g in gaps)
    assert gaps[0] < gaps[1] < gaps[2]


@SCN
@CRIT
@pytest.mark.parametrize("name,r", list(THREE.items()))
def test_gap_matches_closed_form_difference(name, r):
    """פער בגיל 67 בכל תרחיש ← הפרש בין שתי נוסחאות סגורות"""
    c = compare(**IDO_KW, scenario_returns=THREE, current=FeeTerms(2.0, 0.30), alternative=FeeTerms(1.39, 0.10))
    expected = closed_form(420_000, 3330, 348, r, 1.39, 0.10) - closed_form(420_000, 3330, 348, r, 2.0, 0.30)
    assert c.by_name(name).gap_at_retirement == pytest.approx(expected, rel=1e-10)


@SCN
def test_more_expensive_alternative_gives_negative_gap():
    """חלופה יקרה יותר ← פער שלילי"""
    c = compare(**IDO_KW, scenario_returns=THREE, current=FeeTerms(1.0, 0.10), alternative=FeeTerms(2.0, 0.30))
    assert all(s.gap_at_retirement < 0 for s in c.scenarios)


@SCN
def test_first_year_saving_uses_central_scenario_only():
    """שינוי התשואה השמרנית ← אינו משנה את החיסכון בשנה הראשונה"""
    a = compare(**IDO_KW, scenario_returns=THREE, current=FeeTerms(2, 0.3), alternative=FeeTerms(1, 0.1))
    b = compare(**IDO_KW, scenario_returns={**THREE, "conservative": -0.01}, current=FeeTerms(2, 0.3), alternative=FeeTerms(1, 0.1))
    assert a.first_year_fee_saving == pytest.approx(b.first_year_fee_saving)


@SCN
def test_empty_scenarios_rejected():
    """אין תרחישים ← שגיאה מפורשת"""
    with pytest.raises(ValueError):
        compare(**IDO_KW, scenario_returns={}, current=FeeTerms(2, 0.3), alternative=FeeTerms(1, 0.1))


# --- 07 invalid input must fail loudly, never silently ---------------------------

@EDGE
@pytest.mark.parametrize("d,a", [(-1, 0.3), (2.0, -0.1), (100, 0.3), (float("nan"), 0.3), (None, 0.3)])
def test_invalid_fees_rejected(d, a):
    """דמי ניהול שליליים / 100% / NaN / חסרים ← שגיאה"""
    with pytest.raises(ValueError):
        FeeTerms(d, a)


@EDGE
@pytest.mark.parametrize("kwargs", [
    dict(start_balance=-1, monthly_deposit=100, months=12, annual_return=0.03),
    dict(start_balance=0, monthly_deposit=-5, months=12, annual_return=0.03),
    dict(start_balance=0, monthly_deposit=100, months=-1, annual_return=0.03),
    dict(start_balance=0, monthly_deposit=100, months=12, annual_return=-1.0),
])
def test_invalid_sim_input_rejected(kwargs):
    """צבירה/הפקדה/חודשים שליליים או תשואה −100% ← שגיאה"""
    with pytest.raises(ValueError):
        SimInput(**kwargs)


@EDGE
def test_retirement_age_not_after_age_rejected():
    """גיל פרישה = גיל נוכחי ← שגיאה"""
    with pytest.raises(ValueError):
        months_to_retirement(67, 67)


@EDGE
def test_contribution_rate_out_of_range_rejected():
    """שיעור הפקדה 18.5 (אחוז במקום שבר) ← שגיאה"""
    with pytest.raises(ValueError):
        monthly_deposit(18_000, 18.5)
