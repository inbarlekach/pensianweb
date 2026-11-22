"""Plain-language numbers and the verdict level (category 13). Expected values are derived
by hand / closed form, not by running the engine."""
from pathlib import Path

import pytest

from .helpers import analyze, fund, profile, snapshot

READ = pytest.mark.cat("13 תצוגה ברורה ללא ידע פנסיוני")
CRIT = pytest.mark.critical
STATIC = Path(__file__).resolve().parents[1] / "app" / "static"


def calcs(**kw):
    return analyze(**kw)["calcs"]


@READ
@CRIT
def test_first_year_deposit_fees_by_hand():
    """הפקדה 3,330 ₪ × 12 חודשים × 2.00% ← 799.2 ₪ דמי ניהול מההפקדות (מעוגל 799)"""
    assert calcs()["cur_y1_dep_fees"]["value"] == 799


@READ
@CRIT
def test_first_year_accumulation_fees_within_hand_bounds():
    """צבירה 420,000 ₪ ו-0.30% ← בין 0.30% מהצבירה ההתחלתית (1,260) לבין 0.30% מהצבירה המקסימלית האפשרית (≈1,426)"""
    v = calcs()["cur_y1_acc_fees"]["value"]
    upper = 0.003 * (420_000 + 12 * 3330 * 0.98) * 1.035
    assert 1260 <= v <= upper


@READ
@CRIT
def test_total_is_sum_of_parts():
    """סך דמי הניהול בשנה = בדיוק רכיב ההפקדות + רכיב הצבירה כפי שמוצגים (בלי הפרש עיגול גלוי)"""
    c = calcs()
    assert c["cur_y1_total_fees"]["value"] == c["cur_y1_dep_fees"]["value"] + c["cur_y1_acc_fees"]["value"]


@READ
@CRIT
def test_per_1000_and_per_100k_examples():
    """2.00% מההפקדות ← 20 ₪ מכל 1,000; 0.30% מהצבירה ← 300 ₪ בשנה מכל 100,000"""
    c = calcs()
    assert c["cur_dep_per_1000"]["value"] == 20.0
    assert c["cur_acc_per_100k"]["value"] == 300.0


@READ
def test_examples_are_marked_as_facts_and_totals_as_estimates():
    """הדוגמאות לפי אחוזים ← עובדה; הסכום השנתי ← הערכה"""
    c = calcs()
    assert c["cur_dep_per_1000"]["kind"] == "fact" and c["cur_acc_per_100k"]["kind"] == "fact"
    assert c["cur_y1_total_fees"]["kind"] == "estimate"


@READ
@CRIT
def test_verdict_higher_than_all():
    """עידו מול 5 קרנות זולות יותר ← 'גבוה מכולן'"""
    ctx = analyze()["market"]["context"]
    assert ctx["verdict"] == "higher_than_all" and ctx["funds_cheaper_than_you"] == 5


@READ
@CRIT
@pytest.mark.alarm_check
def test_verdict_lower_when_cheapest():
    """דמי ניהול זולים מכולם ← 'lower', בלי הזדמנות"""
    r = analyze(profile(deposit_fee_pct=0.5, accumulation_fee_pct=0.05))
    assert r["market"]["context"]["verdict"] == "lower"
    assert [f["finding_id"] for f in r["findings"]] == ["F-no-gap"]


@READ
def test_verdict_mixed_and_most():
    """קרן אחת זולה מתוך חמש ← 'mixed'; שלוש מתוך חמש ← 'higher_than_most'"""
    pricey = [fund(f"יקרה {i}", 2.5, 0.4) for i in range(4)]
    mixed = analyze(snap=snapshot(funds=[fund("זולה", 1.0, 0.1)] + pricey))
    assert mixed["market"]["context"]["verdict"] == "mixed"
    most = analyze(snap=snapshot(funds=[fund(f"זולה {i}", 1.0, 0.1) for i in range(3)] + pricey[:2]))
    assert most["market"]["context"]["verdict"] == "higher_than_most"


@READ
def test_no_new_numbers_break_the_guard():
    """המספרים החדשים לא מופיעים בטקסט הסוכן ← הניתוח עדיין עובר את בדיקת המספרים"""
    assert analyze()["status"] == "ok"


@READ
def test_insufficient_data_has_no_fee_amounts():
    """אין נתוני שוק ← אין סכומי דמי ניהול מוצגים (לא ממציאים)"""
    c = calcs(snap=None, manifest=None)
    assert "cur_y1_total_fees" not in c


@READ
def test_html_has_detail_window_and_term_buttons():
    """ה-HTML ← יש חלון פירוט (dialog), ומונחי הפרופיל הם כפתורים ולא רמזי עכבר בלבד"""
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    assert '<dialog id="sheet"' in html
    assert 'data-term="deposit_fee"' in html and 'data-term="accumulation_fee"' in html
    assert "<abbr" not in html


@READ
def test_every_inline_term_has_a_glossary_entry():
    """כל מונח שמסומן ב-data-term או ב-term() בקוד ← קיים במילון"""
    import re
    js = (STATIC / "app.js").read_text(encoding="utf-8")
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    keys = set(re.findall(r"data-term=\"(\w+)\"", html)) | set(re.findall(r"term\(\"(\w+)\"", js))
    defined = set(re.findall(r"^\s{2}(\w+): \{ title:", js, flags=re.M))
    assert keys and keys <= defined, f"מונחים בלי הגדרה: {keys - defined}"
