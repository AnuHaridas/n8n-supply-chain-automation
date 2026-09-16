"""Prepare tested planning-engine results for the Excel demo export."""

import csv
import json
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Hashable, Mapping, Sequence

from src.planning import (
    BomComponent,
    CommunicatedPlanRecord,
    PlanningControlResult,
    ProductionOrder,
    calculate_additional_production_requirement,
    calculate_po_release_period,
    calculate_production_start_period,
    classify_communicated_periods,
    compare_demand_snapshots,
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
    "BOARD": {"September": 20, "October": 0, "November": 0, "December": 0},
    "BATTERY": {"September": 0, "October": 0, "November": 0, "December": 0},
}
COMPONENT_PURCHASE_LEAD_TIME_PERIODS = {"BOARD": 2, "BATTERY": 2}


def _read_csv_rows(filename: str) -> list[dict[str, str]]:
    with (FIXTURE_DIRECTORY / filename).open(
        encoding="utf-8", newline=""
    ) as fixture_file:
        return list(csv.DictReader(fixture_file))


def _period_display_label(period: Hashable) -> str:
    """Return a short display label for a named month, otherwise preserve it."""

    period_text = str(period)
    try:
        return datetime.strptime(period_text, "%B").strftime("%b")
    except ValueError:
        return period_text


def build_cm_plan_views(
    *,
    planning_controls: Sequence[PlanningControlResult],
    ordered_periods: Sequence[Hashable],
    planner_comments: Mapping[tuple[str, Hashable], str],
) -> list[dict[str, Any]]:
    """Build simple, presentation-only CM plans from frozen/open controls."""

    periods = tuple(ordered_periods)
    if len(set(periods)) != len(periods):
        raise ValueError("Ordered periods contain duplicates")

    display_label_by_period = {
        period: _period_display_label(period) for period in periods
    }
    if len(set(display_label_by_period.values())) != len(periods):
        raise ValueError("Period display labels are not unique")

    controls_by_item: dict[str, dict[Hashable, PlanningControlResult]] = {}
    item_order: list[str] = []
    for control in planning_controls:
        if control.item not in controls_by_item:
            controls_by_item[control.item] = {}
            item_order.append(control.item)
        if control.period in controls_by_item[control.item]:
            raise ValueError(
                f"Duplicate planning control for item {control.item!r}, "
                f"period {control.period!r}"
            )
        controls_by_item[control.item][control.period] = control

    cm_by_item: dict[str, str] = {}
    for item in item_order:
        assigned_cms = tuple(
            dict.fromkeys(
                control.cm
                for control in controls_by_item[item].values()
                if control.cm
            )
        )
        if not assigned_cms:
            raise ValueError(f"No CM assignment found for item {item!r}")
        if len(assigned_cms) > 1:
            raise ValueError(
                f"Multiple CM assignments found for item {item!r}: "
                f"{assigned_cms!r}"
            )
        cm_by_item[item] = assigned_cms[0]

    cm_order = tuple(dict.fromkeys(cm_by_item[item] for item in item_order))
    cm_plans: list[dict[str, Any]] = []
    for cm in cm_order:
        cm_items = tuple(item for item in item_order if cm_by_item[item] == cm)
        frozen_periods = tuple(
            period
            for period in periods
            if any(
                controls_by_item[item][period].previously_communicated_production
                is not None
                for item in cm_items
            )
        )
        columns = [
            "SKU",
            *(display_label_by_period[period] for period in periods),
            *(
                f"{display_label_by_period[period]} Delta"
                for period in frozen_periods
            ),
            "Comment",
        ]
        output_rows = []
        missing_comment_periods = []

        for item in cm_items:
            missing_periods = [
                period
                for period in periods
                if period not in controls_by_item[item]
            ]
            if missing_periods:
                raise ValueError(
                    f"Missing planning controls for item {item!r}: "
                    f"{missing_periods!r}"
                )

            values: dict[str, Any] = {"SKU": item}
            for period in periods:
                values[display_label_by_period[period]] = controls_by_item[item][
                    period
                ].newly_calculated_production_recommendation

            changed_frozen_periods = []
            comment_parts = []
            for period in frozen_periods:
                control = controls_by_item[item][period]
                delta = control.production_delta
                if delta is None:
                    raise ValueError(
                        f"Frozen period {period!r} for item {item!r} has no delta"
                    )
                values[f"{display_label_by_period[period]} Delta"] = delta
                if delta != 0:
                    changed_frozen_periods.append(period)
                    comment = planner_comments.get((item, period), "").strip()
                    if comment:
                        comment_parts.append(
                            f"{display_label_by_period[period]}: {comment}"
                        )
                    else:
                        missing_comment_periods.append(
                            {"item": item, "period": period}
                        )

            values["Comment"] = "; ".join(comment_parts)
            output_rows.append(
                {
                    "values": values,
                    "changed_frozen_periods": changed_frozen_periods,
                }
            )

        safe_cm_name = re.sub(r"[^A-Za-z0-9]+", "_", cm).strip("_")
        cm_plans.append(
            {
                "cm": cm,
                "filename": f"{safe_cm_name}_Production_Plan.xlsx",
                "periods": list(periods),
                "period_display_labels": display_label_by_period,
                "frozen_periods": list(frozen_periods),
                "columns": columns,
                "rows": output_rows,
                "missing_comment_periods": missing_comment_periods,
                "ready_for_communication": not missing_comment_periods,
            }
        )

    return cm_plans


def build_demo_export_payload(
    *,
    planner_comments: Mapping[tuple[str, Hashable], str] | None = None,
) -> dict[str, Any]:
    """Run the fixture through planning functions and return presentation rows."""

    demand_rows = _read_csv_rows("demand.csv")
    last_accepted_demand_rows = _read_csv_rows("last_accepted_demand.csv")
    inventory_row = _read_csv_rows("inventory.csv")[0]
    production_plan_rows = _read_csv_rows("production_plan.csv")
    bom_rows = _read_csv_rows("bom.csv")
    communicated_plan_rows = _read_csv_rows("last_communicated_cm_plan.csv")
    if planner_comments is None:
        planner_comments = {
            (row["item"], row["period"]): row["comment"]
            for row in _read_csv_rows("planner_comments.csv")
        }

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
    demand_changes = compare_demand_snapshots(
        last_accepted_demand={
            (row["item"], row["period"]): int(row["demand"])
            for row in last_accepted_demand_rows
        },
        latest_demand={
            (row["item"], row["period"]): int(row["demand"])
            for row in demand_rows
        },
    )
    planning_controls = classify_communicated_periods(
        demand_changes=demand_changes,
        new_production_recommendations={
            (ITEM, period): requirement.recommended_production
            for period, requirement in production_requirements.items()
        },
        communicated_plan=tuple(
            CommunicatedPlanRecord(
                item=row["item"],
                period=row["period"],
                communicated_quantity=int(row["communicated_qty"]),
                cm=row["cm"],
                communicated_date=row["communicated_date"],
            )
            for row in communicated_plan_rows
        ),
    )
    planning_control_by_period = {
        result.period: result
        for result in planning_controls
        if result.item == ITEM
    }

    fg_plan_rows = []
    for result in fg_results:
        requirement = production_requirements[result.period]
        planning_control = planning_control_by_period[result.period]
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
                "previous_demand": planning_control.previous_demand,
                "latest_demand": planning_control.latest_demand,
                "demand_delta": planning_control.demand_delta,
                "demand_change_type": planning_control.demand_change_type,
                "opening_inventory": result.opening_balance,
                "in_transit": result.in_transit,
                "existing_production_receipt": result.existing_production_receipt,
                "inbound_eta": (
                    result.in_transit + result.existing_production_receipt
                ),
                "closing_balance_before_new_production": result.closing_balance,
                "physical_shortage": result.physical_shortage,
                "safety_stock_target": result.safety_stock_target,
                "net_production_requirement": requirement.net_requirement,
                "recommended_production": requirement.recommended_production,
                "previously_communicated_cm_production": (
                    planning_control.previously_communicated_production
                ),
                "newly_calculated_production_recommendation": (
                    planning_control.newly_calculated_production_recommendation
                ),
                "production_delta": planning_control.production_delta,
                "protected_production_quantity": (
                    planning_control.protected_production_quantity
                ),
                "production_start_period": (
                    start_result.offset_period if start_result else None
                ),
                "status": status,
                "planning_status": planning_control.planning_status,
                "planner_comment_reason_required": (
                    planning_control.review_comment_required
                ),
            }
        )

    cm_plans = build_cm_plan_views(
        planning_controls=planning_controls,
        ordered_periods=periods,
        planner_comments=planner_comments,
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
        "cm_plans": cm_plans,
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
