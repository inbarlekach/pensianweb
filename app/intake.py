"""Deterministic parsing and validation of free-text profile answers.

Whatever produces the conversation (the scripted interviewer today, an LLM later), every
value that enters a profile passes through these functions. An answer that cannot be
parsed unambiguously is rejected with a reason — never guessed.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

NUM_RE = re.compile(r"\d+(?:[.,]\d+)*")
SKIP_WORDS = ("לא יודע", "לא יודעת", "אין לי מושג", "לא בטוח", "לא בטוחה", "דלג", "לדלג")
CONTINUE_WITHOUT = "המשך בלי הנתון"


class ParseError(ValueError):
    pass


def is_skip(text: str) -> bool:
    t = text.strip()
    return any(w in t for w in SKIP_WORDS) or t == CONTINUE_WITHOUT


def parse_number(text: str, allow_multipliers: bool = True) -> float:
    t = (text or "").replace("₪", " ").replace('ש"ח', " ").replace("שח", " ").replace("%", " % ")
    nums = NUM_RE.findall(t)
    if not nums:
        raise ParseError("לא מצאתי מספר בתשובה")
    if len(nums) > 1:
        raise ParseError("מצאתי יותר ממספר אחד – אפשר לכתוב מספר אחד בלבד?")
    raw = nums[0]
    if re.fullmatch(r"\d{1,3}(,\d{3})+(\.\d+)?", raw):
        v = float(raw.replace(",", ""))
    elif raw.count(",") == 1 and "." not in raw:
        v = float(raw.replace(",", "."))  # decimal comma: "0,3"
    elif raw.count(".") <= 1 and "," not in raw:
        v = float(raw)
    else:
        raise ParseError("פורמט המספר לא ברור")
    if allow_multipliers:
        low = t.lower()
        if "מיליון" in t or re.search(r"\d\s*m\b", low):
            v *= 1_000_000
        elif "אלף" in t or "אלפים" in t or re.search(r"\d\s*k\b", low):
            v *= 1_000
    return v


MARITAL = [
    (("ידוע בציבור", "ידועה בציבור", "ידועים בציבור"), "ידוע/ה בציבור", True),
    (("נשוי", "נשואה", "נשואים", "married"), "נשוי/אה", True),
    (("רווק", "רווקה", "single"), "רווק/ה", False),
    (("גרוש", "גרושה", "divorced"), "גרוש/ה", False),
    (("אלמן", "אלמנה", "widow"), "אלמן/ה", False),
]


def parse_marital(text: str) -> str:
    t = (text or "").strip().lower()
    for words, label, _ in MARITAL:
        if any(w in t for w in words):
            return label
    raise ParseError("לא זיהיתי מצב משפחתי. אפשר לבחור מהאפשרויות")


def has_partner(marital: Optional[str]) -> bool:
    return any(label == marital and partner for _, label, partner in MARITAL)


@dataclass
class FieldSpec:
    key: str
    label: str
    question: str
    kind: str  # text | int | money | pct | marital
    required: bool = True
    min: Optional[float] = None
    max: Optional[float] = None
    help: str = ""
    quick: list[str] = field(default_factory=list)
    condition: Callable[[dict], bool] = lambda a: True
    unit: str = ""


FIELDS: list[FieldSpec] = [
    FieldSpec("name", "שם או כינוי", "איך לקרוא לך? עדיף כינוי ולא שם אמיתי.", "text", required=False,
              quick=["דלג"]),
    FieldSpec("age", "גיל", "בן/בת כמה את/ה?", "int", min=18, max=70),
    FieldSpec("gross_monthly_salary", "שכר חודשי ברוטו", "מה השכר החודשי ברוטו שלך, בערך?", "money",
              min=1_000, max=200_000, unit="₪",
              help="השכר ברוטו מופיע בשורה העליונה של תלוש המשכורת, לפני ניכויים."),
    FieldSpec("accumulated_balance", "חיסכון פנסיוני שנצבר", "כמה כסף נצבר כבר בקרן הפנסיה שלך?", "money",
              min=0, max=20_000_000, unit="₪",
              help="הסכום מופיע בדוח השנתי או הרבעוני של הקרן, או באזור האישי באתר הקרן."),
    FieldSpec("deposit_fee_pct", "דמי ניהול מהפקדות", "כמה דמי ניהול את/ה משלם/ת מההפקדות החודשיות? (באחוזים)", "pct",
              min=0, max=6.0, unit="%",
              help="זה האחוז שהקרן גובה מכל הפקדה חודשית. מופיע בדוח השנתי של הקרן תחת 'דמי ניהול מהפקדות'. התקרה החוקית היא 6%.",
              quick=["לא יודע/ת"]),
    FieldSpec("accumulation_fee_pct", "דמי ניהול מצבירה", "וכמה דמי ניהול מהצבירה? (באחוזים לשנה)", "pct",
              min=0, max=0.5, unit="%",
              help="זה האחוז השנתי שהקרן גובה מכל הכסף שנצבר. מופיע בדוח השנתי תחת 'דמי ניהול מצבירה'. התקרה החוקית היא 0.5%.",
              quick=["לא יודע/ת"]),
    FieldSpec("marital_status", "מצב משפחתי", "מה המצב המשפחתי שלך?", "marital", required=False,
              quick=["נשוי/אה", "ידוע/ה בציבור", "רווק/ה", "גרוש/ה", "אלמן/ה"]),
    FieldSpec("spouse_age", "גיל בן/בת הזוג", "בן/בת כמה בן/בת הזוג?", "int", required=False, min=18, max=100,
              quick=["דלג"], condition=lambda a: has_partner(a.get("marital_status"))),
    FieldSpec("children", "מספר ילדים", "כמה ילדים יש לך?", "int", required=False, min=0, max=15,
              quick=["0", "1", "2", "3"]),
    FieldSpec("planned_retirement_age", "גיל פרישה מתוכנן", "באיזה גיל את/ה מתכנן/ת לפרוש?", "int", min=50, max=80,
              quick=["67", "65", "62"],
              help="גיל הפרישה הקבוע בחוק לגברים הוא 67. כאן אפשר לבחור את הגיל שלפיו נחשב את התחזית."),
    FieldSpec("reason", "סיבת הפנייה", "לסיום: מה הביא אותך לבדוק את הפנסיה?", "text", required=False,
              quick=["לבדוק אם אני משלם/ת יותר מדי דמי ניהול", "דלג"]),
]
BY_KEY = {f.key: f for f in FIELDS}
NUMERIC_KEYS = {f.key for f in FIELDS if f.kind in ("int", "money", "pct")}


def parse_answer(spec: FieldSpec, text: str, answers: dict) -> Any:
    """Returns the parsed value or raises ParseError with a user-facing reason."""
    text = (text or "").strip()
    if not text:
        raise ParseError("לא התקבלה תשובה")
    if spec.kind == "text":
        if len(text) > 200:
            raise ParseError("התשובה ארוכה מדי (עד 200 תווים)")
        return text
    if spec.kind == "marital":
        return parse_marital(text)
    if spec.kind != "money" and re.search(r"אלף|אלפים|מיליון|\d\s*[kKmM]\b", text):
        raise ParseError("לא ברור אם הכוונה לאלפים. אפשר לכתוב את המספר עצמו?")
    v = parse_number(text, allow_multipliers=spec.kind == "money")
    if spec.kind == "int":
        if v != int(v):
            raise ParseError("צריך מספר שלם")
        v = int(v)
    if spec.min is not None and v < spec.min:
        raise ParseError(f"הערך נמוך מהטווח הסביר ({_fmt_bound(spec, spec.min)} לפחות)")
    if spec.max is not None and v > spec.max:
        if spec.kind == "pct":
            raise ParseError(f"{v}% גבוה מהתקרה החוקית ({spec.max}%). אולי נפלה טעות בהקלדה?")
        raise ParseError(f"הערך גבוה מהטווח הסביר (עד {_fmt_bound(spec, spec.max)})")
    if spec.key == "planned_retirement_age" and isinstance(answers.get("age"), int) and v <= answers["age"]:
        raise ParseError("גיל הפרישה צריך להיות גבוה מהגיל הנוכחי")
    if spec.key == "age" and isinstance(answers.get("planned_retirement_age"), int) and v >= answers["planned_retirement_age"]:
        raise ParseError("הגיל צריך להיות נמוך מגיל הפרישה שהוזן")
    return v


def _fmt_bound(spec: FieldSpec, v: float) -> str:
    return f"{v:,.0f} ₪" if spec.kind == "money" else f"{v:g}"


def format_value(spec: FieldSpec, v: Any) -> str:
    if v is None:
        return "חסר" if spec.required else "—"
    if spec.kind == "money":
        return f"{v:,.0f} ₪"
    if spec.kind == "pct":
        return f"{v:.2f}%"
    return str(v)


def build_profile(answers: dict, missing: list[str]) -> dict:
    p = {f.key: answers.get(f.key) for f in FIELDS}
    p["name"] = p["name"] or "משתמש/ת"
    p["reason"] = p["reason"] or "בדיקת דמי הניהול בקרן הפנסיה"
    if not has_partner(p.get("marital_status")):
        p["spouse_age"] = None
    p["current_fund"] = None
    p["insurance"] = {"status": "not_collected",
                      "note": "פרטי הכיסוי הביטוחי לא נאספו בשיחה. הם יתווספו בשלב הבא ואינם מנותחים בגרסה זו."}
    p["_meta"] = {"kind": "user_entered", "missing": list(missing),
                  "notice": "נתונים שהוזנו בשיחה. לא אומתו מול מקור כלשהו. אין להזין נתונים אישיים אמיתיים."}
    return p
