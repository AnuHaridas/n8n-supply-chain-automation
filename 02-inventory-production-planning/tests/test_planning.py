from src.planning import (
    PlanningPeriodResult,
    ProductionRequirementResult,
    calculate_additional_production_requirement,
    evaluate_accepted_supply_plan,
)


def make_period_result(
    closing_balance: int | float,
    safety_stock_target: int | float,
) -> PlanningPeriodResult:
    return PlanningPeriodResult(
        period="period-a",
        opening_balance=0,
        demand=0,
        in_transit=0,
        existing_production_receipt=0,
        closing_balance=closing_balance,
        physical_shortage=max(0, -closing_balance),
        safety_stock_target=safety_stock_target,
        buffer_gap=max(0, safety_stock_target - closing_balance),
    )


def test_existing_supply_covers_demand() -> None:
    results = evaluate_accepted_supply_plan(
        opening_inventory=100,
        periods=("period-a", "period-b"),
        demand_by_period={"period-a": 40, "period-b": 70},
        in_transit_receipts_by_period={"period-a": 20, "period-b": 0},
        existing_production_receipts_by_period={"period-a": 0, "period-b": 30},
        safety_stock_target_by_period={"period-a": 50, "period-b": 35},
    )

    assert results == [
        PlanningPeriodResult(
            period="period-a",
            opening_balance=100,
            demand=40,
            in_transit=20,
            existing_production_receipt=0,
            closing_balance=80,
            physical_shortage=0,
            safety_stock_target=50,
            buffer_gap=0,
        ),
        PlanningPeriodResult(
            period="period-b",
            opening_balance=80,
            demand=70,
            in_transit=0,
            existing_production_receipt=30,
            closing_balance=40,
            physical_shortage=0,
            safety_stock_target=35,
            buffer_gap=0,
        ),
    ]


def test_shortage_carries_forward_as_backlog() -> None:
    results = evaluate_accepted_supply_plan(
        opening_inventory=25,
        periods=(1, 2),
        demand_by_period={1: 40, 2: 10},
        in_transit_receipts_by_period={1: 0, 2: 0},
        existing_production_receipts_by_period={1: 0, 2: 0},
        safety_stock_target_by_period={1: 5, 2: 5},
    )

    assert results[0].closing_balance == -15
    assert results[0].physical_shortage == 15
    assert results[0].buffer_gap == 20
    assert results[1].opening_balance == -15
    assert results[1].closing_balance == -25
    assert results[1].physical_shortage == 25
    assert results[1].buffer_gap == 30


def test_later_receipt_does_not_cover_shortage_before_arrival() -> None:
    results = evaluate_accepted_supply_plan(
        opening_inventory=0,
        periods=("first", "later"),
        demand_by_period={"first": 30, "later": 5},
        in_transit_receipts_by_period={"first": 0, "later": 50},
        existing_production_receipts_by_period={"first": 0, "later": 0},
        safety_stock_target_by_period={"first": 0, "later": 10},
    )

    assert results[0].closing_balance == -30
    assert results[0].physical_shortage == 30
    assert results[1].opening_balance == -30
    assert results[1].closing_balance == 15
    assert results[1].physical_shortage == 0
    assert results[1].buffer_gap == 0


def test_no_additional_production_required() -> None:
    result = calculate_additional_production_requirement(
        make_period_result(closing_balance=120, safety_stock_target=100),
        safety_stock_target=100,
        moq=500,
        production_multiple=500,
    )

    assert result == ProductionRequirementResult(
        period="period-a",
        closing_balance_before_new_production=120,
        safety_stock_target=100,
        net_requirement=0,
        moq=500,
        production_multiple=500,
        recommended_production=0,
    )


def test_physical_shortage_requires_production() -> None:
    result = calculate_additional_production_requirement(
        make_period_result(closing_balance=-200, safety_stock_target=100),
        safety_stock_target=100,
        moq=100,
        production_multiple=100,
    )

    assert result.net_requirement == 300
    assert result.recommended_production == 300


def test_safety_stock_only_breach_requires_production() -> None:
    period_result = make_period_result(closing_balance=50, safety_stock_target=100)

    result = calculate_additional_production_requirement(
        period_result,
        safety_stock_target=100,
        moq=1,
        production_multiple=1,
    )

    assert period_result.physical_shortage == 0
    assert result.net_requirement == 50
    assert result.recommended_production == 50


def test_requirement_is_rounded_up_for_moq_and_production_multiple() -> None:
    result = calculate_additional_production_requirement(
        make_period_result(closing_balance=0, safety_stock_target=620),
        safety_stock_target=620,
        moq=700,
        production_multiple=500,
    )

    assert result.net_requirement == 620
    assert result.recommended_production == 1000


def test_zero_requirement_remains_zero_when_moq_is_positive() -> None:
    result = calculate_additional_production_requirement(
        make_period_result(closing_balance=100, safety_stock_target=100),
        safety_stock_target=100,
        moq=500,
        production_multiple=500,
    )

    assert result.net_requirement == 0
    assert result.recommended_production == 0
