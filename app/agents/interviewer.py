"""Profile interview. Stateless: the client sends the state back with each message.

ScriptedInterviewer is a deterministic stand-in (generated_by="script"). A future LLM
interviewer must implement the same interface and still pass every extracted value
through app.intake.parse_answer — the model may phrase questions, never set values.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Literal, Optional

from pydantic import BaseModel

from .. import intake
from ..intake import BY_KEY, CONTINUE_WITHOUT, FIELDS, ParseError

RESTART = "התחל מחדש"
CONFIRM = "אישור ויצירת פרופיל"
EDIT_PREFIX = "לתקן:"


class InterviewState(BaseModel):
    phase: Literal["start", "ask", "confirm", "done"] = "start"
    current: Optional[str] = None
    answers: dict[str, Any] = {}
    missing: list[str] = []
    retries: int = 0
    editing: bool = False


class SummaryRow(BaseModel):
    key: str
    label: str
    value: str
    missing: bool


class InterviewTurn(BaseModel):
    state: InterviewState
    messages: list[str]
    quick_replies: list[str] = []
    summary: Optional[list[SummaryRow]] = None
    profile: Optional[dict] = None
    field: Optional[str] = None
    generated_by: Literal["script", "llm"] = "script"


class ProfileInterviewer(ABC):
    @abstractmethod
    def step(self, state: InterviewState, message: Optional[str]) -> InterviewTurn: ...


def _applicable(answers: dict) -> list:
    return [f for f in FIELDS if f.condition(answers)]


def _next_field(answers: dict, missing: list[str]) -> Optional[str]:
    for f in _applicable(answers):
        if f.key not in answers and f.key not in missing:
            return f.key
    return None


def _summary(st: InterviewState) -> list[SummaryRow]:
    return [SummaryRow(key=f.key, label=f.label, value=intake.format_value(f, st.answers.get(f.key)),
                       missing=f.required and st.answers.get(f.key) is None)
            for f in _applicable(st.answers)]


class ScriptedInterviewer(ProfileInterviewer):
    def _ask(self, st: InterviewState, key: str, pre: list[str]) -> InterviewTurn:
        f = BY_KEY[key]
        st.phase, st.current, st.retries = "ask", key, 0
        quick = list(f.quick)
        return InterviewTurn(state=st, messages=pre + [f.question], quick_replies=quick, field=key)

    def _confirm(self, st: InterviewState, pre: list[str]) -> InterviewTurn:
        st.phase, st.current, st.editing = "confirm", None, False
        rows = _summary(st)
        msgs = pre + ["זה מה שרשמתי. אפשר לתקן כל שדה, או לאשר וליצור את הפרופיל."]
        if any(r.missing for r in rows):
            msgs.append("שים/י לב: חסרים נתונים שנדרשים להשוואה. אפשר ליצור את הפרופיל, אבל הניתוח יציין מה חסר ולא יציג השוואה.")
        return InterviewTurn(state=st, messages=msgs, quick_replies=[CONFIRM, RESTART], summary=rows)

    def _advance(self, st: InterviewState, pre: list[str]) -> InterviewTurn:
        if st.editing:
            return self._confirm(st, pre)
        nxt = _next_field(st.answers, st.missing)
        return self._ask(st, nxt, pre) if nxt else self._confirm(st, pre)

    def step(self, state: InterviewState, message: Optional[str]) -> InterviewTurn:
        st = state.model_copy(deep=True)
        text = (message or "").strip()

        if st.phase == "start" or text == RESTART:
            st = InterviewState()
            intro = ["שלום! אשאל כמה שאלות קצרות כדי לבנות פרופיל פנסיוני לבדיקת דמי הניהול.",
                     "⚠️ זהו אבטיפוס לימודי. אל תזין/י נתונים אישיים או פיננסיים אמיתיים. אפשר להמציא ערכים, או לטעון את פרופיל ההדגמה של עידו."]
            return self._ask(st, FIELDS[0].key, intro)

        if st.phase == "done":
            return InterviewTurn(state=st, messages=["הפרופיל כבר נוצר. כדי להתחיל שיחה חדשה, בחר/י 'התחל מחדש'."],
                                 quick_replies=[RESTART])

        if text.startswith(EDIT_PREFIX):
            label = text[len(EDIT_PREFIX):].strip()
            f = next((x for x in _applicable(st.answers) if x.label == label or x.key == label), None)
            if not f:
                return InterviewTurn(state=st, messages=["לא מצאתי שדה בשם הזה."], summary=_summary(st),
                                     quick_replies=[CONFIRM, RESTART])
            st.answers.pop(f.key, None)
            if f.key in st.missing:
                st.missing.remove(f.key)
            st.editing = True
            return self._ask(st, f.key, [f"בסדר, נעדכן את '{f.label}'."])

        if st.phase == "confirm":
            if text == CONFIRM:
                st.phase = "done"
                profile = intake.build_profile(st.answers, st.missing)
                return InterviewTurn(state=st, messages=["הפרופיל נוצר ✓ הוא יוצג במסך הפרופיל וישמש לניתוח."],
                                     profile=profile, summary=_summary(st))
            return self._confirm(st, ["לא הבנתי. אפשר לאשר, לתקן שדה או להתחיל מחדש."])

        # phase == ask
        f = BY_KEY[st.current]
        if intake.is_skip(text):
            if not f.required:
                st.answers[f.key] = None
                return self._advance(st, [])
            if text == CONTINUE_WITHOUT:
                st.missing.append(f.key)
                return self._advance(st, [f"רשמתי ש'{f.label}' חסר. בלי הנתון הזה לא נוכל להשוות לשוק."])
            msgs = ["זה בסדר, הרבה אנשים לא יודעים."]
            if f.help:
                msgs.append(f.help)
            msgs.append("אם אפשר לבדוק עכשיו, כתוב/י את הערך. אחרת אפשר להמשיך בלי הנתון.")
            return InterviewTurn(state=st, messages=msgs, quick_replies=[CONTINUE_WITHOUT], field=f.key)
        try:
            value = intake.parse_answer(f, text, st.answers)
        except ParseError as e:
            st.retries += 1
            msgs = [f"{e}."]
            if f.help and st.retries >= 1:
                msgs.append(f.help)
            msgs.append(f.question)
            quick = list(f.quick) + ([CONTINUE_WITHOUT] if f.required and st.retries >= 2 else [])
            return InterviewTurn(state=st, messages=msgs, quick_replies=quick, field=f.key)
        st.answers[f.key] = value
        if f.key == "marital_status" and not intake.has_partner(value):
            st.answers.pop("spouse_age", None)
        return self._advance(st, [f"רשמתי: {f.label} – {intake.format_value(f, value)}."])


def get_interviewer() -> ProfileInterviewer:
    return ScriptedInterviewer()
