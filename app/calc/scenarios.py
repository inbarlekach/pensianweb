"""Current vs. alternative terms across the three return scenarios."""
from __future__ import annotations

from dataclasses import dataclass

from .fees import FeeTerms, SimInput, simulate, months_to_retirement, monthly_deposit


@dataclass
class ScenarioComparison:
    scenario: str
    annual_return: float
    current_final: float
    alternative_final: float
    current_fees: float
    alternative_fees: float
    current_yearly: list[float]
    alternative_yearly: list[float]

    @property
    def gap_at_retirement(self) -> float:
        return self.alternative_final - self.current_final


@dataclass
class Comparison:
    monthly_deposit: float
    months: int
    first_year_fee_saving: float
    first_year_deposit_fee_saving: float
    first_year_accumulation_fee_saving: float
    scenarios: list[ScenarioComparison]

    def by_name(self, name: str) -> ScenarioComparison:
        for s in self.scenarios:
            if s.scenario == name:
                return s
        raise KeyError(name)


def compare(*, age: int, retirement_age: int, salary: float, balance: float,
            contribution_rate: float, salary_growth: float,
            scenario_returns: dict[str, float],
            current: FeeTerms, alternative: FeeTerms) -> Comparison:
    dep = monthly_deposit(salary, contribution_rate)
    months = months_to_retirement(age, retirement_age)
    if not scenario_returns:
        raise ValueError("לא הוגדרו תרחישי תשואה")

    # First-year saving uses the central scenario if present, else the first one.
    central_r = scenario_returns.get("central", next(iter(scenario_returns.values())))
    y1 = SimInput(balance, dep, min(12, months), central_r, salary_growth)
    c1, a1 = simulate(y1, current), simulate(y1, alternative)

    out = []
    for name, r in scenario_returns.items():
        inp = SimInput(balance, dep, months, r, salary_growth)
        c, a = simulate(inp, current), simulate(inp, alternative)
        out.append(ScenarioComparison(name, r, c.final_balance, a.final_balance,
                                      c.total_fees, a.total_fees,
                                      c.yearly_balances, a.yearly_balances))
    return Comparison(
        monthly_deposit=dep,
        months=months,
        first_year_fee_saving=c1.total_fees - a1.total_fees,
        first_year_deposit_fee_saving=c1.total_deposit_fees - a1.total_deposit_fees,
        first_year_accumulation_fee_saving=c1.total_accumulation_fees - a1.total_accumulation_fees,
        scenarios=out,
    )
