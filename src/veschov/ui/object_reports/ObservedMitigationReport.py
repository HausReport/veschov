"""Streamlit UI for observed mitigation analysis."""

from __future__ import annotations

import logging
from typing import Optional, override

import pandas as pd
import plotly.express as px
import streamlit as st

from veschov.ui.components.number_format import get_number_format
from veschov.ui.object_reports.AbstractReport import AbstractReport
from veschov.ui.object_reports.MultiAttackerAndTargetReport import MultiAttackerAndTargetReport
from veschov.ui.view_by import prepare_round_view
from veschov.utils.series import coerce_numeric

logger = logging.getLogger(__name__)

OPTIONAL_PREVIEW_COLUMNS = (
    "round",
    "battle_event",
    "is_crit",
    "attacker_name",
    "attacker_ship",
    "attacker_alliance",
    "target_name",
    "target_ship",
    "target_alliance",
)


class ObservedMitigationReport(MultiAttackerAndTargetReport):
    """Render observed mitigation per shot or round."""

    VIEW_BY_KEY = "observed_mitigation_view_by"
    MITIGATION_CAP = 71.2
    under_title_text = "Shows observed normal-lane mitigation per hit using mitigated_normal / total_normal. "
    "Round view is damage-weighted across all hits in the round."
    under_chart_text = "Use the view selector to switch between shot-level values and round-level averages."
    x_axis_text = "Shot or Round Number"
    y_axis_text = "Observed Mitigation (Normal Lane)"
    title_text = "Observed Mitigation"
    lens_key = f"observed_mitigation_{AbstractReport.key_suffix}"

    def __init__(self) -> None:
        super().__init__()
        self.battle_filename = "Session battle data"
        self.number_format = "Human"
        self.x_axis = "shot_index"

    def _coerce_mitigation_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        if "total_normal" not in df.columns:
            raise KeyError("total_normal")
        if "mitigated_normal" not in df.columns:
            raise KeyError("mitigated_normal")
        df = df.copy()
        df["total_normal"] = coerce_numeric(df["total_normal"])
        df["mitigated_normal"] = coerce_numeric(df["mitigated_normal"])
        return df

    def _filter_valid_rows(self, df: pd.DataFrame) -> pd.DataFrame:
        filtered = df.copy()
        filtered = filtered[filtered["total_normal"].notna()].copy()
        filtered = filtered[filtered["total_normal"] > 0].copy()
        filtered = filtered[filtered["mitigated_normal"].notna()].copy()
        return filtered

    def _prepare_shot_index(self, df: pd.DataFrame) -> pd.DataFrame:
        if "shot_index" not in df.columns:
            shot_index = pd.Series(
                range(1, len(df) + 1),
                index=df.index,
                dtype="Int64",
            )
            return df.assign(shot_index=shot_index)
        shot_index = coerce_numeric(df["shot_index"])
        shot_df = df.assign(shot_index=shot_index)
        shot_df = shot_df[shot_df["shot_index"].notna()].copy()
        if shot_df.empty:
            return shot_df
        shot_df["shot_index"] = shot_df["shot_index"].astype(int)
        return shot_df

    @staticmethod
    def _compute_observed_mitigation(
            mitigated: pd.Series,
            total: pd.Series,
    ) -> pd.Series:
        ratio = mitigated.div(total)
        return ratio.clip(lower=0, upper=1)

    def _format_mitigation_percent(self, series: pd.Series) -> pd.Series:
        return series.mul(100)

    def get_derived_dataframes(self, df: pd.DataFrame, lens) -> Optional[list[pd.DataFrame]]:
        display_df = df.copy()
        display_df.attrs = {}

        try:
            display_df = self._coerce_mitigation_columns(display_df)
        except KeyError as exc:
            st.error(f"Missing required column: {exc.args[0]}")
            return None

        filtered_df = self.apply_combat_lens(display_df, lens)
        if filtered_df.empty:
            st.warning("No matching mitigation events found for this selection.")
            return None

        filtered_df = self._filter_valid_rows(filtered_df)
        if filtered_df.empty:
            st.warning("No valid mitigation rows found (total_normal must be > 0).")
            return None

        try:
            filtered_df = self._build_attacker_key(filtered_df)
        except KeyError as exc:
            st.error(f"Missing required column: {exc.args[0]}")
            return None

        self.view_by = self._resolve_view_by()
        self.battle_filename = st.session_state.get("battle_filename") or "Session battle data"

        if self.view_by == "Round":
            if "round" not in filtered_df.columns:
                st.error("Missing required column: round")
                return None
            round_df = prepare_round_view(filtered_df)
            if round_df is None:
                return None
            grouped = (
                round_df.groupby(["attacker_key", "round"], dropna=False)
                .agg(
                    sum_total=("total_normal", "sum"),
                    sum_mitigated=("mitigated_normal", "sum"),
                )
                .reset_index()
            )
            grouped = grouped[grouped["sum_total"] > 0].copy()
            if grouped.empty:
                st.warning("No round data is available for this selection.")
                return None
            grouped["observed_mitigation"] = self._compute_observed_mitigation(
                grouped["sum_mitigated"],
                grouped["sum_total"],
            )
            self.x_axis = "round"
            plot_df = grouped
            table_df = grouped
        else:
            shot_df = filtered_df.copy()
            if "battle_event" in shot_df.columns:
                shot_df = shot_df.sort_values("battle_event", kind="stable")
            shot_df = self._prepare_shot_index(shot_df)
            if shot_df.empty:
                st.warning("No shot index data is available for this selection.")
                return None
            duplicate_mask = shot_df["shot_index"].duplicated(keep=False)
            if duplicate_mask.any():
                duplicate_count = shot_df.loc[duplicate_mask, "shot_index"].nunique()
                logger.warning(
                    "Multiple mitigation rows share the same shot_index (%s distinct values). "
                    "Reindexing shots sequentially for display.",
                    duplicate_count,
                )
            shot_df["observed_mitigation"] = self._compute_observed_mitigation(
                shot_df["mitigated_normal"],
                shot_df["total_normal"],
            )
            plot_df = shot_df.reset_index(drop=True)
            plot_df["shot_index"] = pd.Series(
                range(1, len(plot_df) + 1),
                index=plot_df.index,
                dtype="Int64",
            )
            self.x_axis = "shot_index"
            table_df = shot_df

        return [plot_df, table_df]

    def get_plot_titles(self) -> list[str]:
        kind = self._resolve_view_by().title()
        return [f"Observed Mitigation of Defender by {kind}"]

    def display_plots(self, dfs: list[pd.DataFrame]) -> None:
        plot_df = dfs[0].copy()
        number_format = self.number_format or get_number_format()
        plot_df["observed_mitigation_pct"] = self._format_mitigation_percent(
            plot_df["observed_mitigation"],
        )
        plot_df["observed_mitigation_display"] = plot_df["observed_mitigation_pct"].map(
            lambda value: f"{value:.1f}%" if pd.notna(value) else "—",
        )
        for column in ("total_normal", "mitigated_normal", "sum_total", "sum_mitigated"):
            if column in plot_df.columns:
                plot_df[f"{column}_display"] = self._format_large_number_series(
                    plot_df[column],
                    number_format,
                )
        for column in (
                "total_normal_display",
                "mitigated_normal_display",
                "sum_total_display",
                "sum_mitigated_display",
        ):
            if column not in plot_df.columns:
                plot_df[column] = "—"
        if "round" in plot_df.columns:
            plot_df["round_display"] = plot_df["round"].map(
                lambda value: str(int(value)) if pd.notna(value) else "—",
            )
        else:
            plot_df["round_display"] = "—"

        hover_columns = (
            "round",
            "observed_mitigation_display",
            "total_normal_display",
            "mitigated_normal_display",
            "sum_total_display",
            "sum_mitigated_display",
            "attacker_key",
            "round_display",
        )
        plot_args = {
            "data_frame": plot_df,
            "x": self.x_axis,
            "y": "observed_mitigation_pct",
            "color": "attacker_key",
        }
        plot_args.update(self._build_attacker_series_style(plot_df))
        hover_data = {column: True for column in hover_columns if column in plot_df.columns}
        hover_data["observed_mitigation_pct"] = False
        plot_args["hover_data"] = hover_data
        n_rounds = plot_df[self.x_axis].nunique()
        if self.view_by == "Round" and n_rounds == 1:
            fig = px.bar(**plot_args)
            fig.update_layout(barmode="group")
            fig.update_xaxes(range=[0.5, 1.5])
        else:
            fig = px.line(**plot_args, markers=True)
            max_value = plot_df[self.x_axis].max()
            if pd.notna(max_value):
                fig.update_xaxes(range=[1, int(max_value)])
        fig.update_layout(
            xaxis_title=self.x_axis_text,
            yaxis_title=self.y_axis_text,
        )
        fig.update_yaxes(range=[0, 100], tickformat=".1f", ticksuffix="%")
        fig.add_hline(
            y=self.MITIGATION_CAP,
            line_color="red",
            line_dash="dash",
            line_width=2,
            annotation_text="Normal Mitigation Cap.",
            annotation_position="top left",
            annotation_font_color="red",
        )
        if self.view_by == "Round":
            fig.update_traces(
                customdata=plot_df[
                    [
                        "attacker_key",
                        "sum_total_display",
                        "sum_mitigated_display",
                    ]
                ],
                hovertemplate=(
                    "Attacker: %{customdata[0]}<br>"
                    f"{self.x_axis_text}: %{{x}}<br>"
                    "Observed Mitigation: %{y:.1f}%<br>"
                    "Total Normal (Sum): %{customdata[1]}<br>"
                    "Mitigated Normal (Sum): %{customdata[2]}<extra></extra>"
                ),
            )
        else:
            fig.update_traces(
                customdata=plot_df[
                    [
                        "attacker_key",
                        "total_normal_display",
                        "mitigated_normal_display",
                        "round_display",
                    ]
                ],
                hovertemplate=(
                    "Attacker: %{customdata[0]}<br>"
                    f"{self.x_axis_text}: %{{x}}<br>"
                    "Observed Mitigation: %{y:.1f}%<br>"
                    "Total Normal: %{customdata[1]}<br>"
                    "Mitigated Normal: %{customdata[2]}<br>"
                    "Round: %{customdata[3]}<extra></extra>"
                ),
            )
        st.plotly_chart(fig, width="stretch")

    def display_tables(self, dfs: list[pd.DataFrame]) -> None:
        table_df = dfs[1]
        show_table = st.checkbox("Show raw table", value=False)
        if not show_table:
            return
        if self.view_by == "Round":
            preview_cols = [
                "round",
                "attacker_key",
                "observed_mitigation",
                "sum_total",
                "sum_mitigated",
            ]
            preview_cols = [col for col in preview_cols if col in table_df.columns]
            st.caption("Preview of round-level observed mitigation values.")
            st.dataframe(table_df.loc[:, preview_cols].head(200), width="stretch")
            return

        preview_cols = [
            "shot_index",
            "attacker_key",
            "observed_mitigation",
            "total_normal",
            "mitigated_normal",
        ]
        if "round" in table_df.columns:
            preview_cols.append("round")
        preview_cols.extend(col for col in OPTIONAL_PREVIEW_COLUMNS if col in table_df.columns)
        preview_cols = list(dict.fromkeys(preview_cols))
        st.caption("Preview of shot-level mitigation values and optional combat log metadata.")
        st.dataframe(table_df.loc[:, preview_cols].head(200), width="stretch")

    @override
    def render_debug_info(self, df: pd.DataFrame) -> None:
        return None
