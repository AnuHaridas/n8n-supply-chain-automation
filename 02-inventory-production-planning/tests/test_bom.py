from collections import defaultdict

import pytest

from src.planning import (
    BomComponent,
    ComponentGrossRequirement,
    ProductionOrder,
    explode_one_level_bom,
)


CAM_A_BOM = (
    BomComponent(
        parent_item="CAM-A",
        bom_revision="R1",
        component_item="BOARD",
        quantity_per=1,
    ),
    BomComponent(
        parent_item="CAM-A",
        bom_revision="R1",
        component_item="BATTERY",
        quantity_per=2,
    ),
)


def test_one_level_bom_explosion_calculates_component_requirements() -> None:
    requirements = explode_one_level_bom(
        production_orders=(
            ProductionOrder(
                production_order_id="PO-100",
                parent_item="CAM-A",
                production_quantity=100,
                production_start_period="W1",
                bom_revision="R1",
            ),
        ),
        bom_components=CAM_A_BOM,
    )

    assert requirements == [
        ComponentGrossRequirement(
            production_order_id="PO-100",
            parent_item="CAM-A",
            component_item="BOARD",
            production_start_period="W1",
            bom_revision="R1",
            quantity_per=1,
            gross_requirement=100,
        ),
        ComponentGrossRequirement(
            production_order_id="PO-100",
            parent_item="CAM-A",
            component_item="BATTERY",
            production_start_period="W1",
            bom_revision="R1",
            quantity_per=2,
            gross_requirement=200,
        ),
    ]


def test_existing_and_proposed_orders_aggregate_in_the_same_period() -> None:
    requirements = explode_one_level_bom(
        production_orders=(
            ProductionOrder("PO-EXISTING", "CAM-A", 100, "W1", "R1"),
            ProductionOrder("PO-PROPOSED", "CAM-A", 100, "W1", "R1"),
        ),
        bom_components=CAM_A_BOM,
    )

    totals_by_component: dict[str, int | float] = defaultdict(int)
    for requirement in requirements:
        totals_by_component[requirement.component_item] += (
            requirement.gross_requirement
        )

    assert dict(totals_by_component) == {"BOARD": 200, "BATTERY": 400}
    assert {requirement.production_order_id for requirement in requirements} == {
        "PO-EXISTING",
        "PO-PROPOSED",
    }


def test_production_in_different_periods_remains_time_phased() -> None:
    requirements = explode_one_level_bom(
        production_orders=(
            ProductionOrder("PO-W1", "CAM-A", 100, "W1", "R1"),
            ProductionOrder("PO-W2", "CAM-A", 50, "W2", "R1"),
        ),
        bom_components=CAM_A_BOM,
    )

    totals_by_period_and_component: dict[tuple[object, str], int | float] = (
        defaultdict(int)
    )
    for requirement in requirements:
        key = (
            requirement.production_start_period,
            requirement.component_item,
        )
        totals_by_period_and_component[key] += requirement.gross_requirement

    assert dict(totals_by_period_and_component) == {
        ("W1", "BOARD"): 100,
        ("W1", "BATTERY"): 200,
        ("W2", "BOARD"): 50,
        ("W2", "BATTERY"): 100,
    }


def test_missing_bom_fails_clearly() -> None:
    order_without_bom = ProductionOrder(
        production_order_id="PO-MISSING",
        parent_item="CAM-B",
        production_quantity=100,
        production_start_period="W1",
        bom_revision="R1",
    )

    with pytest.raises(
        ValueError,
        match=r"PO-MISSING.*CAM-B.*R1",
    ):
        explode_one_level_bom(
            production_orders=(order_without_bom,),
            bom_components=CAM_A_BOM,
        )
