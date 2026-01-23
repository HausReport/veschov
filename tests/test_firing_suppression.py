from __future__ import annotations

import pytest

from veschov.ui.object_reports.AppliedDamageHeatmapsByAttackerReport import (
    compute_0th_order_metrics,
    compute_1st_order_metrics,
    t_critical_95,
)


def test_firing_suppression_metrics_sample_vector() -> None:
    shots = [7, 7, 7, 4, 1, 5, 2, 3, 1]
    zeroth = compute_0th_order_metrics(shots)
    first = compute_1st_order_metrics(shots)

    assert zeroth["baseline"] == pytest.approx(7.0)
    assert zeroth["lost_shots"] == pytest.approx(26.0)
    assert zeroth["lost_pct"] == pytest.approx(26.0 / 63.0)

    assert isinstance(first.get("slope"), float)
    assert first["slope"] == pytest.approx(-0.75, abs=0.02)
    assert first["suppression_detected"] is True


def test_firing_suppression_insufficient_nonzero_rounds() -> None:
    shots = [0, 0, 1]
    first = compute_1st_order_metrics(shots)
    assert first == {}


@pytest.mark.parametrize(
    ("degrees_freedom", "expected"),
    [
        (1, 12.706),
        (10, 2.228),
        (30, 2.042),
        (31, 1.96),
    ],
)
def test_t_critical_95_lookup(degrees_freedom: int, expected: float) -> None:
    assert t_critical_95(degrees_freedom) == pytest.approx(expected)
