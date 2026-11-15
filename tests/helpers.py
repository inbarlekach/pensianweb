import copy
import json
from datetime import date
from pathlib import Path

from app.agents.mock_provider import TemplateAgent
from app.orchestrator import run

ROOT = Path(__file__).resolve().parents[1]
TODAY = date(2026, 11, 15)
ASSUMPTIONS = json.loads((ROOT / "data" / "assumptions.json").read_text(encoding="utf-8"))
IDO = json.loads((ROOT / "data" / "profile_ido.json").read_text(encoding="utf-8"))
CAPS = {"deposit": 6.0, "accumulation": 0.5}


def fund(name, d, a, period=202609, comparable=True, tracks=3):
    return {"parent_company": name, "report_period": period, "deposit_fee_pct": d,
            "accumulation_fee_pct": a, "track_count": tracks, "total_assets_m": 1000.0,
            "comparable": comparable, "issues": []}


DEFAULT_FUNDS = [fund("קרן א", 1.0, 0.18), fund("קרן ב", 1.25, 0.11), fund("קרן ג", 1.47, 0.16),
                 fund("קרן ד", 1.52, 0.14), fund("קרן ה", 1.73, 0.15)]


def snapshot(funds=None, period=202609):
    return {"snapshot_id": "test", "collected_at": "2026-11-15T00:00:00+00:00",
            "latest_report_period": period, "funds": DEFAULT_FUNDS if funds is None else funds,
            "coverage": {}, "rejected": []}


MANIFEST_OK = {"current_snapshot": "x", "last_attempt": {"at": "2026-11-15T00:00:00+00:00", "status": "success"}}


def profile(**changes):
    p = copy.deepcopy(IDO)
    for k, v in changes.items():
        if v is _DROP:
            p.pop(k, None)
        else:
            p[k] = v
    return p


_DROP = object()
DROP = _DROP


def assumptions(**changes):
    a = copy.deepcopy(ASSUMPTIONS)
    for path, v in changes.items():
        node = a
        keys = path.split("__")
        for k in keys[:-1]:
            node = node[k]
        node[keys[-1]] = v
    return a


def analyze(prof=None, snap="default", manifest=MANIFEST_OK, agent=None, today=TODAY, assm=None):
    return run(prof if prof is not None else profile(), assm or ASSUMPTIONS, manifest,
               snapshot() if snap == "default" else snap, agent or TemplateAgent(), today)


def rec(fid, parent, period=202609, d=1.2, a=0.15, cls="קרנות חדשות", assets=100.0, name=None):
    return {"FUND_ID": fid, "FUND_NAME": name or f"{parent} מסלול {fid}", "PARENT_COMPANY_NAME": parent,
            "FUND_CLASSIFICATION": cls, "REPORT_PERIOD": period, "AVG_DEPOSIT_FEE": d,
            "AVG_ANNUAL_MANAGEMENT_FEE": a, "TOTAL_ASSETS": assets}
