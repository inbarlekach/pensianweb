"""Web entry point. Run: .venv\\Scripts\\python -m uvicorn app.main:app --port 8000

Profiles entered in the chat are never stored on the server: the browser keeps them
(sessionStorage) and sends them with each request.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any, Optional

from fastapi import Body, FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError

from . import orchestrator, rules
from .agents import get_agent
from .agents.interviewer import InterviewState, get_interviewer
from .calc.fees import monthly_deposit
from .market import load_current_snapshot
from .models import Profile

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
STATIC = Path(__file__).parent / "static"

app = FastAPI(title="Pension fee demo", docs_url=None, redoc_url=None)


def _json(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


def _with_derived(p: dict) -> dict:
    """Adds code-computed display values and validation problems to a profile."""
    a = _json(DATA / "assumptions.json")
    rate = a["contribution_rate"]["value"]
    out = dict(p)
    errors: list[str] = []
    try:
        model = Profile.model_validate(p)
        caps = {k: a["legal_fee_caps_pct"][k] for k in ("deposit", "accumulation")}
        errors += rules.check_profile(model, caps)
    except ValidationError as e:
        errors += [f"שדה חסר או לא תקין: {orchestrator.field_label('.'.join(map(str, er['loc'])))}" for er in e.errors()]
    salary, age, ret = p.get("gross_monthly_salary"), p.get("age"), p.get("planned_retirement_age")
    out["derived"] = {
        "monthly_deposit": round(monthly_deposit(salary, rate), 2) if isinstance(salary, (int, float)) and salary > 0 else None,
        "contribution_rate": rate,
        "contribution_rate_status": a["contribution_rate"]["status"],
        "years_to_retirement": (ret - age) if isinstance(age, int) and isinstance(ret, int) else None,
    }
    out["validation_errors"] = errors
    return out


@app.get("/api/profile")
def demo_profile():
    return _with_derived(_json(DATA / "profile_ido.json"))


@app.post("/api/profile/preview")
def profile_preview(body: dict = Body(...)):
    return _with_derived(body.get("profile") or {})


@app.post("/api/interview")
def interview(body: dict = Body(default={})):
    try:
        state = InterviewState.model_validate(body.get("state") or {})
    except ValidationError:
        state = InterviewState()
    turn = get_interviewer().step(state, body.get("message"))
    return turn.model_dump(mode="json")


@app.get("/api/assumptions")
def assumptions():
    return _json(DATA / "assumptions.json")


@app.get("/api/sources")
def sources():
    manifest, snapshot = load_current_snapshot(DATA / "market")
    return {
        "manifest": manifest,
        "snapshot": None if snapshot is None else {
            k: snapshot.get(k) for k in ("snapshot_id", "collected_at", "resource_last_modified",
                                         "latest_report_period", "coverage", "funds", "rejected")},
    }


@app.post("/api/analyze")
def analyze(body: Optional[dict[str, Any]] = Body(default=None)):
    manifest, snapshot = load_current_snapshot(DATA / "market")
    try:
        agent = get_agent()
    except RuntimeError as e:
        return JSONResponse({"status": "failed", "error": str(e), "steps": [], "findings": []}, status_code=500)
    profile = (body or {}).get("profile") or _json(DATA / "profile_ido.json")
    return orchestrator.run(profile, _json(DATA / "assumptions.json"), manifest, snapshot, agent, date.today())


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


app.mount("/static", StaticFiles(directory=STATIC), name="static")
