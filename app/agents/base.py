"""Provider-agnostic interface for the fee-analysis agent.

The agent receives ONLY structured, already-decided facts (drafts from app.rules plus
calculated values) and returns wording. It cannot change certainty, risk, ranking or
amounts, and every number it writes is checked by app.agents.guard.
To plug a real LLM provider later: implement FeeAnalystAgent in a new module, read the
API key from an environment variable (never from source), and select it in
app.agents.get_agent().
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Literal

from pydantic import BaseModel

from ..models import CalcResult


class DraftIn(BaseModel):
    finding_id: str
    kind: str
    certainty: int
    risk: str
    calc_refs: list[str]
    source_refs: list[str]
    facts: dict


class AnalysisInput(BaseModel):
    profile_summary: dict
    calcs: dict[str, CalcResult]
    drafts: list[DraftIn]
    source_ids: list[str]


class WordedFinding(BaseModel):
    finding_id: str
    title: str
    finding: str
    explanation: str
    next_step: str


class AgentOutput(BaseModel):
    generated_by: Literal["template", "llm"]
    provider: str
    findings: list[WordedFinding]


class FeeAnalystAgent(ABC):
    @abstractmethod
    def analyze(self, inp: AnalysisInput) -> AgentOutput: ...
