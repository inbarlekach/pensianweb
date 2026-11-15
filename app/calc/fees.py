"""Deterministic monthly savings simulation. All money math lives here, never in an LLM.

Monthly order of operations (documented and tested):
  1. deposit fee   = deposit * deposit_fee_pct/100;  balance += deposit - deposit fee
  2. return        : balance *= (1 + r_m), where r_m = (1 + annual_return)^(1/12) - 1
  3. accum. fee    = balance * accumulation_fee_pct/100 / 12;  balance -= accum. fee
The accumulation fee is accrued monthly as 1/12 of the annual rate on the balance after
return. This is a modelling choice (stated to the user), not a quote of any fund's
regulations.
Salary (and therefore deposit) grows once a year by salary_growth_annual.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class FeeTerms:
    deposit_fee_pct: float        # e.g. 2.0 means 2% of each deposit
    accumulation_fee_pct: float   # e.g. 0.30 means 0.30% of balance per year

    def __post_init__(self):
        for name in ("deposit_fee_pct", "accumulation_fee_pct"):
            v = getattr(self, name)
            if v is None or not isinstance(v, (int, float)) or v != v:
                raise ValueError(f"{name} חסר או אינו מספר")
            if v < 0 or v >= 100:
                raise ValueError(f"{name}={v} מחוץ לטווח 0–100")


@dataclass(frozen=True)
class SimInput:
    start_balance: float
    monthly_deposit: float
    months: int
    annual_return: float
    salary_growth_annual: float = 0.0

    def __post_init__(self):
        if self.start_balance < 0:
            raise ValueError("צבירה התחלתית שלילית")
        if self.monthly_deposit < 0:
            raise ValueError("הפקדה חודשית שלילית")
        if not isinstance(self.months, int) or self.months < 0:
            raise ValueError("מספר חודשים לא תקין")
        if self.annual_return <= -1:
            raise ValueError("תשואה שנתית לא תקינה")


@dataclass
class SimResult:
    final_balance: float
    total_deposits: float
    total_deposit_fees: float
    total_accumulation_fees: float
    yearly_balances: list[float] = field(default_factory=list)

    @property
    def total_fees(self) -> float:
        return self.total_deposit_fees + self.total_accumulation_fees


def monthly_rate(annual_return: float) -> float:
    return (1.0 + annual_return) ** (1.0 / 12.0) - 1.0


def simulate(inp: SimInput, fees: FeeTerms) -> SimResult:
    r_m = monthly_rate(inp.annual_return)
    d = fees.deposit_fee_pct / 100.0
    a = fees.accumulation_fee_pct / 100.0 / 12.0
    balance = float(inp.start_balance)
    deposit = float(inp.monthly_deposit)
    tot_dep = tot_dep_fee = tot_acc_fee = 0.0
    yearly: list[float] = []
    for m in range(inp.months):
        if m > 0 and m % 12 == 0:
            deposit *= 1.0 + inp.salary_growth_annual
        dep_fee = deposit * d
        balance += deposit - dep_fee
        balance *= 1.0 + r_m
        acc_fee = balance * a
        balance -= acc_fee
        tot_dep += deposit
        tot_dep_fee += dep_fee
        tot_acc_fee += acc_fee
        if (m + 1) % 12 == 0:
            yearly.append(balance)
    return SimResult(balance, tot_dep, tot_dep_fee, tot_acc_fee, yearly)


def months_to_retirement(age: int, retirement_age: int) -> int:
    if retirement_age <= age:
        raise ValueError("גיל הפרישה חייב להיות גבוה מהגיל הנוכחי")
    return (retirement_age - age) * 12


def monthly_deposit(gross_salary: float, contribution_rate: float) -> float:
    if gross_salary <= 0:
        raise ValueError("שכר חייב להיות חיובי")
    if not 0 < contribution_rate < 1:
        raise ValueError("שיעור הפקדה חייב להיות בין 0 ל-1")
    return gross_salary * contribution_rate
