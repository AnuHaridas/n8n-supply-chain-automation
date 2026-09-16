import csv
import json
from pathlib import Path

from src.demo_export_data import build_demo_export_payload
from src.planning import (
    CommunicatedPlanRecord,
    calculate_additional_production_requirement,
    classify_communicated_periods,
    compare_demand_snapshots,
    evaluate_accepted_supply_plan,
)


FIXTURE_DIRECTORY = Path(__file__).parent / "fixtures" / "fg_demand_change"


def _read_csv(filename: str) -> list[dict[str, str]]:
    with (FIXTURE_DIRECTORY / filename).open(
        encoding="utf-8", newline=""
    ) as fixture_file:
        return list(csv.DictReader(fixture_file))


def _fixture_control_results():
    latest_rows = _read_csv("demand.csv")
    previous_rows = _read_csv("last_accepted_demand.csv")
    production_rows = _read_csv("production_plan.csv")
    communicated_rows = _read_csv("last_communicated_cm_plan.csv")
    inventory_row = _read_csv("inventory.csv")[0]

    with (FIXTURE_DIRECTORY / "policy.json").open(encoding="utf-8") as policy_file:
        policy = json.load(policy_file)

    periods = tuple(row["period"] for row in latest_rows)
    accepted_supply = evaluate_accepted_supply_plan(
        opening_inventory=int(inventory_row["opening_inventory"]),
        periods=periods,
        demand_by_period={
            row["period"]: int(row["demand"]) for row in latest_rows
        },
        in_transit_receipts_by_period={
            row["period"]: int(row["in_transit"]) for row in production_rows
        },
        existing_production_receipts_by_period={
            row["period"]: int(row["existing_production_receipt"])
            for row in production_rows
        },
        safety_stock_target_by_period=policy["safety_stock_target_by_period"],
    )
    recommendations = {
        ("CAM-A", result.period): calculate_additional_production_requirement(
            result,
            safety_stock_target=policy["safety_stock_target_by_period"][
                result.period
            ],
            moq=policy["moq"],
            production_multiple=policy["production_multiple"],
        ).recommended_production
        for result in accepted_supply
    }
    demand_changes = compare_demand_snapshots(
        last_accepted_demand={
            (row["item"], row["period"]): int(row["demand"])
            for row in previous_rows
        },
        latest_demand={
            (row["item"], row["period"]): int(row["demand"])
            for row in latest_rows
        },
    )
    results = classify_communicated_periods(
        demand_changes=demand_changes,
        new_production_recommendations=recommendations,
        communicated_plan=tuple(
            CommunicatedPlanRecord(
                item=row["item"],
                period=row["period"],
                communicated_quantity=int(row["communicated_qty"]),
                cm=row["cm"],
                communicated_date=row["communicated_date"],
            )
            for row in communicated_rows
        ),
    )
    return {(result.item, result.period): result for result in results}


def test_demand_change_detection_reports_types_and_missing_combinations() -> None:
    results = compare_demand_snapshots(
        last_accepted_demand={
            ("CAM-A", "September"): 40,
            ("CAM-A", "October"): 50,
            ("CAM-B", "September"): 25,
            ("CAM-C", "September"): 15,
        },
        latest_demand={
            ("CAM-A", "September"): 40,
            ("CAM-A", "October"): 60,
            ("CAM-B", "September"): 20,
            ("CAM-D", "September"): 10,
        },
    )
    by_key = {(result.item, result.period): result for result in results}

    assert by_key[("CAM-A", "September")].change_type == "UNCHANGED"
    assert by_key[("CAM-A", "October")].change_type == "INCREASE"
    assert by_key[("CAM-A", "October")].demand_delta == 10
    assert by_key[("CAM-B", "September")].change_type == "DECREASE"
    assert by_key[("CAM-C", "September")].presence_status == (
        "MISSING_LATEST_ITEM_PERIOD"
    )
    assert by_key[("CAM-C", "September")].demand_delta is None
    assert by_key[("CAM-D", "September")].presence_status == "NEW_ITEM_PERIOD"
    assert by_key[("CAM-D", "September")].previous_demand is None


def test_unchanged_communicated_period_is_unchanged_frozen() -> None:
    september = _fixture_control_results()[("CAM-A", "September")]

    assert september.planning_status == "UNCHANGED_FROZEN"
    assert september.review_comment_required is False
    assert september.protected_production_quantity == 0


def test_demand_change_in_communicated_period_is_explicitly_flagged() -> None:
    demand_change = compare_demand_snapshots(
        last_accepted_demand={("CAM-A", "October"): 50},
        latest_demand={("CAM-A", "October"): 60},
    )

    result = classify_communicated_periods(
        demand_changes=demand_change,
        new_production_recommendations={("CAM-A", "October"): 100},
        communicated_plan=(
            CommunicatedPlanRecord(
                item="CAM-A",
                period="October",
                communicated_quantity=100,
                cm="CM-China",
                communicated_date="2026-08-08",
            ),
        ),
    )[0]

    assert result.planning_status == "FROZEN_PERIOD_DEMAND_CHANGE"
    assert result.demand_delta == 10
    assert result.frozen_period_demand_change is True
    assert result.review_comment_required is True


def test_frozen_production_change_exposes_old_new_and_delta() -> None:
    october = _fixture_control_results()[("CAM-A", "October")]

    assert october.planning_status == "FROZEN_PERIOD_PRODUCTION_CHANGE"
    assert october.previously_communicated_production == 100
    assert october.newly_calculated_production_recommendation == 0
    assert october.production_delta == -100
    assert october.demand_delta == 10
    assert october.review_comment_required is True


def test_new_open_period_receives_normal_production_recommendation() -> None:
    november = _fixture_control_results()[("CAM-A", "November")]

    assert november.planning_status == "NEW_OPEN_PERIOD"
    assert november.previously_communicated_production is None
    assert november.newly_calculated_production_recommendation == 100
    assert november.protected_production_quantity == 100
    assert november.review_comment_required is False


def test_export_keeps_communicated_quantity_separate_from_recalculation() -> None:
    payload = build_demo_export_payload()
    october = next(
        row
        for row in payload["fg_plan"]
        if row["item"] == "CAM-A" and row["period"] == "October"
    )

    assert october["previously_communicated_cm_production"] == 100
    assert october["newly_calculated_production_recommendation"] == 0
    assert october["production_delta"] == -100
    assert october["protected_production_quantity"] == 100
    assert october["planning_status"] == "FROZEN_PERIOD_PRODUCTION_CHANGE"
    assert october["planner_comment_reason_required"] is True
