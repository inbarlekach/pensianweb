"""Data-collection failure tests (category 06). Network is mocked with httpx.MockTransport;
no real requests are made."""
import json

import httpx
import pytest

from app.market import load_current_snapshot
from scripts.refresh_market_data import refresh

from .helpers import TODAY, analyze, rec

ING = pytest.mark.cat("06 כשלים באיסוף נתונים")

GOOD = [rec(1, "קרן א", d=1.0, a=0.18), rec(2, "קרן א", d=1.0, a=0.18), rec(3, "קרן ב", d=1.5, a=0.14),
        rec(4, "קרן כללית", cls="קרנות כלליות")]


def client(records=GOOD, total=None, status=200, success=True, exc=None):
    def h(req):
        if exc:
            raise exc(req)
        if req.url.path.endswith("resource_show"):
            return httpx.Response(200, json={"success": True, "result": {"last_modified": "2026-11-15T05:00:34"}})
        if status != 200:
            return httpx.Response(status, text="error")
        off, lim = int(req.url.params.get("offset", 0)), int(req.url.params["limit"])
        return httpx.Response(200, json={"success": success, "result": {
            "records": records[off:off + lim], "total": len(records) if total is None else total}})
    return httpx.Client(transport=httpx.MockTransport(h))


def manifest(d):
    return json.loads((d / "manifest.json").read_text(encoding="utf-8"))


@ING
@pytest.mark.critical
def test_success_writes_snapshot(tmp_path):
    """תשובה תקינה ← נוצרים snapshot ו-manifest, נכללות 2 קרנות מקיפות בלבד"""
    a = refresh(client(), tmp_path)
    assert a["status"] == "success"
    m, s = load_current_snapshot(tmp_path)
    assert [f["parent_company"] for f in s["funds"]] == ["קרן א", "קרן ב"]
    assert m["sources"][0]["verification_status"] == "verified"


@ING
@pytest.mark.critical
def test_http_500_keeps_previous_snapshot(tmp_path):
    """רענון מוצלח ואחריו HTTP 500 ← ה-snapshot הקודם נשאר, הניסיון מסומן failed"""
    refresh(client(), tmp_path)
    prev = manifest(tmp_path)["current_snapshot"]
    a = refresh(client(status=500), tmp_path)
    m = manifest(tmp_path)
    assert a["status"] == "failed"
    assert m["current_snapshot"] == prev and (tmp_path / prev).exists()
    assert m["last_attempt"]["status"] == "failed"


@ING
def test_timeout_fails(tmp_path):
    """Timeout ברשת ← failed, אין snapshot"""
    a = refresh(client(exc=lambda r: httpx.ReadTimeout("timeout", request=r)), tmp_path)
    assert a["status"] == "failed" and manifest(tmp_path)["current_snapshot"] is None


@ING
def test_api_success_false_fails(tmp_path):
    """ה-API מחזיר success=false ← failed"""
    assert refresh(client(success=False), tmp_path)["status"] == "failed"


@ING
def test_schema_change_fails(tmp_path):
    """עמודת דמי ניהול נעלמה מהמקור ← failed עם הודעה על שינוי מבנה"""
    bad = [{k: v for k, v in r.items() if k != "AVG_DEPOSIT_FEE"} for r in GOOD]
    a = refresh(client(records=bad), tmp_path)
    assert a["status"] == "failed" and "מבנה הנתונים השתנה" in a["error"]


@ING
def test_partial_download_fails(tmp_path):
    """התקבלו פחות רשומות מה-total ← failed (לא נשמר מידע חלקי)"""
    a = refresh(client(total=len(GOOD) + 5), tmp_path)
    assert a["status"] == "failed" and manifest(tmp_path)["current_snapshot"] is None


@ING
def test_no_in_scope_funds_fails(tmp_path):
    """רק קרנות כלליות במקור ← failed"""
    a = refresh(client(records=[rec(1, "כללית", cls="קרנות כלליות")]), tmp_path)
    assert a["status"] == "failed"


@ING
@pytest.mark.critical
def test_ui_warned_after_failed_refresh(tmp_path):
    """רענון נכשל אחרי הצלחה ← הניתוח רץ על הנתונים הקודמים ומסמן last_refresh_failed"""
    refresh(client(), tmp_path)
    refresh(client(status=503), tmp_path)
    m, s = load_current_snapshot(tmp_path)
    r = analyze(snap=s, manifest=m, today=TODAY)
    assert r["market"]["last_refresh_failed"] is True
    assert any("נכשל" in x for x in r["market"]["messages"])
