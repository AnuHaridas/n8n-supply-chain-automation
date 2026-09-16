from src.planning import (
    ComponentPlanningPeriodResult,
    evaluate_component_supply_plan,
)


def test_board_receipt_and_gross_requirement_create_shortage() -> None:
    results = evaluate_component_supply_plan(
        component_item="BOARD",
        periods=("W1", "W2"),
        opening_inventory=160,
        gross_requirements_by_period={"W1": 0, "W2": 200},
        scheduled_receipts_by_period={"W1": 0, "W2": 20},
        safety_stock_target_by_period={"W1": 0, "W2": 0},
    )

    assert results[1] == ComponentPlanningPeriodResult(
        component_item="BOARD",
        period="W2",
        opening_balance=160,
        gross_requirement=200,
        scheduled_receipt=20,
        closing_balance=-20,
        physical_shortage=20,
        safety_stock_target=0,
        buffer_gap=20,
    )


def test_battery_inventory_covers_gross_requirement() -> None:
    result = evaluate_component_supply_plan(
        component_item="BATTERY",
        periods=("W2",),
        opening_inventory=500,
        gross_requirements_by_period={"W2": 400},
        scheduled_receipts_by_period={"W2": 0},
        safety_stock_target_by_period={"W2": 0},
    )[0]

    assert result.closing_balance == 100
    assert result.physical_shortage == 0
    assert result.buffer_gap == 0


def test_w3_receipt_does_not_prevent_w2_shortage() -> None:
    results = evaluate_component_supply_plan(
        component_item="BOARD",
        periods=("W2", "W3"),
        opening_inventory=0,
        gross_requirements_by_period={"W2": 100, "W3": 0},
        scheduled_receipts_by_period={"W2": 0, "W3": 100},
        safety_stock_target_by_period={"W2": 0, "W3": 0},
    )

    assert results[0].closing_balance == -100
    assert results[0].physical_shortage == 100
    assert results[1].closing_balance == 0


def test_negative_w2_balance_carries_forward_into_w3() -> None:
    results = evaluate_component_supply_plan(
        component_item="BOARD",
        periods=("W2", "W3"),
        opening_inventory=50,
        gross_requirements_by_period={"W2": 100, "W3": 25},
        scheduled_receipts_by_period={"W2": 0, "W3": 0},
        safety_stock_target_by_period={"W2": 0, "W3": 0},
    )

    assert results[0].closing_balance == -50
    assert results[1].opening_balance == -50
    assert results[1].closing_balance == -75
    assert results[1].physical_shortage == 75


def test_additional_receipt_in_needed_period_eliminates_shortage() -> None:
    without_additional_receipt = evaluate_component_supply_plan(
        component_item="BOARD",
        periods=("W2",),
        opening_inventory=160,
        gross_requirements_by_period={"W2": 200},
        scheduled_receipts_by_period={"W2": 20},
        safety_stock_target_by_period={"W2": 0},
    )[0]
    with_additional_receipt = evaluate_component_supply_plan(
        component_item="BOARD",
        periods=("W2",),
        opening_inventory=160,
        gross_requirements_by_period={"W2": 200},
        scheduled_receipts_by_period={"W2": 40},
        safety_stock_target_by_period={"W2": 0},
    )[0]

    assert without_additional_receipt.physical_shortage == 20
    assert with_additional_receipt.closing_balance == 0
    assert with_additional_receipt.physical_shortage == 0
