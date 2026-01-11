"""Streamlit UI for raw damage analysis."""

from __future__ import annotations

import logging
from typing import Optional, override

import pandas as pd
import plotly.express as px
import streamlit as st

from veschov.ui.components.combat_log_header import apply_combat_lens, render_combat_log_header
from veschov.ui.object_reports.RoundOrShotsReport import RoundOrShotsReport
from veschov.ui.view_by import prepare_round_view
from veschov.utils.series import coerce_numeric

logger = logging.getLogger(__name__)


class RawDamageReport(RoundOrShotsReport):
    """Render the raw damage (pre-mitigation) report."""

    VIEW_BY_KEY = "raw_damage_view_by"

    def __init__(self) -> None:
        super().__init__()
        self.battle_filename = "Session battle data"
        self.x_axis = "shot_index"

    def get_x_axis_text(self) -> Optional[str]:
        return "Shot or Round Number"

    def get_y_axis_text(self) -> Optional[str]:
        return "Raw Damage"

    def get_title_text(self) -> Optional[str]:
        return "Raw Damage by Type"

    def get_under_title_text(self) -> Optional[str]:
        return (
            "Raw Damage by Type shows pre-mitigation totals (Normal vs Isolytic), "
            "split by whether the hit was critical."
        )

    def get_under_chart_text(self) -> Optional[str]:
        return (
            "Stacks show how much raw damage was logged for each damage type and crit state."
        )

    def get_log_title(self) -> str:
        return "Raw Damage by Type"

    def get_log_description(self) -> str:
        return "Upload a battle log to visualize raw damage (normal vs isolytic, crit vs non-crit)."

    def get_lens_key(self) -> str:
        return "raw_damage"

    def get_derived_dataframes(self, df: pd.DataFrame, lens) -> Optional[list[pd.DataFrame]]:
        display_df = df.copy()
        display_df.attrs = {}

        required_columns = ("event_type", "is_crit", "total_normal", "total_iso")
        missing_columns = [col for col in required_columns if col not in display_df.columns]
        if missing_columns:
            st.error(f"Missing required columns: {', '.join(missing_columns)}")
            return None

        try:
            typ = display_df["event_type"].astype(str).str.strip().str.lower()
            total_normal = coerce_numeric(display_df["total_normal"]).fillna(0)
            total_iso = coerce_numeric(display_df["total_iso"]).fillna(0)
        except KeyError as exc:
            st.error(f"Missing required column: {exc.args[0]}")
            return None

        damage_mask = (typ == "attack") & ((total_normal > 0) | (total_iso > 0))
        shot_df = display_df.loc[damage_mask].copy()
        shot_df["total_normal"] = total_normal.loc[damage_mask].fillna(0)
        shot_df["total_iso"] = total_iso.loc[damage_mask].fillna(0)

        if "battle_event" in shot_df.columns:
            shot_df = shot_df.sort_values("battle_event", kind="stable")

        shot_df = apply_combat_lens(shot_df, lens)

        if shot_df.empty:
            st.warning("No matching attack events found for this selection.")
            return None

        self.view_by = self._resolve_view_by()
        self.battle_filename = st.session_state.get("battle_filename") or "Session battle data"

        if self.view_by == "Round":
            round_df = prepare_round_view(shot_df)
            if round_df is None:
                return None
            grouped = (
                round_df.groupby(["round", "is_crit"], dropna=False)[
                    ["total_normal", "total_iso"]
                ]
                .sum()
                .reset_index()
            )
            pivot = grouped.pivot_table(
                index="round",
                columns="is_crit",
                values=["total_normal", "total_iso"],
                aggfunc="sum",
                fill_value=0,
            ).sort_index()

            def _metric(metric: str, crit_value: bool) -> pd.Series:
                if (metric, crit_value) in pivot.columns:
                    return pivot[(metric, crit_value)]
                return pd.Series(0, index=pivot.index, dtype="float")

            series_df = pd.DataFrame(
                {
                    "round": pivot.index.astype(int),
                    "Non-crit Normal Damage": _metric("total_normal", False),
                    "Crit Normal Damage": _metric("total_normal", True),
                    "Non-crit Isolytic Damage": _metric("total_iso", False),
                    "Crit Isolytic Damage": _metric("total_iso", True),
                }
            )
            self.x_axis = "round"
        else:
            shot_index = pd.Series(
                range(1, len(shot_df) + 1),
                index=shot_df.index,
                dtype="Int64",
            )
            shot_df = shot_df.assign(shot_index=shot_index)
            crit = shot_df["is_crit"].fillna(False).astype(bool)
            series_df = pd.DataFrame(
                {
                    "shot_index": shot_df["shot_index"],
                    "Non-crit Normal Damage": shot_df["total_normal"].where(~crit, 0),
                    "Crit Normal Damage": shot_df["total_normal"].where(crit, 0),
                    "Non-crit Isolytic Damage": shot_df["total_iso"].where(~crit, 0),
                    "Crit Isolytic Damage": shot_df["total_iso"].where(crit, 0),
                }
            )
            self.x_axis = "shot_index"

        long_df = series_df.melt(
            id_vars=self.x_axis,
            var_name="series_name",
            value_name="amount",
        )
        long_df["amount"] = coerce_numeric(long_df["amount"]).fillna(0)
        long_df[self.x_axis] = coerce_numeric(long_df[self.x_axis]).astype(int)
        return [long_df, series_df, shot_df]

    def display_plots(self, dfs: list[pd.DataFrame]) -> None:
        long_df = dfs[0]
        fig = px.area(
            long_df,
            x=self.x_axis,
            y="amount",
            color="series_name",
            title=f"{self.get_title_text()} — {self.battle_filename}",
            category_orders={
                "series_name": [
                    "Non-crit Normal Damage",
                    "Crit Normal Damage",
                    "Non-crit Isolytic Damage",
                    "Crit Isolytic Damage",
                ]
            },
        )
        max_value = long_df[self.x_axis].max()
        if pd.notna(max_value):
            fig.update_xaxes(range=[1, int(max_value)])
        st.plotly_chart(fig, width="stretch")

    def display_tables(self, dfs: list[pd.DataFrame]) -> None:
        series_df = dfs[1]
        shot_df = dfs[2]
        show_table = st.checkbox("Show raw table", value=False)
        if show_table:
            st.caption("Raw rows include per-shot totals before mitigation.")
            if self.view_by == "Round":
                st.dataframe(series_df, width="stretch")
            else:
                preview_cols = ["shot_index", "event_type", "total_normal", "total_iso", "is_crit"]
                if "battle_event" in shot_df.columns:
                    preview_cols.append("battle_event")
                if "round" in shot_df.columns:
                    preview_cols.append("round")
                st.dataframe(shot_df.loc[:, preview_cols], width="stretch")

    @override
    def render_debug_info(self, df: pd.DataFrame) -> None:
        return None


