"""Streamlit UI for Apex Barrier per-shot analysis."""

from __future__ import annotations

import logging
from typing import Optional, override

import humanize
import pandas as pd
import plotly.express as px
import streamlit as st

from veschov.ui.object_reports.RoundOrShotsReport import RoundOrShotsReport
from veschov.ui.view_by import prepare_round_view
from veschov.utils.series import coerce_numeric

logger = logging.getLogger(__name__)

OPTIONAL_PREVIEW_COLUMNS = (
    "round",
    "battle_event",
    "is_crit",
    "Ship",
    "Weapon",
)


def _format_large_number(value: object, number_format: str) -> str:
    if pd.isna(value):
        return "—"
    numeric = pd.to_numeric(value, errors="coerce")
    if pd.isna(numeric):
        return str(value)
    if abs(numeric) >= 1_000_000:
        if number_format == "Human":
            return humanize.intword(numeric)
        return f"{numeric:,.0f}"
    if float(numeric).is_integer():
        return f"{int(numeric)}"
    return str(value)


class ApexBarrierReport(RoundOrShotsReport):
    """Render the Apex Barrier report."""

    VIEW_BY_KEY = "apex_barrier_view_by"

    def __init__(self) -> None:
        super().__init__()
        self.battle_filename = "Session battle data"
        self.number_format = "Human"
        self.total_mitigation: float | None = None
        self.x_axis = "shot_index"

    def render_header(self, df: pd.DataFrame):
        players_df = df.attrs.get("players_df")
        fleets_df = df.attrs.get("fleets_df")
        number_format, lens = self.render_combat_log_header(
            players_df,
            fleets_df,
            df,
            lens_key=self.get_lens_key(),
        )
        self.number_format = number_format
        return lens

    def get_x_axis_text(self) -> Optional[str]:
        return "Shot or Round Number"

    def get_y_axis_text(self) -> Optional[str]:
        return "Apex Barrier Hit"

    def get_title_text(self) -> Optional[str]:
        return "Apex Barrier per Shot"

    def get_under_title_text(self) -> Optional[str]:
        return (
            "Apex Barrier values are inferred from combat log mitigation fields and "
            "represent the portion of each hit absorbed by the barrier."
        )

    def get_under_chart_text(self) -> Optional[str]:
        return "Use the view selector to switch between shot-level and round-level totals."

    def get_log_title(self) -> str:
        return "Apex Barrier Analysis"

    def get_log_description(self) -> str:
        return "Upload a battle log to estimate Apex Barrier per hit."

    def get_lens_key(self) -> str:
        return "apex_barrier"

    def _total_apex_barrier_mitigation(
        self,
        df: pd.DataFrame,
        *,
        lens,
    ) -> float | None:
        if "mitigated_apex" not in df.columns:
            return None
        mitigation_df = self.apply_combat_lens(df, lens)
        total = coerce_numeric(mitigation_df["mitigated_apex"]).sum(min_count=1)
        if pd.isna(total):
            return None
        return float(total)

    def _coerce_apex_hit(self, df: pd.DataFrame) -> pd.DataFrame:
        if "apex_barrier_hit" not in df.columns:
            raise KeyError("apex_barrier_hit")
        df = df.copy()
        df["apex_barrier_hit"] = coerce_numeric(df["apex_barrier_hit"])
        return df

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

    def get_derived_dataframes(self, df: pd.DataFrame, lens) -> Optional[list[pd.DataFrame]]:
        display_df = df.copy()
        display_df.attrs = {}

        try:
            display_df = self._coerce_apex_hit(display_df)
        except KeyError as exc:
            st.error(f"Missing required column: {exc.args[0]}")
            return None

        include_missing = st.checkbox("Include rows without Apex Barrier hit", value=False)
        if not include_missing:
            display_df = display_df[display_df["apex_barrier_hit"].notna()].copy()

        filtered_df = self.apply_combat_lens(display_df, lens)
        if filtered_df.empty:
            st.warning("No matching Apex Barrier events found for this selection.")
            return None

        self.view_by = self._resolve_view_by()
        self.battle_filename = st.session_state.get("battle_filename") or "Session battle data"
        self.total_mitigation = self._total_apex_barrier_mitigation(display_df, lens=lens)

        if self.view_by == "Round":
            round_df = prepare_round_view(filtered_df)
            if round_df is None:
                return None
            plot_df = (
                round_df.groupby("round", dropna=False)["apex_barrier_hit"]
                .sum(min_count=1)
                .reset_index()
            )
            plot_df["round"] = plot_df["round"].astype(int)
            self.x_axis = "round"
            shot_df = round_df
        else:
            shot_df = filtered_df.copy()
            if "battle_event" in shot_df.columns:
                shot_df = shot_df.sort_values("battle_event", kind="stable")
            shot_df = self._prepare_shot_index(shot_df)
            if shot_df.empty:
                st.warning("No shot index data is available for this selection.")
                return None
            plot_df = shot_df
            self.x_axis = "shot_index"

        return [plot_df, shot_df]

    def display_plots(self, dfs: list[pd.DataFrame]) -> None:
        plot_df = dfs[0]
        fig = px.line(
            plot_df,
            x=self.x_axis,
            y="apex_barrier_hit",
            markers=True,
            title=f"{self.get_title_text()} — {self.battle_filename}",
        )
        max_value = plot_df[self.x_axis].max()
        if pd.notna(max_value):
            fig.update_xaxes(range=[1, int(max_value)])
        st.plotly_chart(fig, width="stretch")

        formatted_total = (
            _format_large_number(self.total_mitigation, self.number_format)
            if self.total_mitigation is not None
            else "—"
        )
        st.markdown(f"**Total Apex Barrier Damage Mitigation:** {formatted_total}")

    def display_tables(self, dfs: list[pd.DataFrame]) -> None:
        shot_df = dfs[1]
        show_table = st.checkbox("Show raw table", value=False)
        if show_table:
            preview_cols = ["shot_index", "apex_barrier_hit"]
            if "round" in shot_df.columns:
                preview_cols.append("round")
            preview_cols.extend(col for col in OPTIONAL_PREVIEW_COLUMNS if col in shot_df.columns)
            preview_cols = list(dict.fromkeys(preview_cols))
            st.caption("Preview of shot-level Apex values and optional combat log metadata.")
            st.dataframe(shot_df.loc[:, preview_cols].head(200), width="stretch")

    @override
    def get_debug_info(self, df: pd.DataFrame) -> None:
        return None
