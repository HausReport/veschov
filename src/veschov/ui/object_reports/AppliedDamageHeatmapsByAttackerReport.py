from __future__ import annotations

import logging
import math
from typing import Optional, Sequence, override

import humanize
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from veschov.io.SessionInfo import SessionInfo, ShipSpecifier
from veschov.transforms.columns import (
    ATTACKER_COLUMN_CANDIDATES,
    TARGET_COLUMN_CANDIDATES,
    resolve_column,
)
from veschov.ui.components.number_format import get_number_format
from veschov.ui.object_reports.AttackerAndTargetReport import AttackerAndTargetReport
from veschov.utils.series import coerce_numeric

logger = logging.getLogger(__name__)

EPSILON = 1e-6
T_CRITICAL_95 = {
    1: 12.706,
    2: 4.303,
    3: 3.182,
    4: 2.776,
    5: 2.571,
    6: 2.447,
    7: 2.365,
    8: 2.306,
    9: 2.262,
    10: 2.228,
    11: 2.201,
    12: 2.179,
    13: 2.160,
    14: 2.145,
    15: 2.131,
    16: 2.120,
    17: 2.110,
    18: 2.101,
    19: 2.093,
    20: 2.086,
    21: 2.080,
    22: 2.074,
    23: 2.069,
    24: 2.064,
    25: 2.060,
    26: 2.056,
    27: 2.052,
    28: 2.048,
    29: 2.045,
    30: 2.042,
}


def detect_npc(players_df: pd.DataFrame | None) -> ShipSpecifier | None:
    """Return the NPC ship spec when the players metadata indicates one exists."""
    if players_df is None or players_df.empty:
        logger.warning("NPC detection skipped: players_df missing or empty.")
        return None

    npc_row = players_df.iloc[-1]
    alliance_value = ""
    for column in ("Alliance", "Player Alliance"):
        if column in players_df.columns:
            alliance_value = ShipSpecifier.normalize_text(npc_row.get(column))
            break
    if alliance_value:
        return None

    npc_name = ShipSpecifier.normalize_text(npc_row.get("Player Name"))
    npc_ship = ShipSpecifier.normalize_text(npc_row.get("Ship Name"))
    if not npc_name and not npc_ship:
        logger.warning("NPC detection skipped: missing name/ship in players_df.")
        return None
    return ShipSpecifier(name=npc_name or None, alliance=None, ship=npc_ship or None)


def compute_shots_per_round(
    df: pd.DataFrame,
    shooter_spec: ShipSpecifier,
) -> tuple[list[int], list[int]]:
    """Return shots-per-round and round labels for the shooter spec."""
    if df.empty:
        return [], []
    attacker_column = resolve_column(df, ATTACKER_COLUMN_CANDIDATES)
    if attacker_column is None:
        logger.warning("Shots-per-round missing attacker column candidates.")
        return [], []

    shooter_mask = _build_spec_mask(df, shooter_spec, attacker_column)
    shooter_df = df.loc[shooter_mask]
    if shooter_df.empty:
        return [], []

    rounds = pd.to_numeric(shooter_df["round"], errors="coerce").dropna()
    if rounds.empty:
        return [], []

    min_round = int(rounds.min())
    max_round = int(rounds.max())
    if max_round < min_round:
        return [], []

    round_counts = shooter_df.groupby("round").size().to_dict()
    round_labels = list(range(min_round, max_round + 1))
    shots_per_round = [
        int(round_counts.get(round_value, 0)) for round_value in round_labels
    ]
    return shots_per_round, round_labels


def compute_0th_order_metrics(shots_per_round: Sequence[int]) -> dict[str, float]:
    """Compute baseline-vs-observed suppression metrics."""
    if not shots_per_round:
        return {}
    shot_values = np.asarray(shots_per_round, dtype=float)
    total_rounds = len(shot_values)
    k_rounds = min(3, total_rounds)
    baseline = float(np.mean(shot_values[:k_rounds]))
    observed_total = float(shot_values.sum())
    expected_total = baseline * total_rounds
    lost_shots = max(0.0, expected_total - observed_total)
    lost_pct = lost_shots / max(expected_total, EPSILON)
    observed_avg = observed_total / total_rounds if total_rounds else 0.0
    return {
        "baseline": baseline,
        "observed_avg": observed_avg,
        "observed_total": observed_total,
        "expected_total": expected_total,
        "lost_shots": lost_shots,
        "lost_pct": lost_pct,
    }


def compute_1st_order_metrics(
    shots_per_round: Sequence[int],
) -> dict[str, float | bool | None]:
    """Compute slope metrics and detection confidence for suppression trends."""
    if not (shots_per_round and len(shots_per_round) >= 2):
        return {}

    shot_values = np.asarray(shots_per_round, dtype=float)
    nonzero_rounds = int(np.sum(shot_values > 0))
    if nonzero_rounds < 2:
        return {}

    x_values = np.arange(len(shot_values), dtype=float)
    x_mean = float(x_values.mean())
    y_mean = float(shot_values.mean())
    sxx = float(np.sum((x_values - x_mean) ** 2))
    if sxx <= 0:
        return {}

    sxy = float(np.sum((x_values - x_mean) * (shot_values - y_mean)))
    slope = sxy / sxx
    intercept = y_mean - slope * x_mean
    residuals = shot_values - (slope * x_values + intercept)
    sse = float(np.sum(residuals ** 2))
    degrees_freedom = len(shot_values) - 2
    slope_se = None
    ci_low = None
    ci_high = None
    suppression_detected = False
    if degrees_freedom > 0:
        sigma2 = sse / degrees_freedom
        slope_se = math.sqrt(sigma2 / sxx)
        t_critical = t_critical_95(degrees_freedom)
        ci_low = slope - t_critical * slope_se
        ci_high = slope + t_critical * slope_se
        suppression_detected = ci_high < 0
    else:
        logger.warning("Not enough degrees of freedom for slope confidence interval.")

    slope_norm = None
    if abs(intercept) > EPSILON:
        slope_norm = slope / max(abs(intercept), EPSILON)

    return {
        "slope": slope,
        "intercept": intercept,
        "slope_se": slope_se,
        "ci_low": ci_low,
        "ci_high": ci_high,
        "slope_norm": slope_norm,
        "suppression_detected": suppression_detected,
        "nonzero_rounds": nonzero_rounds,
    }


def t_critical_95(degrees_freedom: int) -> float:
    """Return a 95% two-tailed t critical value for the given degrees of freedom."""
    if degrees_freedom <= 0:
        return float("nan")
    if degrees_freedom > 30:
        return 1.96
    return T_CRITICAL_95.get(degrees_freedom, 1.96)


def _build_spec_mask(
    df: pd.DataFrame,
    spec: ShipSpecifier,
    attacker_column: str,
) -> pd.Series:
    """Return a dataframe mask for rows matching a ship spec."""
    mask = pd.Series(True, index=df.index)
    if spec.name:
        mask &= df[attacker_column] == spec.name
    if "attacker_alliance" in df.columns and spec.alliance:
        mask &= df["attacker_alliance"] == spec.alliance
    if "attacker_ship" in df.columns and spec.ship:
        mask &= df["attacker_ship"] == spec.ship
    return mask


def _format_metric(value: float | None, *, precision: int = 2) -> str:
    """Return formatted metric strings for display."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "N/A"
    return f"{value:.{precision}f}"

class AppliedDamageHeatmapsByAttackerReport(AttackerAndTargetReport):
    """Render per-attacker applied damage heatmaps by round and shot index."""

    def __init__(self) -> None:
        super().__init__()
        self.selected_attackers: list[ShipSpecifier] = []
        self.selected_targets: list[ShipSpecifier] = []
        self.outcome_lookup: dict[tuple[str, str, str], object] = {}
        self.global_zmin: float | None = None
        self.global_zmax: float | None = None
        self.number_format = "Human"
        self.session_info: SessionInfo | None = None
        self.suppression_df: pd.DataFrame | None = None
        self.attacker_column: str | None = None
        self.target_column: str | None = None

    def get_x_axis_text(self) -> Optional[str]:
        return "Round"

    def get_y_axis_text(self) -> Optional[str]:
        return "Shot # (within round)"

    def get_title_text(self) -> Optional[str]:
        return "Applied Damage Heatmaps"

    def get_under_title_text(self) -> Optional[str]:
        return (
            "Applied Damage Heatmaps show per-attacker damage applied by shot index within each round."
        )

    def get_under_chart_text(self) -> Optional[str]:
        return None

    def get_log_title(self) -> str:
        return "Applied Damage Heatmaps"

    def get_log_description(self) -> str:
        return "Upload a battle log to visualize applied damage by round and shot index."

    def get_lens_key(self) -> str:
        return "applied_damage_heatmaps"

    def get_derived_dataframes(self, df: pd.DataFrame, lens) -> Optional[list[pd.DataFrame]]:
        display_df = df.copy()
        display_df.attrs = {}
        self._refresh_selection_state(display_df)
        self.suppression_df = None
        self.attacker_column = None
        self.target_column = None

        required_columns = ("round", "shot_index", "applied_damage")
        missing_columns = [col for col in required_columns if col not in display_df.columns]
        if missing_columns:
            logger.warning(
                "Applied damage heatmaps missing required columns: %s",
                missing_columns,
            )
            st.error(f"Missing required columns: {', '.join(missing_columns)}")
            return None

        attacker_column = resolve_column(display_df, ATTACKER_COLUMN_CANDIDATES)
        target_column = resolve_column(display_df, TARGET_COLUMN_CANDIDATES)
        if attacker_column is None:
            logger.warning("Applied damage heatmaps missing attacker column candidates.")
            st.error("Missing attacker column for filtering.")
            return None
        if target_column is None:
            logger.warning("Applied damage heatmaps missing target column candidates.")
            st.error("Missing target column for filtering.")
            return None
        self.attacker_column = attacker_column
        self.target_column = target_column

        if not self.selected_attackers:
            logger.warning("Applied damage heatmaps has no selected attackers.")
            st.info("No attackers selected.")
            return None

        round_series = pd.to_numeric(display_df["round"], errors="coerce")
        shot_series = pd.to_numeric(display_df["shot_index"], errors="coerce")
        damage_series = coerce_numeric(display_df["applied_damage"])

        display_df = display_df.assign(
            round=round_series,
            shot_index=shot_series,
            applied_damage=damage_series,
        )
        display_df = display_df.dropna(subset=["round", "shot_index", "applied_damage"])
        display_df["round"] = display_df["round"].astype(int)
        display_df["shot_index"] = display_df["shot_index"].astype(int)
        display_df = display_df.loc[display_df["shot_index"] >= 0]

        suppression_df = display_df
        if self.selected_targets:
            target_names = {
                spec.normalized_name()
                for spec in self.selected_targets
                if spec.normalized_name()
            }
            if target_names:
                suppression_df = suppression_df.loc[
                    suppression_df[target_column].isin(target_names)
                ]
        self.suppression_df = suppression_df

        attacker_mask = self._build_attacker_mask(display_df, attacker_column)
        filtered_df = display_df.loc[attacker_mask]

        if self.selected_targets:
            target_names = {
                spec.normalized_name()
                for spec in self.selected_targets
                if spec.normalized_name()
            }
            if target_names:
                filtered_df = filtered_df.loc[filtered_df[target_column].isin(target_names)]

        if filtered_df.empty:
            logger.warning("Applied damage heatmaps filtered to empty dataframe.")
            st.warning("No matching damage events found for this selection.")
            return None

        damage_values = filtered_df["applied_damage"].dropna()
        if damage_values.empty:
            logger.warning("Applied damage heatmaps has no applied_damage values after filtering.")
            st.warning("No applied damage values found for this selection.")
            return None

        self.global_zmin = float(damage_values.min())
        self.global_zmax = float(damage_values.max())
        return [filtered_df]

    def get_plot_titles(self) -> list[str]:
        ret: list[str] = []
        for attacker in self.selected_attackers:
            tmp = f" {attacker.name} raw total damage by shot"
            ret.append(tmp)
        return ret

    def display_plots(self, dfs: list[pd.DataFrame]) -> None:
        filtered_df = dfs[0]
        self._display_firing_suppression_panel()
        # all_rounds = sorted(filtered_df["round"].unique())
        # all integers between min and max - want to see holes
        rmin = int(filtered_df["round"].min())
        rmax = int(filtered_df["round"].max())
        all_rounds = list(range(rmin, rmax + 1))
        attacker_index = 0
        for attacker in self.selected_attackers:
            attacker_label = self._format_ship_spec_label(attacker, self.outcome_lookup)
            st.subheader(attacker_label)

            attacker_df = filtered_df.loc[
                self._build_single_attacker_mask(filtered_df, attacker)
            ]
            if attacker_df.empty:
                st.caption("No attacks match current filters.")
                continue

            attacker_df = attacker_df.sort_values(["round", "shot_index"])
            attacker_df = attacker_df.assign(
                shot_in_round=attacker_df.groupby("round").cumcount()
            )

            x_rounds = all_rounds
            if not x_rounds:
                st.caption("No rounds available for this attacker.")
                continue

            max_shot = attacker_df["shot_in_round"].max()
            if pd.isna(max_shot):
                st.caption("No shots available for this attacker.")
                continue

            y_max = int(max_shot) + 1
            if y_max <= 0:
                st.caption("No shots available for this attacker.")
                continue

            z_matrix = np.full((y_max, len(x_rounds)), None, dtype=object)
            round_lookup = {round_value: index for index, round_value in enumerate(x_rounds)}

            for row in attacker_df.itertuples(index=False):
                round_value = int(row.round)
                shot_index = int(row.shot_in_round)
                if shot_index < 0:
                    continue
                col_index = round_lookup.get(round_value)
                if col_index is None:
                    continue
                current_value = z_matrix[shot_index, col_index]
                damage_value = float(row.applied_damage)
                if current_value is None:
                    z_matrix[shot_index, col_index] = damage_value
                else:
                    z_matrix[shot_index, col_index] = float(current_value) + damage_value

            formatted_matrix = [
                [
                    self._format_applied_damage_value(z_matrix[row_index, col_index])
                    for col_index in range(len(x_rounds))
                ]
                for row_index in range(y_max)
            ]

            fig = go.Figure(
                data=[
                    go.Heatmap(
                        z=z_matrix,
                        x=x_rounds,
                        y=list(range(y_max)),
                        zmin=self.global_zmin,
                        zmax=self.global_zmax,
                        colorbar={"title": "Applied Damage"},
                        customdata=formatted_matrix,
                        hovertemplate=(
                            "Round %{x}<br>Shot %{y}<br>Applied %{customdata}<extra></extra>"
                        ),
                    )
                ]
            )
            fig.update_layout(
                # title = self.get_plot_titles()[attacker_index],
                xaxis_title=self.get_x_axis_text(),
                yaxis_title=self.get_y_axis_text(),
                yaxis_autorange="reversed",
            )
            st.plotly_chart(fig, width="stretch")
            attacker_index += 1

    def display_tables(self, dfs: list[pd.DataFrame]) -> None:
        return None

    @override
    def render_debug_info(self, dfs: list[pd.DataFrame]) -> None:
        return None

    def _build_attacker_mask(self, df: pd.DataFrame, attacker_column: str) -> pd.Series:
        mask = pd.Series(False, index=df.index)
        for spec in self.selected_attackers:
            if not (spec.name or spec.alliance or spec.ship):
                continue
            spec_mask = pd.Series(True, index=df.index)
            if spec.name:
                spec_mask &= df[attacker_column] == spec.name
            if "attacker_alliance" in df.columns and spec.alliance:
                spec_mask &= df["attacker_alliance"] == spec.alliance
            if "attacker_ship" in df.columns and spec.ship:
                spec_mask &= df["attacker_ship"] == spec.ship
            mask |= spec_mask
        return mask

    def _build_single_attacker_mask(self, df: pd.DataFrame, spec: ShipSpecifier) -> pd.Series:
        attacker_column = resolve_column(df, ATTACKER_COLUMN_CANDIDATES)
        spec_mask = pd.Series(True, index=df.index)
        if attacker_column and spec.name:
            spec_mask &= df[attacker_column] == spec.name
        if "attacker_alliance" in df.columns and spec.alliance:
            spec_mask &= df["attacker_alliance"] == spec.alliance
        if "attacker_ship" in df.columns and spec.ship:
            spec_mask &= df["attacker_ship"] == spec.ship
        return spec_mask

    def _refresh_selection_state(self, df: pd.DataFrame) -> None:
        self.number_format = get_number_format()
        resolved_session_info = st.session_state.get("session_info")
        self.session_info = (
            resolved_session_info
            if isinstance(resolved_session_info, SessionInfo)
            else None
        )
        selected_attackers, selected_targets = self._resolve_selected_specs_from_state(
            resolved_session_info,
        )
        self.selected_attackers = list(selected_attackers)
        self.selected_targets = list(selected_targets)
        self.outcome_lookup = self._build_outcome_lookup(self.session_info, df)

    def _format_applied_damage_value(self, value: object) -> str:
        if value is None or pd.isna(value):
            return "—"
        numeric_value = float(value)
        if self.number_format == "Human" and abs(numeric_value) >= 1_000_000:
            return humanize.intword(numeric_value, format="%.1f")
        if numeric_value.is_integer():
            return f"{int(numeric_value):,}"
        return f"{numeric_value:,}"

    def _display_firing_suppression_panel(self) -> None:
        if self.suppression_df is None or self.suppression_df.empty:
            return

        shooter_spec, shooter_label = self._resolve_suppression_shooter()
        if shooter_spec is None:
            return

        shots_per_round, round_labels = compute_shots_per_round(
            self.suppression_df,
            shooter_spec,
        )
        st.subheader("Firing Suppression")
        st.caption(f"Shooter: {shooter_label}")
        if not shots_per_round:
            logger.warning("Firing suppression has no events for shooter %s.", shooter_label)
            st.caption("No applied-damage events found for this shooter.")
            return

        zeroth_metrics = compute_0th_order_metrics(shots_per_round)
        first_metrics = compute_1st_order_metrics(shots_per_round)

        metric_cols = st.columns(4)
        metric_cols[0].metric(
            "Baseline shots/round",
            _format_metric(zeroth_metrics.get("baseline")),
        )
        metric_cols[1].metric(
            "Observed avg shots/round",
            _format_metric(zeroth_metrics.get("observed_avg")),
        )
        metric_cols[2].metric(
            "Lost shots (0th)",
            _format_metric(zeroth_metrics.get("lost_shots")),
        )
        lost_pct_value = zeroth_metrics.get("lost_pct")
        lost_pct_label = "N/A"
        if isinstance(lost_pct_value, float):
            lost_pct_label = f"{lost_pct_value:.1%}"
        metric_cols[3].metric("Lost shots (%)", lost_pct_label)

        trend_cols = st.columns(4)
        trend_cols[0].metric("Slope (m)", _format_metric(first_metrics.get("slope"), precision=3))
        trend_cols[1].metric(
            "Normalized slope",
            _format_metric(first_metrics.get("slope_norm"), precision=3),
        )
        detection_label = "Insufficient rounds"
        if first_metrics:
            detection_label = (
                "Detected" if first_metrics.get("suppression_detected") else "Inconclusive"
            )
        trend_cols[2].metric("Suppression trend", detection_label)
        trend_cols[3].metric(
            "Nonzero rounds",
            _format_metric(first_metrics.get("nonzero_rounds"), precision=0),
        )

        self._render_shots_sparkline(shots_per_round, round_labels, first_metrics)

    def _render_shots_sparkline(
        self,
        shots_per_round: Sequence[int],
        round_labels: Sequence[int],
        first_metrics: dict[str, float | bool | None],
    ) -> None:
        x_rounds = list(round_labels)
        fig = go.Figure()
        fig.add_trace(
            go.Bar(
                x=x_rounds,
                y=shots_per_round,
                name="Shots per round",
                marker_color="#4C78A8",
            )
        )
        slope = first_metrics.get("slope")
        intercept = first_metrics.get("intercept")
        if isinstance(slope, float) and isinstance(intercept, float):
            fit_values = [
                slope * round_index + intercept for round_index in range(len(x_rounds))
            ]
            fig.add_trace(
                go.Scatter(
                    x=x_rounds,
                    y=fit_values,
                    mode="lines",
                    name="OLS fit",
                    line=dict(color="#F58518", width=2),
                )
            )
        fig.update_layout(
            height=220,
            margin=dict(l=20, r=20, t=20, b=20),
            xaxis_title="Round",
            yaxis_title="Shots",
            legend=dict(orientation="h"),
        )
        st.plotly_chart(fig, width="stretch")

    def _resolve_suppression_shooter(self) -> tuple[ShipSpecifier | None, str]:
        npc_spec = detect_npc(self.session_info.players_df if self.session_info else None)
        if npc_spec is not None:
            npc_label = self._format_ship_spec_label(npc_spec, self.outcome_lookup)
            return npc_spec, f"NPC (auto-detected) — {npc_label}"

        if not self.selected_attackers:
            logger.warning("Firing suppression skipped: no attackers selected.")
            return None, ""

        shooter_spec = self.selected_attackers[0]
        if len(self.selected_attackers) > 1:
            logger.warning(
                "Multiple attackers selected; using first for suppression analysis: %s",
                shooter_spec,
            )
        shooter_label = self._format_ship_spec_label(shooter_spec, self.outcome_lookup)
        return shooter_spec, shooter_label
