"""Structured data passed between components. No free text crosses component borders
without a schema."""
from __future__ import annotations

from enum import IntEnum, Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field


class Profile(BaseModel):
    name: str
    age: int = Field(ge=18, le=80)
    gross_monthly_salary: float = Field(gt=0)
    accumulated_balance: float = Field(ge=0)
    accumulation_fee_pct: float = Field(ge=0, lt=100)
    deposit_fee_pct: float = Field(ge=0, lt=100)
    marital_status: Optional[str] = None
    spouse_age: Optional[int] = None
    children: Optional[int] = Field(default=None, ge=0)
    planned_retirement_age: int = Field(ge=50, le=80)


class MarketFund(BaseModel):
    """One fund/track row from a market snapshot. Fees are fund-level AVERAGES actually
    charged (פנסיה-נט), never an offer to a specific user."""
    fund_id: int
    fund_name: str
    parent_company: str
    report_period: int  # YYYYMM
    avg_deposit_fee_pct: float
    avg_accumulation_fee_pct: float
    total_assets_m: Optional[float] = None
    avg_annual_yield_5y_pct: Optional[float] = None
    source_id: str


class SourceRecord(BaseModel):
    source_id: str
    name: str
    publisher: str
    url: str
    data_type: str
    collected_at: Optional[str] = None
    published_or_updated: Optional[str] = None
    verification_status: Literal["verified", "partial", "not_checked", "failed"]
    known_limitations: list[str] = []
    coverage: Optional[str] = None


class Certainty(IntEnum):
    VERIFIED = 1      # רמה 1: מידע מספק ומאומת
    INDICATION = 2    # רמה 2: אינדיקציה להזדמנות
    INSUFFICIENT = 3  # רמה 3: אין די מידע


class Risk(str, Enum):
    LOW = "low"
    HIGH = "high"


class CalcResult(BaseModel):
    calc_id: str
    label: str
    value: float
    unit: Literal["ILS", "pct"]
    kind: Literal["fact", "estimate"]
    formula: str


class Finding(BaseModel):
    finding_id: str
    title: str
    finding: str
    explanation: str
    next_step: str
    certainty: Certainty
    risk: Risk
    calc_refs: list[str]
    source_refs: list[str]
    assumptions: list[str]
    limitations: list[str]
    ranking_value_ils: Optional[float] = None
    generated_by: Literal["template", "llm"]
