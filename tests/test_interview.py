"""Profile interview tests (category 11): parsing, validation, flow, and the effect of a
chat-built profile on the analysis."""
import pytest

from app.agents.interviewer import CONFIRM, EDIT_PREFIX, RESTART, InterviewState, ScriptedInterviewer
from app.intake import BY_KEY, CONTINUE_WITHOUT, ParseError, parse_answer, parse_number

from .helpers import analyze

INT = pytest.mark.cat("11 ראיון ובניית פרופיל")
CRIT = pytest.mark.critical
BOT = ScriptedInterviewer()

IDO_ANSWERS = ["עידו", "38", "18,000", "420 אלף", "2%", "0.3", "נשוי", "36", "2", "67", "לבדוק דמי ניהול"]


def run_chat(answers):
    t = BOT.step(InterviewState(), None)
    for a in answers:
        t = BOT.step(t.state, a)
    return t


@INT
@CRIT
@pytest.mark.parametrize("text,expected", [
    ("18,000", 18000), ("18000 ₪", 18000), ("18 אלף", 18000), ("18k", 18000),
    ("כ-420 אלף", 420000), ("1.2 מיליון", 1_200_000), ("0,3", 0.3), ('₪ 3,330 ש"ח', 3330),
])
def test_parse_number_formats(text, expected):
    """פורמטים שונים של סכום ← ערך מספרי נכון"""
    assert parse_number(text) == pytest.approx(expected)


@INT
@pytest.mark.parametrize("text", ["בערך הרבה", "18-20 אלף", ""])
def test_parse_number_rejects_ambiguous(text):
    """תשובה בלי מספר או עם שני מספרים ← נדחית, לא מנחשים"""
    with pytest.raises(ParseError):
        parse_number(text)


@INT
@CRIT
def test_fee_above_legal_cap_rejected():
    """דמי צבירה 3% (מעל התקרה 0.5%) ← נדחה עם הסבר"""
    with pytest.raises(ParseError, match="התקרה"):
        parse_answer(BY_KEY["accumulation_fee_pct"], "3%", {})


@INT
def test_percent_field_ignores_thousand_word():
    """שדה אחוזים ← מילת 'אלף' לא מכפילה את הערך"""
    with pytest.raises(ParseError):
        parse_answer(BY_KEY["deposit_fee_pct"], "2 אלף", {})


@INT
def test_retirement_must_follow_age():
    """גיל 45, פרישה 40 ← נדחה"""
    with pytest.raises(ParseError):
        parse_answer(BY_KEY["planned_retirement_age"], "40", {"age": 45})


@INT
@CRIT
def test_full_chat_builds_profile_matching_answers():
    """שיחה מלאה עם ערכי עידו ← פרופיל עם אותם ערכים בדיוק"""
    t = run_chat(IDO_ANSWERS)
    assert t.state.phase == "confirm" and not any(r.missing for r in t.summary)
    t = BOT.step(t.state, CONFIRM)
    p = t.profile
    assert (p["age"], p["gross_monthly_salary"], p["accumulated_balance"]) == (38, 18000, 420000)
    assert (p["deposit_fee_pct"], p["accumulation_fee_pct"]) == (2.0, 0.3)
    assert (p["marital_status"], p["spouse_age"], p["children"], p["planned_retirement_age"]) == ("נשוי/אה", 36, 2, 67)
    assert p["_meta"]["kind"] == "user_entered"


@INT
@CRIT
def test_chat_profile_gives_same_analysis_as_demo():
    """פרופיל מהשיחה עם ערכי עידו ← אותם ממצאים וסכומים כמו פרופיל ההדגמה"""
    p = BOT.step(run_chat(IDO_ANSWERS).state, CONFIRM).profile
    a, b = analyze(p), analyze()
    assert a["status"] == "ok"
    assert [(f["finding_id"], f["ranking_value_ils"]) for f in a["findings"]] == \
           [(f["finding_id"], f["ranking_value_ils"]) for f in b["findings"]]


@INT
@CRIT
def test_chat_profile_changes_results():
    """שכר וצבירה שונים בשיחה ← פער שונה בתוצאות (הפרופיל משפיע על הניתוח)"""
    other = list(IDO_ANSWERS)
    other[2], other[3] = "30,000", "100 אלף"
    p = BOT.step(run_chat(other).state, CONFIRM).profile
    a, b = analyze(p), analyze()
    assert a["scenarios"]["items"][1]["gap"] != b["scenarios"]["items"][1]["gap"]


@INT
def test_single_skips_spouse_question():
    """מצב משפחתי רווק/ה ← לא נשאלת שאלה על בן/בת זוג"""
    t = run_chat(IDO_ANSWERS[:6] + ["רווק"])
    assert t.state.current == "children"


@INT
def test_invalid_answer_reasks_same_question():
    """תשובה לא תקינה לגיל ← אותה שאלה שוב, הערך לא נשמר"""
    t = run_chat(["דלג", "מאה"])
    assert t.state.current == "age" and "age" not in t.state.answers


@INT
def test_unknown_fee_offers_help_then_continue_without():
    """'לא יודע' לדמי ניהול ← הסבר איפה למצוא + אפשרות להמשיך בלי הנתון"""
    t = run_chat(IDO_ANSWERS[:4] + ["לא יודע"])
    assert t.state.current == "deposit_fee_pct"
    assert CONTINUE_WITHOUT in t.quick_replies
    assert any("דוח השנתי" in m for m in t.messages)


@INT
@CRIT
def test_missing_fee_blocks_analysis():
    """המשך בלי דמי הפקדה ← הפרופיל נוצר אבל הניתוח נחסם ומציין את השדה"""
    t = run_chat(IDO_ANSWERS[:4] + [CONTINUE_WITHOUT] + IDO_ANSWERS[5:])
    assert any(r.missing and r.key == "deposit_fee_pct" for r in t.summary)
    p = BOT.step(t.state, CONFIRM).profile
    r = analyze(p)
    assert r["status"] == "invalid_input" and r["invalid_fields"] == ["deposit_fee_pct"]
    assert "דמי ניהול מהפקדות" in r["error"]


@INT
def test_edit_field_from_summary():
    """תיקון שכר מהסיכום ← חוזר לשאלה, מעדכן וחוזר לסיכום"""
    t = run_chat(IDO_ANSWERS)
    t = BOT.step(t.state, f"{EDIT_PREFIX} שכר חודשי ברוטו")
    assert t.state.current == "gross_monthly_salary"
    t = BOT.step(t.state, "25 אלף")
    assert t.state.phase == "confirm" and t.state.answers["gross_monthly_salary"] == 25000


@INT
def test_restart_clears_answers():
    """'התחל מחדש' ← כל התשובות נמחקות"""
    t = BOT.step(run_chat(IDO_ANSWERS[:5]).state, RESTART)
    assert t.state.answers == {} and t.state.current == "name"


@INT
def test_first_message_warns_against_real_data():
    """הודעת הפתיחה ← אזהרה לא להזין נתונים אמיתיים"""
    t = BOT.step(InterviewState(), None)
    assert any("אמיתיים" in m for m in t.messages)
