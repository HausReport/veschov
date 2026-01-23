from __future__ import annotations

import pandas as pd
import pytest

from veschov.ui.object_reports.AppliedDamageHeatmapsByAttackerReport import (
    compute_0th_order_metrics,
    compute_1st_order_metrics,
    compute_shots_per_round,
    t_critical_95,
)
from veschov.io.ShipSpecifier import ShipSpecifier


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


def test_compute_shots_per_round_uses_min_round() -> None:
    df = pd.DataFrame(
        {
            "round": [1, 2, 3],
            "shot_index": [0, 0, 0],
            "applied_damage": [10, 10, 10],
            "attacker_name": ["NPC", "NPC", "NPC"],
        }
    )
    shots, labels = compute_shots_per_round(
        df,
        ShipSpecifier(name="NPC", alliance=None, ship=None),
    )
    assert shots == [1, 1, 1]
    assert labels == [1, 2, 3]


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
