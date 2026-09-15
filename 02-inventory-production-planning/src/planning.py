"""Deterministic finished-goods inventory roll-forward logic."""

from dataclasses import dataclass
from math import ceil
from typing import Hashable, Mapping, Sequence, TypeVar


Period = TypeVar("Period", bound=Hashable)


@dataclass(frozen=True)
class PlanningPeriodResult:
    """The explainable supply position for one planning period."""

    period: Hashable
    opening_balance: int | float
    demand: int | float
    in_transit: int | float
    existing_production_receipt: int | float
    closing_balance: int | float
    physical_shortage: int | float
    safety_stock_target: int | float
    buffer_gap: int | float


@dataclass(frozen=True)
class ProductionRequirementResult:
    """The explainable additional-production calculation for one period."""

    period: Hashable
    closing_balance_before_new_production: int | float
    safety_stock_target: int | float
    net_requirement: int | float
    moq: int | float
    production_multiple: int | float
    recommended_production: int | float


def evaluate_accepted_supply_plan(
    *,
    opening_inventory: int | float,
    periods: Sequence[Period],
    demand_by_period: Mapping[Period, int | float],
    in_transit_receipts_by_period: Mapping[Period, int | float],
    existing_production_receipts_by_period: Mapping[Period, int | float],
    safety_stock_target_by_period: Mapping[Period, int | float],
) -> list[PlanningPeriodResult]:
    """Evaluate the accepted supply plan in the supplied period order.

    Every period must be present in each input mapping. Negative closing balances
    are retained as backlog and become the next period's opening balance. This
    function evaluates accepted supply only; it does not propose production.
    """

    results: list[PlanningPeriodResult] = []
    current_opening_balance = opening_inventory

    for period in periods:
        demand = demand_by_period[period]
        in_transit = in_transit_receipts_by_period[period]
        existing_production_receipt = existing_production_receipts_by_period[period]
        safety_stock_target = safety_stock_target_by_period[period]

        closing_balance = (
            current_opening_balance
            + in_transit
            + existing_production_receipt
            - demand
        )
        physical_shortage = max(0, -closing_balance)
        buffer_gap = max(0, safety_stock_target - closing_balance)

        results.append(
            PlanningPeriodResult(
                period=period,
                opening_balance=current_opening_balance,
                demand=demand,
                in_transit=in_transit,
                existing_production_receipt=existing_production_receipt,
                closing_balance=closing_balance,
                physical_shortage=physical_shortage,
                safety_stock_target=safety_stock_target,
                buffer_gap=buffer_gap,
            )
        )
        current_opening_balance = closing_balance

    return results


def calculate_additional_production_requirement(
    planning_period_result: PlanningPeriodResult,
    *,
    safety_stock_target: int | float,
    moq: int | float,
    production_multiple: int | float,
) -> ProductionRequirementResult:
    """Calculate new production needed after evaluating accepted supply."""

    net_requirement = max(
        0,
        safety_stock_target - planning_period_result.closing_balance,
    )

    if net_requirement == 0:
        recommended_production = 0
    else:
        recommended_production = production_multiple * ceil(
            max(net_requirement, moq) / production_multiple
        )

    return ProductionRequirementResult(
        period=planning_period_result.period,
        closing_balance_before_new_production=planning_period_result.closing_balance,
        safety_stock_target=safety_stock_target,
        net_requirement=net_requirement,
        moq=moq,
        production_multiple=production_multiple,
        recommended_production=recommended_production,
    )
