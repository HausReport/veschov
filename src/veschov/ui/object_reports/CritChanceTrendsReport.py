"""Streamlit UI for critical hit chance trends."""

from __future__ import annotations

import logging
from typing import Optional, override

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from veschov.ui.chirality import Lens
from veschov.ui.object_reports.AbstractReport import AbstractReport
from veschov.ui.object_reports.RoundOrShotsReport import RoundOrShotsReport
from veschov.ui.pretty_stats.Statistic import Statistic
from veschov.ui.view_by import prepare_round_view
from veschov.utils.series import coerce_numeric

logger = logging.getLogger(__name__)

CRIT_LINE_COLOR = "#1f77b4"
SMOOTHED_LINE_COLOR = "#d62728"
TREND_LINE_COLOR = "#2ca02c"
CI_FILL_COLOR = "rgba(31, 119, 180, 0.15)"


class CritChanceTrendsReport(RoundOrShotsReport):
    """Render the critical chance trend report."""
    under_title_text = "Crit Chance Trends shows cumulative crit chance over time, with a smoothed "
    "trend and Wilson confidence bounds."
    VIEW_BY_KEY = "crit_chance_trends_view_by"
    Z_SCORE = 1.96
    x_axis_text = "Shot or Round Number"
    y_axis_text = "Critical Hit Chance"
    title_text = "Crit Chance Trends"
    lens_key = f"crit_chance_trends_{AbstractReport.key_suffix}"

    def __init__(self) -> None:
        super().__init__()
        self.battle_filename = "Session battle data"
        self.x_axis = "shot_index_global"

    @override
    @property
    def under_chart_text(self) -> Optional[str]:
        kind = self._resolve_view_by().title()
        if kind == "Round":
            return (
                "Points show per-round crit chance, with a smoothed line, linear trend, "
                "and Wilson interval bands."
            )
        return (
            "Lines show cumulative crit chance and a smoothed 3-point average over global shots, "
            "with Wilson interval bands."
        )

    def get_descriptive_statistics(self) -> list[Statistic]:
        return []


    def get_derived_dataframes(self, df: pd.DataFrame, lens: Lens | None) -> Optional[list[pd.DataFrame]]:
        display_df = df.copy()
        display_df.attrs = {}

        typ = display_df["event_type"].astype("string").str.strip().str.lower()
        total_normal = display_df["total_normal"].fillna(0)
        total_iso = display_df["total_iso"].fillna(0)
        attack_mask = typ.eq("attack") & ((total_normal + total_iso) > 0)
        shot_df = display_df.loc[attack_mask].copy()
        shot_df["total_normal"] = total_normal.loc[attack_mask].fillna(0)
        shot_df["total_iso"] = total_iso.loc[attack_mask].fillna(0)

        if "battle_event" in shot_df.columns:
            shot_df = shot_df.sort_values("battle_event", kind="stable")

        shot_df = self.apply_combat_lens(shot_df, lens)

        if shot_df.empty:
            logger.warning("No matching attack events found for crit chance trends selection.")
            st.warning("No matching attack events found for this selection.")
            return None

        self.view_by = self._resolve_view_by()
        self.battle_filename = st.session_state.get("battle_filename") or "Session battle data"

        if self.view_by == "Round":
            round_df = self._build_round_df(shot_df)
            if round_df is None:
                return None
            return [round_df, shot_df]

        shot_view_df = self._build_shot_df(shot_df)
        if shot_view_df is None:
            return None
        return [shot_view_df, shot_df]

    def display_plots(self, dfs: list[pd.DataFrame]) -> None:
        if self.view_by == "Round":
            round_df = dfs[0]
            fig = self._build_round_plot(round_df)
        else:
            shot_view_df = dfs[0]
            fig = self._build_shot_plot(shot_view_df)
        st.plotly_chart(fig, width="stretch")

    def display_tables(self, dfs: list[pd.DataFrame]) -> None:
        show_table = st.checkbox("Show raw table", value=False)
        if not show_table:
            return

        if self.view_by == "Round":
            st.caption("Raw rows include per-round crit counts and confidence intervals.")
            st.dataframe(dfs[0], width="stretch")
            return

        st.caption("Raw rows include cumulative crit counts and confidence intervals per shot.")
        st.dataframe(dfs[0], width="stretch")

    @override
    def render_debug_info(self, df: pd.DataFrame) -> None:
        return None

    def _build_shot_df(self, shot_df: pd.DataFrame) -> pd.DataFrame | None:
        if "round" not in shot_df.columns or "shot_index" not in shot_df.columns:
            logger.warning("Shot view requires round and shot_index columns.")
            st.warning("Shot view is unavailable because round or shot index data is missing.")
            return None

        round_series = coerce_numeric(shot_df["round"])
        shot_index_series = coerce_numeric(shot_df["shot_index"])
        valid_mask = round_series.notna() & shot_index_series.notna()
        if not valid_mask.all():
            logger.warning("Dropping %d rows missing round or shot index data.", (~valid_mask).sum())
        filtered = shot_df.loc[valid_mask].copy()
        if filtered.empty:
            logger.warning("No valid shot rows found after filtering for round/shot index data.")
            st.warning("No valid shot rows found for this selection.")
            return None

        filtered = filtered.assign(
            round=round_series.loc[valid_mask].astype(int),
            shot_index=shot_index_series.loc[valid_mask].astype(int),
        )
        filtered = filtered.sort_values(["round", "shot_index"], kind="stable")

        shot_index_global = pd.Series(
            range(1, len(filtered) + 1),
            index=filtered.index,
            dtype="Int64",
        )
        crit_flags = filtered["is_crit"].fillna(False).astype(bool)
        cum_crits = crit_flags.cumsum().astype(int)
        cum_shots = shot_index_global.astype(int)
        crit_chance = (cum_crits / cum_shots).astype(float)
        wilson_lower, wilson_upper = self._wilson_interval(cum_crits, cum_shots)
        smoothed = self._smooth_series(crit_chance)

        return pd.DataFrame(
            {
                "shot_index_global": shot_index_global.astype(int),
                "cum_shots": cum_shots,
                "cum_crits": cum_crits,
                "crit_chance": crit_chance,
                "wilson_lower": wilson_lower,
                "wilson_upper": wilson_upper,
                "smoothed": smoothed,
            }
        )

    def _build_round_df(self, shot_df: pd.DataFrame) -> pd.DataFrame | None:
        round_df = prepare_round_view(shot_df)
        if round_df is None:
            return None
        crit_flags = round_df["is_crit"].fillna(False).astype(bool)
        grouped = round_df.assign(is_crit=crit_flags).groupby("round", dropna=False)
        summary = grouped["is_crit"].agg(shots="size", crits="sum")
        summary = summary.sort_index()
        summary = summary.loc[summary["shots"] > 0].copy()
        if summary.empty:
            logger.warning("No rounds with valid shot counts found.")
            st.warning("No round data available for this selection.")
            return None

        summary["crit_chance"] = (summary["crits"] / summary["shots"]).astype(float)
        wilson_lower, wilson_upper = self._wilson_interval(summary["crits"], summary["shots"])
        summary["wilson_lower"] = wilson_lower
        summary["wilson_upper"] = wilson_upper
        summary["smoothed_round"] = self._smooth_series(summary["crit_chance"])
        summary["trend"] = self._trend_line(summary.index.to_series(), summary["crit_chance"])
        summary = summary.reset_index()
        return summary

    def _build_shot_plot(self, shot_view_df: pd.DataFrame) -> go.Figure:
        x_values = shot_view_df["shot_index_global"].astype(int)
        crit_pct = shot_view_df["crit_chance"] * 100.0
        smoothed_pct = shot_view_df["smoothed"] * 100.0
        lower_pct = shot_view_df["wilson_lower"] * 100.0
        upper_pct = shot_view_df["wilson_upper"] * 100.0

        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=x_values,
                y=upper_pct,
                mode="lines",
                line=dict(width=0),
                hoverinfo="skip",
                showlegend=False,
            )
        )
        fig.add_trace(
            go.Scatter(
                x=x_values,
                y=lower_pct,
                mode="lines",
                line=dict(width=0),
                fill="tonexty",
                fillcolor=CI_FILL_COLOR,
                name="95% Wilson interval",
                hoverinfo="skip",
            )
        )
        fig.add_trace(
            go.Scatter(
                x=x_values,
                y=crit_pct,
                mode="lines",
                line=dict(color=CRIT_LINE_COLOR, width=2),
                name="Cumulative crit chance",
            )
        )
        fig.add_trace(
            go.Scatter(
                x=x_values,
                y=smoothed_pct,
                mode="lines",
                line=dict(color=SMOOTHED_LINE_COLOR, width=2),
                name="Smoothed (3-pt)",
            )
        )

        fig.update_layout(
            title=f"{self.title_text} — {self.battle_filename}",
            xaxis_title="Global Shot Index",
            yaxis_title="Crit Chance (%)",
            legend_title_text="",
        )
        fig.update_yaxes(range=[0, 100], ticksuffix="%")
        return fig

    def _build_round_plot(self, round_df: pd.DataFrame) -> go.Figure:
        x_values = round_df["round"].astype(int)
        crit_pct = round_df["crit_chance"] * 100.0
        smoothed_pct = round_df["smoothed_round"] * 100.0
        trend_pct = round_df["trend"] * 100.0
        lower_pct = round_df["wilson_lower"] * 100.0
        upper_pct = round_df["wilson_upper"] * 100.0

        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=x_values,
                y=upper_pct,
                mode="lines",
                line=dict(width=0),
                hoverinfo="skip",
                showlegend=False,
            )
        )
        fig.add_trace(
            go.Scatter(
                x=x_values,
                y=lower_pct,
                mode="lines",
                line=dict(width=0),
                fill="tonexty",
                fillcolor=CI_FILL_COLOR,
                name="95% Wilson interval",
                hoverinfo="skip",
            )
        )
        fig.add_trace(
            go.Scatter(
                x=x_values,
                y=crit_pct,
                mode="markers",
                marker=dict(color=CRIT_LINE_COLOR, size=7),
                name="Actual crit chance",
            )
        )
        fig.add_trace(
            go.Scatter(
                x=x_values,
                y=smoothed_pct,
                mode="lines",
                line=dict(color=SMOOTHED_LINE_COLOR, width=2),
                name="Smoothed (3-pt)",
            )
        )
        fig.add_trace(
            go.Scatter(
                x=x_values,
                y=trend_pct,
                mode="lines",
                line=dict(color=TREND_LINE_COLOR, width=2, dash="dash"),
                name="Trend line",
            )
        )

        fig.update_layout(
            title=f"{self.title_text} — {self.battle_filename}",
            xaxis_title="Round",
            yaxis_title="Crit Chance (%)",
            legend_title_text="",
        )
        fig.update_yaxes(range=[0, 100], ticksuffix="%")
        return fig

    def _smooth_series(self, series: pd.Series) -> pd.Series:
        values = series.astype(float).copy()
        if len(values) == 0:
            return values
        if len(values) == 1:
            return values.clip(0.0, 1.0)

        smoothed = values.rolling(window=3, center=True).mean()
        if len(values) == 2:
            mean_value = values.mean()
            smoothed.iloc[0] = mean_value
            smoothed.iloc[1] = mean_value
        else:
            smoothed.iloc[0] = values.iloc[:2].mean()
            smoothed.iloc[-1] = values.iloc[-2:].mean()
            smoothed = smoothed.fillna(values)
        return smoothed.clip(0.0, 1.0)

    def _wilson_interval(
            self,
            successes: pd.Series,
            total: pd.Series,
    ) -> tuple[pd.Series, pd.Series]:
        successes = successes.astype(float)
        total = total.astype(float)
        n = total.to_numpy()
        k = successes.to_numpy()
        if (n <= 0).any():
            logger.warning("Wilson interval computed with zero or negative totals.")
        z = self.Z_SCORE
        with np.errstate(divide="ignore", invalid="ignore"):
            p = np.divide(k, n, out=np.zeros_like(k, dtype=float), where=n > 0)
            denom = 1.0 + (z ** 2) / n
            center = (p + (z ** 2) / (2.0 * n)) / denom
            margin = (
                    z
                    * np.sqrt((p * (1.0 - p) / n) + (z ** 2) / (4.0 * n ** 2))
                    / denom
            )
        lower = np.where(n > 0, center - margin, 0.0)
        upper = np.where(n > 0, center + margin, 0.0)
        lower_series = pd.Series(lower, index=successes.index).clip(0.0, 1.0)
        upper_series = pd.Series(upper, index=successes.index).clip(0.0, 1.0)
        return lower_series, upper_series

    def _trend_line(self, rounds: pd.Series, crit_chance: pd.Series) -> pd.Series:
        x_values = rounds.astype(float)
        y_values = crit_chance.astype(float)
        if len(x_values) < 2:
            logger.warning("Trend line omitted; fewer than two rounds available.")
            return y_values.clip(0.0, 1.0)
        if float(np.var(x_values)) == 0.0:
            logger.warning("Trend line omitted; round values have zero variance.")
            return y_values.clip(0.0, 1.0)
        slope, intercept = np.polyfit(x_values, y_values, deg=1)
        trend_raw = intercept + slope * x_values
        return pd.Series(trend_raw, index=rounds.index).clip(0.0, 1.0)
