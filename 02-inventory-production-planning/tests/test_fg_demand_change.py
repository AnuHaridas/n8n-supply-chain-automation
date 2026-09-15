import csv
import json
from pathlib import Path

from src.planning import (
    calculate_additional_production_requirement,
    evaluate_accepted_supply_plan,
)


FIXTURE_DIRECTORY = Path(__file__).parent / "fixtures" / "fg_demand_change"


def read_period_values(path: Path, value_column: str) -> dict[str, int]:
    with path.open(encoding="utf-8", newline="") as fixture_file:
        return {
            row["period"]: int(row[value_column])
            for row in csv.DictReader(fixture_file)
        }


def test_fg_demand_change_fixture_produces_expected_result() -> None:
    demand_by_period = read_period_values(FIXTURE_DIRECTORY / "demand.csv", "demand")

    with (FIXTURE_DIRECTORY / "inventory.csv").open(
        encoding="utf-8", newline=""
    ) as inventory_file:
        opening_inventory = int(next(csv.DictReader(inventory_file))["opening_inventory"])

    with (FIXTURE_DIRECTORY / "production_plan.csv").open(
        encoding="utf-8", newline=""
    ) as production_plan_file:
        production_plan = list(csv.DictReader(production_plan_file))

    with (FIXTURE_DIRECTORY / "policy.json").open(encoding="utf-8") as policy_file:
        policy = json.load(policy_file)

    with (FIXTURE_DIRECTORY / "expected.json").open(encoding="utf-8") as expected_file:
        expected = json.load(expected_file)

    periods = tuple(demand_by_period)
    in_transit_by_period = {
        row["period"]: int(row["in_transit"]) for row in production_plan
    }
    existing_production_by_period = {
        row["period"]: int(row["existing_production_receipt"])
        for row in production_plan
    }

    planning_results = evaluate_accepted_supply_plan(
        opening_inventory=opening_inventory,
        periods=periods,
        demand_by_period=demand_by_period,
        in_transit_receipts_by_period=in_transit_by_period,
        existing_production_receipts_by_period=existing_production_by_period,
        safety_stock_target_by_period=policy["safety_stock_target_by_period"],
    )
    result_by_period = {result.period: result for result in planning_results}
    target_period_result = result_by_period[expected["period"]]

    production_requirement = calculate_additional_production_requirement(
        target_period_result,
        safety_stock_target=policy["safety_stock_target_by_period"][expected["period"]],
        moq=policy["moq"],
        production_multiple=policy["production_multiple"],
    )

    actual = {
        "period": target_period_result.period,
        "closing_balance": target_period_result.closing_balance,
        "physical_shortage": target_period_result.physical_shortage,
        "buffer_gap": target_period_result.buffer_gap,
        "net_requirement": production_requirement.net_requirement,
        "recommended_production": production_requirement.recommended_production,
    }

    assert actual == expected, (
        "Finished-goods demand-change fixture result differs from expected.json: "
        f"actual={actual}, expected={expected}"
    )
