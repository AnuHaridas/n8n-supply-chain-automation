import pytest

from src.planning import (
    PeriodOffsetResult,
    calculate_po_release_period,
    calculate_production_start_period,
)


def test_fg_available_w3_with_two_period_lead_time_starts_w1() -> None:
    result = calculate_production_start_period(
        ordered_calendar=("W1", "W2", "W3"),
        fg_available_period="W3",
        manufacturing_lead_time_periods=2,
    )

    assert result == PeriodOffsetResult(
        target_period="W3",
        lead_time_periods=2,
        offset_period="W1",
        status="OK",
    )


def test_component_needed_w1_with_two_period_lead_time_releases_w_minus_1() -> None:
    result = calculate_po_release_period(
        ordered_calendar=("W-1", "W0", "W1", "W2"),
        component_need_period="W1",
        purchase_lead_time_periods=2,
    )

    assert result.offset_period == "W-1"
    assert result.status == "OK"


def test_insufficient_calendar_lookback_returns_past_due_release() -> None:
    result = calculate_po_release_period(
        ordered_calendar=("W1", "W2", "W3"),
        component_need_period="W1",
        purchase_lead_time_periods=2,
    )

    assert result.offset_period is None
    assert result.status == "PAST_DUE_RELEASE"


def test_zero_and_negative_lead_times_fail_clearly() -> None:
    with pytest.raises(ValueError, match="positive whole number"):
        calculate_production_start_period(
            ordered_calendar=("W1", "W2", "W3"),
            fg_available_period="W3",
            manufacturing_lead_time_periods=0,
        )

    with pytest.raises(ValueError, match="positive whole number"):
        calculate_po_release_period(
            ordered_calendar=("W1", "W2", "W3"),
            component_need_period="W3",
            purchase_lead_time_periods=-1,
        )
