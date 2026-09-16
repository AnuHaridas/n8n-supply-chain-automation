"""Prepare tested planning-engine results for the Excel demo export."""

import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from src.planning import (
    BomComponent,
    ProductionOrder,
    calculate_additional_production_requirement,
    calculate_po_release_period,
    calculate_production_start_period,
    evaluate_accepted_supply_plan,
    evaluate_component_supply_plan,
    explode_one_level_bom,
)


PROJECT_DIRECTORY = Path(__file__).parents[1]
FIXTURE_DIRECTORY = PROJECT_DIRECTORY / "tests" / "fixtures" / "fg_demand_change"
ITEM = "CAM-A"
MANUFACTURING_LEAD_TIME_PERIODS = 2

# Demo inputs for the component supply position. Planning calculations remain in
# planning.py; these values only provide the component scenario to evaluate.
COMPONENT_OPENING_INVENTORY = {"BOARD": 160, "BATTERY": 500}
COMPONENT_SCHEDULED_RECEIPTS = {
    "BOARD": {"W1": 20, "W2": 0, "W3": 0, "W4": 0},
    "BATTERY": {"W1": 0, "W2": 0, "W3": 0, "W4": 0},
}
COMPONENT_PURCHASE_LEAD_TIME_PERIODS = {"BOARD": 2, "BATTERY": 2}


def _read_csv_rows(filename: str) -> list[dict[str, str]]:
    with (FIXTURE_DIRECTORY / filename).open(
        encoding="utf-8", newline=""
    ) as fixture_file:
        return list(csv.DictReader(fixture_file))


def build_demo_export_payload() -> dict[str, Any]:
    """Run the fixture through planning functions and return presentation rows."""

    demand_rows = _read_csv_rows("demand.csv")
    inventory_row = _read_csv_rows("inventory.csv")[0]
    production_plan_rows = _read_csv_rows("production_plan.csv")
    bom_rows = _read_csv_rows("bom.csv")

    with (FIXTURE_DIRECTORY / "policy.json").open(encoding="utf-8") as policy_file:
        policy = json.load(policy_file)

    periods = tuple(row["period"] for row in demand_rows)
    planning_calendar = ("W-1", "W0", *periods)
    demand_by_period = {row["period"]: int(row["demand"]) for row in demand_rows}
    in_transit_by_period = {
        row["period"]: int(row["in_transit"]) for row in production_plan_rows
    }
    existing_production_by_period = {
        row["period"]: int(row["existing_production_receipt"])
        for row in production_plan_rows
    }

    fg_results = evaluate_accepted_supply_plan(
        opening_inventory=int(inventory_row["opening_inventory"]),
        periods=periods,
        demand_by_period=demand_by_period,
        in_transit_receipts_by_period=in_transit_by_period,
        existing_production_receipts_by_period=existing_production_by_period,
        safety_stock_target_by_period=policy["safety_stock_target_by_period"],
    )

    production_requirements = {
        result.period: calculate_additional_production_requirement(
            result,
            safety_stock_target=policy["safety_stock_target_by_period"][result.period],
            moq=policy["moq"],
            production_multiple=policy["production_multiple"],
        )
        for result in fg_results
    }
    production_start_results = {
        period: calculate_production_start_period(
            ordered_calendar=planning_calendar,
            fg_available_period=period,
            manufacturing_lead_time_periods=MANUFACTURING_LEAD_TIME_PERIODS,
        )
        for period, requirement in production_requirements.items()
        if requirement.recommended_production > 0
    }

    fg_plan_rows = []
    for result in fg_results:
        requirement = production_requirements[result.period]
        start_result = production_start_results.get(result.period)
        if start_result and start_result.status != "OK":
            status = start_result.status
        elif requirement.recommended_production > 0:
            status = "PRODUCTION REQUIRED"
        else:
            status = "OK"

        fg_plan_rows.append(
            {
                "item": ITEM,
                "period": result.period,
                "demand": result.demand,
                "opening_inventory": result.opening_balance,
                "in_transit": result.in_transit,
                "existing_production_receipt": result.existing_production_receipt,
                "closing_balance_before_new_production": result.closing_balance,
                "physical_shortage": result.physical_shortage,
                "safety_stock_target": result.safety_stock_target,
                "net_production_requirement": requirement.net_requirement,
                "recommended_production": requirement.recommended_production,
                "production_start_period": (
                    start_result.offset_period if start_result else None
                ),
                "status": status,
            }
        )

    bom_components = tuple(
        BomComponent(
            parent_item=row["parent_item"],
            bom_revision=row["bom_revision"],
            component_item=row["component_item"],
            quantity_per=int(row["quantity_per"]),
        )
        for row in bom_rows
    )
    production_orders = []
    for period in periods:
        start_result = calculate_production_start_period(
            ordered_calendar=planning_calendar,
            fg_available_period=period,
            manufacturing_lead_time_periods=MANUFACTURING_LEAD_TIME_PERIODS,
        )
        existing_quantity = existing_production_by_period[period]
        if existing_quantity > 0 and start_result.offset_period is not None:
            production_orders.append(
                ProductionOrder(
                    production_order_id=f"ACCEPTED-{period}",
                    parent_item=ITEM,
                    production_quantity=existing_quantity,
                    production_start_period=start_result.offset_period,
                    bom_revision="R1",
                )
            )

        proposed_quantity = production_requirements[period].recommended_production
        if proposed_quantity > 0 and start_result.offset_period is not None:
            production_orders.append(
                ProductionOrder(
                    production_order_id=f"PROPOSAL-{period}",
                    parent_item=ITEM,
                    production_quantity=proposed_quantity,
                    production_start_period=start_result.offset_period,
                    bom_revision="R1",
                )
            )

    exploded_requirements = explode_one_level_bom(
        production_orders=tuple(production_orders),
        bom_components=bom_components,
    )
    requirements_by_component_and_period = defaultdict(list)
    for requirement in exploded_requirements:
        requirements_by_component_and_period[
            (requirement.component_item, requirement.production_start_period)
        ].append(requirement)

    component_items = tuple(dict.fromkeys(row["component_item"] for row in bom_rows))
    component_plan_rows = []
    past_due_component_releases = []
    for component_item in component_items:
        gross_requirements_by_period = {
            period: sum(
                requirement.gross_requirement
                for requirement in requirements_by_component_and_period[
                    (component_item, period)
                ]
            )
            for period in periods
        }
        component_results = evaluate_component_supply_plan(
            component_item=component_item,
            periods=periods,
            opening_inventory=COMPONENT_OPENING_INVENTORY[component_item],
            gross_requirements_by_period=gross_requirements_by_period,
            scheduled_receipts_by_period=COMPONENT_SCHEDULED_RECEIPTS[component_item],
            safety_stock_target_by_period={period: 0 for period in periods},
        )

        for result in component_results:
            detail = requirements_by_component_and_period[
                (component_item, result.period)
            ]
            release_result = None
            if result.gross_requirement > 0:
                release_result = calculate_po_release_period(
                    ordered_calendar=planning_calendar,
                    component_need_period=result.period,
                    purchase_lead_time_periods=(
                        COMPONENT_PURCHASE_LEAD_TIME_PERIODS[component_item]
                    ),
                )
            if release_result and release_result.status != "OK":
                status = release_result.status
                past_due_component_releases.append(
                    {"component": component_item, "period": result.period}
                )
            elif result.physical_shortage > 0:
                status = "SHORTAGE"
            else:
                status = "OK"

            component_plan_rows.append(
                {
                    "component": component_item,
                    "parent_fg": ", ".join(
                        dict.fromkeys(requirement.parent_item for requirement in detail)
                    ),
                    "production_order_reference": ", ".join(
                        requirement.production_order_id for requirement in detail
                    ),
                    "component_need_period": result.period,
                    "gross_requirement": result.gross_requirement,
                    "opening_inventory": result.opening_balance,
                    "scheduled_po_receipt": result.scheduled_receipt,
                    "closing_balance": result.closing_balance,
                    "physical_shortage": result.physical_shortage,
                    "purchase_lead_time": (
                        COMPONENT_PURCHASE_LEAD_TIME_PERIODS[component_item]
                    ),
                    "required_po_release_period": (
                        release_result.offset_period if release_result else None
                    ),
                    "status": status,
                }
            )

    return {
        "fg_plan": fg_plan_rows,
        "component_plan": component_plan_rows,
        "summary": {
            "fg_additional_production_required": [
                {
                    "item": row["item"],
                    "period": row["period"],
                    "quantity": row["recommended_production"],
                }
                for row in fg_plan_rows
                if row["recommended_production"] > 0
            ],
            "component_shortages": [
                {
                    "component": row["component"],
                    "period": row["component_need_period"],
                    "quantity": row["physical_shortage"],
                }
                for row in component_plan_rows
                if row["physical_shortage"] > 0
            ],
            "production_start_periods": [
                {
                    "item": ITEM,
                    "available_period": period,
                    "start_period": result.offset_period,
                    "status": result.status,
                }
                for period, result in production_start_results.items()
            ],
            "past_due_component_releases": past_due_component_releases,
        },
    }


if __name__ == "__main__":
    print(json.dumps(build_demo_export_payload()))
