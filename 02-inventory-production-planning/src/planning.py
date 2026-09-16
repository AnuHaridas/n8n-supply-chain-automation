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


@dataclass(frozen=True)
class ProductionOrder:
    """A finished-good production quantity released for a start period."""

    production_order_id: str
    parent_item: str
    production_quantity: int | float
    production_start_period: Hashable
    bom_revision: str


@dataclass(frozen=True)
class BomComponent:
    """One component line in a one-level finished-good BOM revision."""

    parent_item: str
    bom_revision: str
    component_item: str
    quantity_per: int | float


@dataclass(frozen=True)
class ComponentGrossRequirement:
    """An exploded component requirement attributable to one production order."""

    production_order_id: str
    parent_item: str
    component_item: str
    production_start_period: Hashable
    bom_revision: str
    quantity_per: int | float
    gross_requirement: int | float


@dataclass(frozen=True)
class ComponentPlanningPeriodResult:
    """The explainable component supply position for one planning period."""

    component_item: str
    period: Hashable
    opening_balance: int | float
    gross_requirement: int | float
    scheduled_receipt: int | float
    closing_balance: int | float
    physical_shortage: int | float
    safety_stock_target: int | float
    buffer_gap: int | float


@dataclass(frozen=True)
class PeriodOffsetResult:
    """The outcome of offsetting a required period by a whole-period lead time."""

    target_period: Hashable
    lead_time_periods: int
    offset_period: Hashable | None
    status: str


@dataclass(frozen=True)
class DemandChangeResult:
    """The comparison of two demand snapshots for one item and period."""

    item: str
    period: Hashable
    previous_demand: int | float | None
    latest_demand: int | float | None
    demand_delta: int | float | None
    change_type: str
    presence_status: str


@dataclass(frozen=True)
class CommunicatedPlanRecord:
    """A production quantity previously communicated to a contract manufacturer."""

    item: str
    period: Hashable
    communicated_quantity: int | float
    cm: str
    communicated_date: str


@dataclass(frozen=True)
class PlanningControlResult:
    """The frozen/open planning decision for one item and period."""

    item: str
    period: Hashable
    previous_demand: int | float | None
    latest_demand: int | float | None
    demand_delta: int | float | None
    demand_change_type: str
    frozen_period_demand_change: bool
    previously_communicated_production: int | float | None
    newly_calculated_production_recommendation: int | float
    production_delta: int | float | None
    protected_production_quantity: int | float
    planning_status: str
    review_comment_required: bool
    cm: str | None
    communicated_date: str | None


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


def explode_one_level_bom(
    production_orders: Sequence[ProductionOrder],
    bom_components: Sequence[BomComponent],
) -> list[ComponentGrossRequirement]:
    """Calculate time-phased gross component demand from production orders.

    Results retain production-order detail so consumers can aggregate by period
    and component without losing traceability. A production order must have at
    least one BOM line matching both its parent item and BOM revision.
    """

    bom_by_parent_and_revision: dict[tuple[str, str], list[BomComponent]] = {}
    for component in bom_components:
        key = (component.parent_item, component.bom_revision)
        bom_by_parent_and_revision.setdefault(key, []).append(component)

    requirements: list[ComponentGrossRequirement] = []
    for order in production_orders:
        key = (order.parent_item, order.bom_revision)
        applicable_components = bom_by_parent_and_revision.get(key)
        if not applicable_components:
            raise ValueError(
                f"No BOM found for production order {order.production_order_id!r} "
                f"(parent_item={order.parent_item!r}, "
                f"bom_revision={order.bom_revision!r})"
            )

        for component in applicable_components:
            requirements.append(
                ComponentGrossRequirement(
                    production_order_id=order.production_order_id,
                    parent_item=order.parent_item,
                    component_item=component.component_item,
                    production_start_period=order.production_start_period,
                    bom_revision=order.bom_revision,
                    quantity_per=component.quantity_per,
                    gross_requirement=(
                        order.production_quantity * component.quantity_per
                    ),
                )
            )

    return requirements


def evaluate_component_supply_plan(
    *,
    component_item: str,
    periods: Sequence[Period],
    opening_inventory: int | float,
    gross_requirements_by_period: Mapping[Period, int | float],
    scheduled_receipts_by_period: Mapping[Period, int | float],
    safety_stock_target_by_period: Mapping[Period, int | float],
) -> list[ComponentPlanningPeriodResult]:
    """Evaluate time-phased gross-to-net supply for one component.

    Every period must be present in each input mapping. Callers that do not use
    component safety stock must explicitly provide a zero target for each period.
    Negative closing balances remain backlog in subsequent periods.
    """

    results: list[ComponentPlanningPeriodResult] = []
    current_opening_balance = opening_inventory

    for period in periods:
        gross_requirement = gross_requirements_by_period[period]
        scheduled_receipt = scheduled_receipts_by_period[period]
        safety_stock_target = safety_stock_target_by_period[period]

        closing_balance = (
            current_opening_balance + scheduled_receipt - gross_requirement
        )
        physical_shortage = max(0, -closing_balance)
        buffer_gap = max(0, safety_stock_target - closing_balance)

        results.append(
            ComponentPlanningPeriodResult(
                component_item=component_item,
                period=period,
                opening_balance=current_opening_balance,
                gross_requirement=gross_requirement,
                scheduled_receipt=scheduled_receipt,
                closing_balance=closing_balance,
                physical_shortage=physical_shortage,
                safety_stock_target=safety_stock_target,
                buffer_gap=buffer_gap,
            )
        )
        current_opening_balance = closing_balance

    return results


def _offset_period(
    *,
    ordered_calendar: Sequence[Period],
    target_period: Period,
    lead_time_periods: int,
) -> PeriodOffsetResult:
    if (
        isinstance(lead_time_periods, bool)
        or not isinstance(lead_time_periods, int)
        or lead_time_periods <= 0
    ):
        raise ValueError("Lead time must be a positive whole number of periods")

    calendar = tuple(ordered_calendar)
    if len(set(calendar)) != len(calendar):
        raise ValueError("Ordered planning calendar contains duplicate periods")

    try:
        target_index = calendar.index(target_period)
    except ValueError as error:
        raise ValueError(
            f"Target period {target_period!r} is not in the ordered planning calendar"
        ) from error

    offset_index = target_index - lead_time_periods
    if offset_index < 0:
        return PeriodOffsetResult(
            target_period=target_period,
            lead_time_periods=lead_time_periods,
            offset_period=None,
            status="PAST_DUE_RELEASE",
        )

    return PeriodOffsetResult(
        target_period=target_period,
        lead_time_periods=lead_time_periods,
        offset_period=calendar[offset_index],
        status="OK",
    )


def calculate_production_start_period(
    *,
    ordered_calendar: Sequence[Period],
    fg_available_period: Period,
    manufacturing_lead_time_periods: int,
) -> PeriodOffsetResult:
    """Offset an FG available period to its production start period."""

    return _offset_period(
        ordered_calendar=ordered_calendar,
        target_period=fg_available_period,
        lead_time_periods=manufacturing_lead_time_periods,
    )


def calculate_po_release_period(
    *,
    ordered_calendar: Sequence[Period],
    component_need_period: Period,
    purchase_lead_time_periods: int,
) -> PeriodOffsetResult:
    """Offset a component need period to its required PO release period."""

    return _offset_period(
        ordered_calendar=ordered_calendar,
        target_period=component_need_period,
        lead_time_periods=purchase_lead_time_periods,
    )


def compare_demand_snapshots(
    *,
    last_accepted_demand: Mapping[tuple[str, Period], int | float],
    latest_demand: Mapping[tuple[str, Period], int | float],
) -> list[DemandChangeResult]:
    """Compare demand snapshots without treating absent combinations as zero.

    Rows follow the insertion order of the accepted snapshot, followed by any
    item-period combinations that exist only in the latest snapshot.
    """

    keys = tuple(dict.fromkeys((*last_accepted_demand, *latest_demand)))
    results: list[DemandChangeResult] = []

    for item, period in keys:
        previous_value = last_accepted_demand.get((item, period))
        latest_value = latest_demand.get((item, period))

        if (item, period) not in last_accepted_demand:
            demand_delta = None
            change_type = "NOT_COMPARABLE"
            presence_status = "NEW_ITEM_PERIOD"
        elif (item, period) not in latest_demand:
            demand_delta = None
            change_type = "NOT_COMPARABLE"
            presence_status = "MISSING_LATEST_ITEM_PERIOD"
        else:
            demand_delta = latest_value - previous_value
            if demand_delta > 0:
                change_type = "INCREASE"
            elif demand_delta < 0:
                change_type = "DECREASE"
            else:
                change_type = "UNCHANGED"
            presence_status = "PRESENT_IN_BOTH"

        results.append(
            DemandChangeResult(
                item=item,
                period=period,
                previous_demand=previous_value,
                latest_demand=latest_value,
                demand_delta=demand_delta,
                change_type=change_type,
                presence_status=presence_status,
            )
        )

    return results


def classify_communicated_periods(
    *,
    demand_changes: Sequence[DemandChangeResult],
    new_production_recommendations: Mapping[tuple[str, Period], int | float],
    communicated_plan: Sequence[CommunicatedPlanRecord],
) -> list[PlanningControlResult]:
    """Classify recalculated production without overwriting communicated periods."""

    communicated_by_key: dict[tuple[str, Hashable], CommunicatedPlanRecord] = {}
    for record in communicated_plan:
        key = (record.item, record.period)
        if key in communicated_by_key:
            raise ValueError(
                f"Duplicate communicated plan for item {record.item!r}, "
                f"period {record.period!r}"
            )
        communicated_by_key[key] = record

    demand_change_by_key = {
        (change.item, change.period): change for change in demand_changes
    }
    keys = tuple(
        dict.fromkeys(
            (
                *demand_change_by_key,
                *new_production_recommendations,
                *communicated_by_key,
            )
        )
    )
    results: list[PlanningControlResult] = []

    for item, period in keys:
        key = (item, period)
        if key not in new_production_recommendations:
            raise ValueError(
                f"Missing new production recommendation for item {item!r}, "
                f"period {period!r}"
            )

        change = demand_change_by_key.get(key)
        communicated = communicated_by_key.get(key)
        new_recommendation = new_production_recommendations[key]
        demand_changed = change is None or change.change_type != "UNCHANGED"

        if communicated is None:
            planning_status = "NEW_OPEN_PERIOD"
            production_delta = None
            protected_quantity = new_recommendation
            review_comment_required = False
        else:
            production_delta = (
                new_recommendation - communicated.communicated_quantity
            )
            protected_quantity = communicated.communicated_quantity
            review_comment_required = production_delta != 0
            if production_delta != 0:
                planning_status = "FROZEN_PERIOD_PRODUCTION_CHANGE"
            elif demand_changed:
                planning_status = "FROZEN_PERIOD_DEMAND_CHANGE"
            else:
                planning_status = "UNCHANGED_FROZEN"

        results.append(
            PlanningControlResult(
                item=item,
                period=period,
                previous_demand=(change.previous_demand if change else None),
                latest_demand=(change.latest_demand if change else None),
                demand_delta=(change.demand_delta if change else None),
                demand_change_type=(
                    change.change_type if change else "NOT_COMPARABLE"
                ),
                frozen_period_demand_change=(
                    communicated is not None and demand_changed
                ),
                previously_communicated_production=(
                    communicated.communicated_quantity if communicated else None
                ),
                newly_calculated_production_recommendation=new_recommendation,
                production_delta=production_delta,
                protected_production_quantity=protected_quantity,
                planning_status=planning_status,
                review_comment_required=review_comment_required,
                cm=(communicated.cm if communicated else None),
                communicated_date=(
                    communicated.communicated_date if communicated else None
                ),
            )
        )

    return results
