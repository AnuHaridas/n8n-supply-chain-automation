from src.demo_export_data import build_demo_export_payload


def _cm_plan(*, with_comments: bool = True):
    payload = build_demo_export_payload(
        planner_comments=None if with_comments else {}
    )
    assert len(payload["cm_plans"]) == 1
    return payload["cm_plans"][0]


def test_unchanged_frozen_month_has_zero_delta() -> None:
    cm_plan = _cm_plan()
    row = cm_plan["rows"][0]["values"]

    assert row["Sep"] == 0
    assert row["Sep Delta"] == 0


def test_changed_frozen_month_has_correct_delta() -> None:
    cm_plan = _cm_plan()
    row = cm_plan["rows"][0]["values"]

    assert row["Oct"] == 0
    assert row["Oct Delta"] == -100
    assert cm_plan["rows"][0]["changed_frozen_periods"] == ["October"]


def test_open_month_updates_without_frozen_delta_column() -> None:
    cm_plan = _cm_plan()
    row = cm_plan["rows"][0]["values"]

    assert row["Nov"] == 100
    assert "Nov Delta" not in cm_plan["columns"]
    assert "Nov Delta" not in row


def test_frozen_change_without_comment_is_not_ready_for_communication() -> None:
    cm_plan = _cm_plan(with_comments=False)

    assert cm_plan["ready_for_communication"] is False
    assert cm_plan["missing_comment_periods"] == [
        {"item": "CAM-A", "period": "October"}
    ]
    assert cm_plan["rows"][0]["values"]["Comment"] == ""


def test_cm_output_contains_only_simple_cm_facing_columns() -> None:
    cm_plan = _cm_plan()
    expected_columns = [
        "SKU",
        "Sep",
        "Oct",
        "Nov",
        "Dec",
        "Sep Delta",
        "Oct Delta",
        "Comment",
    ]

    assert cm_plan["columns"] == expected_columns
    assert list(cm_plan["rows"][0]["values"]) == expected_columns
    assert cm_plan["ready_for_communication"] is True
