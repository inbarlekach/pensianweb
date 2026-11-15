"""Test categories + a per-case report (tests/REPORT.md).

Markers:
  cat(name)    – the test-plan category of the case.
  critical     – the case checks a critical field (fees, balances, deposit, gap, certainty,
                 risk, source date). A failing critical case = a silent error candidate.
  alarm_check  – the case expects NO opportunity/alarm. A failure = a false alarm.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from pathlib import Path

import pytest

_results: list[dict] = []


def pytest_configure(config):
    config.addinivalue_line("markers", "cat(name): test-plan category")
    config.addinivalue_line("markers", "critical: checks a critical field")
    config.addinivalue_line("markers", "alarm_check: expects no alarm/opportunity")


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    rep = outcome.get_result()
    if rep.when == "call" or (rep.when == "setup" and rep.outcome != "passed"):
        m = item.get_closest_marker("cat")
        _results.append({
            "id": item.nodeid.split("::", 1)[-1],
            "cat": m.args[0] if m else "ללא קטגוריה",
            "desc": (item.function.__doc__ or "").strip().splitlines()[0] if item.function.__doc__ else "",
            "outcome": rep.outcome,
            "critical": item.get_closest_marker("critical") is not None,
            "alarm": item.get_closest_marker("alarm_check") is not None,
        })


def pytest_sessionfinish(session, exitstatus):
    if not _results:
        return
    by_cat = defaultdict(list)
    for r in _results:
        by_cat[r["cat"]].append(r)
    total = len(_results)
    passed = sum(r["outcome"] == "passed" for r in _results)
    crit = [r for r in _results if r["critical"]]
    alarms = [r for r in _results if r["alarm"]]
    silent = sum(r["outcome"] != "passed" for r in crit)
    false_alarm = sum(r["outcome"] != "passed" for r in alarms)
    lines = [
        "# דוח מקרי בדיקה",
        "",
        f"נוצר אוטומטית: {datetime.now():%Y-%m-%d %H:%M}. הקובץ נכתב מחדש בכל ריצה של pytest.",
        "",
        f"- **סה\"כ מקרים:** {total} · **עברו:** {passed} · **נכשלו:** {total - passed}",
        f"- **טעויות שקטות** (כשל במקרה שבודק שדה קריטי): {silent} מתוך {len(crit)} מקרים קריטיים",
        f"- **התראות שווא** (נוצרה הזדמנות במקרה שבו אין לצפות לה): {false_alarm} מתוך {len(alarms)} מקרי ביקורת"
        + (f" ({false_alarm / len(alarms):.0%})" if alarms else ""),
        "",
        "> **מגבלה:** הצלחה במקרי הבדיקה מראה שהמערכת מתנהגת כמצופה במקרים שהוגדרו. אין בה הוכחה לשיעור דיוק בעולם האמיתי.",
        "> מערך הבדיקה אינו מדגם מייצג של חוסכים.",
        "",
        "## לפי קטגוריה",
        "",
        "| קטגוריה | מקרים | עברו |",
        "|---|---|---|",
    ]
    for c, rs in sorted(by_cat.items()):
        lines.append(f"| {c} | {len(rs)} | {sum(r['outcome'] == 'passed' for r in rs)} |")
    lines += ["", "## פירוט", ""]
    for c, rs in sorted(by_cat.items()):
        lines += [f"### {c}", "", "| מקרה | תיאור (קלט ← תוצאה צפויה) | תוצאה בפועל |", "|---|---|---|"]
        for r in rs:
            flag = (" 🔒" if r["critical"] else "") + (" 🔕" if r["alarm"] else "")
            res = "✅ עבר" if r["outcome"] == "passed" else "❌ נכשל"
            lines.append(f"| `{r['id']}`{flag} | {r['desc']} | {res} |")
        lines.append("")
    lines += ["🔒 = שדה קריטי · 🔕 = מקרה ביקורת להתראות שווא", ""]
    Path(__file__).with_name("REPORT.md").write_text("\n".join(lines), encoding="utf-8")
