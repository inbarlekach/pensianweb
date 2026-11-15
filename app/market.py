"""Parsing and validation of פנסיה-נט records into a fund-level market snapshot.

Facts verified against the live data (2026-11-15):
- FUND_CLASSIFICATION has two values: "קרנות חדשות" (new comprehensive funds) and
  "קרנות כלליות" (general funds). Only "קרנות חדשות" is in scope.
- Each row is one investment track (FUND_ID) per month (REPORT_PERIOD, YYYYMM).
- AVG_DEPOSIT_FEE / AVG_ANNUAL_MANAGEMENT_FEE are fund-level averages actually charged;
  in the data they repeat identically across all tracks of the same fund. Units are
  interpreted as percent (values ~1.0–1.8 and ~0.1–0.3); this is an inference from the
  value ranges vs. legal caps, recorded as a limitation.
Pure functions only — no network here, so everything is testable offline.
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel

IN_SCOPE_CLASSIFICATION = "קרנות חדשות"
REQUIRED_FIELDS = ("FUND_ID", "FUND_NAME", "PARENT_COMPANY_NAME", "FUND_CLASSIFICATION",
                   "REPORT_PERIOD", "AVG_DEPOSIT_FEE", "AVG_ANNUAL_MANAGEMENT_FEE")


class FundSummary(BaseModel):
    parent_company: str
    report_period: int
    deposit_fee_pct: Optional[float]
    accumulation_fee_pct: Optional[float]
    track_count: int
    total_assets_m: float
    comparable: bool
    issues: list[str] = []


class Rejection(BaseModel):
    fund_id: Any = None
    fund_name: Any = None
    parent_company: Any = None
    report_period: Any = None
    reason: str


class ParseResult(BaseModel):
    latest_report_period: Optional[int]
    funds: list[FundSummary]
    rejected: list[Rejection]
    in_scope_rows: int
    total_rows: int


def _num(v) -> Optional[float]:
    if v is None or v == "":
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if f != f else f


def _period(v) -> Optional[int]:
    try:
        p = int(v)
    except (TypeError, ValueError):
        return None
    y, m = divmod(p, 100)
    return p if 1990 <= y <= 2100 and 1 <= m <= 12 else None


def parse_records(records: list[dict], caps: dict[str, float]) -> ParseResult:
    """caps: {"deposit": max %, "accumulation": max %} used for range validation."""
    rejected: list[Rejection] = []
    latest_by_track: dict[Any, dict] = {}
    in_scope = 0

    for r in records:
        missing = [f for f in ("FUND_ID", "FUND_CLASSIFICATION", "REPORT_PERIOD") if r.get(f) in (None, "")]
        if missing:
            rejected.append(Rejection(fund_id=r.get("FUND_ID"), fund_name=r.get("FUND_NAME"),
                                      reason=f"שדות חסרים: {', '.join(missing)}"))
            continue
        if r["FUND_CLASSIFICATION"] != IN_SCOPE_CLASSIFICATION:
            continue
        in_scope += 1
        p = _period(r["REPORT_PERIOD"])
        if p is None:
            rejected.append(Rejection(fund_id=r["FUND_ID"], fund_name=r.get("FUND_NAME"),
                                      report_period=r["REPORT_PERIOD"], reason="תקופת דיווח לא תקינה"))
            continue
        prev = latest_by_track.get(r["FUND_ID"])
        if prev is not None and _period(prev["REPORT_PERIOD"]) == p:
            rejected.append(Rejection(fund_id=r["FUND_ID"], fund_name=r.get("FUND_NAME"),
                                      report_period=p, reason="רשומה כפולה לאותו מסלול ותקופה"))
            continue
        if prev is None or _period(prev["REPORT_PERIOD"]) < p:
            latest_by_track[r["FUND_ID"]] = r

    if not latest_by_track:
        return ParseResult(latest_report_period=None, funds=[], rejected=rejected,
                           in_scope_rows=in_scope, total_rows=len(records))

    global_latest = max(_period(r["REPORT_PERIOD"]) for r in latest_by_track.values())
    by_parent: dict[str, list[dict]] = defaultdict(list)

    for fid, r in latest_by_track.items():
        base = dict(fund_id=fid, fund_name=r.get("FUND_NAME"),
                    parent_company=r.get("PARENT_COMPANY_NAME"),
                    report_period=_period(r["REPORT_PERIOD"]))
        if not (r.get("PARENT_COMPANY_NAME") or "").strip():
            rejected.append(Rejection(**base, reason="חסר שם קרן מנהלת"))
            continue
        if base["report_period"] != global_latest:
            rejected.append(Rejection(**base, reason=f"המסלול לא דווח בתקופה האחרונה ({global_latest})"))
            continue
        d, a = _num(r.get("AVG_DEPOSIT_FEE")), _num(r.get("AVG_ANNUAL_MANAGEMENT_FEE"))
        if d is None or a is None:
            rejected.append(Rejection(**base, reason="דמי ניהול חסרים במקור"))
            continue
        if not (0 <= d <= caps["deposit"]) or not (0 <= a <= caps["accumulation"]):
            rejected.append(Rejection(**base, reason=f"דמי ניהול מחוץ לטווח החוקי (הפקדה {d}, צבירה {a})"))
            continue
        by_parent[" ".join(r["PARENT_COMPANY_NAME"].split())].append(r)

    funds: list[FundSummary] = []
    for parent, rows in sorted(by_parent.items()):
        fees = {(_num(x["AVG_DEPOSIT_FEE"]), _num(x["AVG_ANNUAL_MANAGEMENT_FEE"])) for x in rows}
        assets = sum(_num(x.get("TOTAL_ASSETS")) or 0.0 for x in rows)
        if len(fees) == 1:
            (d, a), = fees
            funds.append(FundSummary(parent_company=parent, report_period=global_latest,
                                     deposit_fee_pct=d, accumulation_fee_pct=a,
                                     track_count=len(rows), total_assets_m=round(assets, 2),
                                     comparable=True))
        else:
            funds.append(FundSummary(parent_company=parent, report_period=global_latest,
                                     deposit_fee_pct=None, accumulation_fee_pct=None,
                                     track_count=len(rows), total_assets_m=round(assets, 2),
                                     comparable=False,
                                     issues=[f"דמי ניהול שונים בין מסלולי אותה קרן: {sorted(fees)}"]))

    return ParseResult(latest_report_period=global_latest, funds=funds, rejected=rejected,
                       in_scope_rows=in_scope, total_rows=len(records))


# --- snapshot / manifest I/O --------------------------------------------------

def load_manifest(market_dir: Path) -> Optional[dict]:
    p = market_dir / "manifest.json"
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def load_current_snapshot(market_dir: Path) -> tuple[Optional[dict], Optional[dict]]:
    """Returns (manifest, snapshot). Either may be None; callers must handle it."""
    m = load_manifest(market_dir)
    if not m or not m.get("current_snapshot"):
        return m, None
    p = market_dir / m["current_snapshot"]
    if not p.exists():
        return m, None
    return m, json.loads(p.read_text(encoding="utf-8"))
