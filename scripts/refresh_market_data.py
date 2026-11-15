"""Operator-only market data refresh. Run manually:
    .venv\\Scripts\\python scripts\\refresh_market_data.py
Not exposed through the web app. On failure the previous snapshot stays in place and the
manifest records the failed attempt, so the UI can say the data was not refreshed.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.market import parse_records, load_manifest  # noqa: E402

API = "https://data.gov.il/api/3/action"
RESOURCE_ID = "6d47d6b5-cb08-488b-b333-f1e717b1e1bd"
DATASET_URL = "https://data.gov.il/dataset/pensia-net"
SOURCE_ID = "pensianet_2024_now"
MARKET_DIR = ROOT / "data" / "market"
PAGE = 5000

STATIC_SOURCES = [
    {
        "source_id": "cma_fee_calculator",
        "name": "מחשבון דמי ניהול של רשות שוק ההון",
        "publisher": "רשות שוק ההון, ביטוח וחיסכון",
        "url": "https://nihul.cma.gov.il/",
        "data_type": "דמי ניהול מוצעים לפי מאפייני חוסך",
        "verification_status": "not_checked",
        "known_limitations": ["האתר חסם גישה אוטומטית (HTTP 403) ולא נבדק ידנית. לא נעשה בו שימוש בדמו."],
    },
    {
        "source_id": "pensyanet_portal",
        "name": "פורטל פנסיה-נט",
        "publisher": "רשות שוק ההון, ביטוח וחיסכון",
        "url": "https://pensyanet.cma.gov.il/Parameters/Index",
        "data_type": "ממשק צפייה בנתוני קרנות",
        "verification_status": "not_checked",
        "known_limitations": ["החיבור נותק בניסיון הגישה. הנתונים נלקחו במקום זאת ממאגר data.gov.il."],
    },
]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def fetch_all(client: httpx.Client) -> tuple[list[dict], dict]:
    meta = client.get(f"{API}/resource_show", params={"id": RESOURCE_ID})
    meta.raise_for_status()
    meta_j = meta.json()
    if not meta_j.get("success"):
        raise RuntimeError("resource_show החזיר success=false")
    records, offset, total = [], 0, None
    while True:
        r = client.get(f"{API}/datastore_search",
                       params={"resource_id": RESOURCE_ID, "limit": PAGE, "offset": offset})
        r.raise_for_status()
        j = r.json()
        if not j.get("success"):
            raise RuntimeError("datastore_search החזיר success=false")
        res = j["result"]
        total = res.get("total")
        batch = res.get("records") or []
        records += batch
        offset += len(batch)
        if not batch or (total is not None and offset >= total):
            break
    if total is not None and len(records) != total:
        raise RuntimeError(f"התקבלו {len(records)} רשומות מתוך {total}")
    return records, meta_j["result"]


def refresh(client: httpx.Client | None = None, market_dir: Path = MARKET_DIR) -> dict:
    market_dir.mkdir(parents=True, exist_ok=True)
    assumptions = json.loads((ROOT / "data" / "assumptions.json").read_text(encoding="utf-8"))
    caps = {k: assumptions["legal_fee_caps_pct"][k] for k in ("deposit", "accumulation")}
    manifest = load_manifest(market_dir) or {"current_snapshot": None, "history": []}
    attempt = {"at": now_iso(), "source_id": SOURCE_ID}
    own_client = client is None
    client = client or httpx.Client(timeout=60, headers={"User-Agent": "pension-demo-student-project"})
    try:
        records, meta = fetch_all(client)
        missing_cols = [c for c in ("FUND_ID", "FUND_CLASSIFICATION", "REPORT_PERIOD",
                                    "PARENT_COMPANY_NAME", "AVG_DEPOSIT_FEE", "AVG_ANNUAL_MANAGEMENT_FEE")
                        if records and c not in records[0]]
        if missing_cols:
            raise RuntimeError(f"מבנה הנתונים השתנה, חסרות עמודות: {missing_cols}")
        parsed = parse_records(records, caps)
        if not parsed.funds:
            raise RuntimeError("לא נמצאו קרנות פנסיה חדשות מקיפות תקינות בנתונים")
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        name = f"snapshot_{stamp}.json"
        comparable = [f for f in parsed.funds if f.comparable]
        snapshot = {
            "snapshot_id": stamp,
            "source_id": SOURCE_ID,
            "collected_at": attempt["at"],
            "resource_last_modified": meta.get("last_modified"),
            "latest_report_period": parsed.latest_report_period,
            "total_rows": parsed.total_rows,
            "in_scope_rows": parsed.in_scope_rows,
            "coverage": {
                "funds_found": len(parsed.funds),
                "funds_comparable": len(comparable),
                "tracks_included": sum(f.track_count for f in parsed.funds),
                "rows_rejected": len(parsed.rejected),
                "note": "הכיסוי מחושב מתוך מה שהתקבל מהמקור בלבד. אין טענה לכיסוי מלא של השוק.",
            },
            "funds": [f.model_dump() for f in parsed.funds],
            "rejected": [x.model_dump() for x in parsed.rejected],
        }
        (market_dir / name).write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
        attempt.update(status="success", snapshot=name)
        manifest["current_snapshot"] = name
        manifest["sources"] = [{
            "source_id": SOURCE_ID,
            "name": "פנסיה-נט: נתוני קרנות פנסיה לשנים 2024–היום",
            "publisher": "רשות שוק ההון, ביטוח וחיסכון (באמצעות data.gov.il)",
            "url": DATASET_URL,
            "api": f"{API}/datastore_search?resource_id={RESOURCE_ID}",
            "data_type": "נתונים חודשיים לכל מסלול: דמי ניהול ממוצעים שנגבו בפועל, נכסים, תשואות",
            "collected_at": attempt["at"],
            "published_or_updated": meta.get("last_modified"),
            "verification_status": "verified",
            "known_limitations": [
                "דמי הניהול הם ממוצע שנגבה בפועל מכלל העמיתים בקרן, ולא הצעה לחוסך מסוים.",
                "יחידות שדות דמי הניהול פורשו כאחוזים לפי טווח הערכים; המקור לא מציין יחידות במפורש.",
                "הנתונים מתפרסמים בפיגור של כחודשיים.",
            ],
            "coverage": f"{len(comparable)} קרנות מקיפות ברות-השוואה, תקופה {parsed.latest_report_period}",
        }] + STATIC_SOURCES
    except Exception as e:  # any failure: keep previous snapshot, record failure
        attempt.update(status="failed", error=f"{type(e).__name__}: {e}")
    finally:
        if own_client:
            client.close()
    manifest["last_attempt"] = attempt
    manifest.setdefault("history", []).append(attempt)
    manifest["history"] = manifest["history"][-20:]
    (market_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return attempt


if __name__ == "__main__":
    result = refresh()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0 if result["status"] == "success" else 1)
