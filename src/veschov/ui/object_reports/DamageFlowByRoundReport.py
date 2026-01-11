from __future__ import annotations

from typing import Optional, override

import pandas as pd
import plotly.express as px
import streamlit as st

from veschov.ui.components.combat_log_header import render_combat_log_header, apply_combat_lens
from veschov.ui.damage_flow_by_round import _coerce_pool_damage, _normalize_round, _build_damage_mask, \
    _resolve_hover_columns, _build_long_df, SEGMENT_COLORS, SEGMENT_ORDER, OPTIONAL_PREVIEW_COLUMNS
from veschov.ui.object_reports.RoundOrShotsReport import RoundOrShotsReport
from veschov.ui.view_by import prepare_round_view


class DamageFlowByRoundReport(RoundOrShotsReport):

    def get_x_axis_text(self) -> Optional[str]:
        return "Shot or Round Number"

    def get_y_axis_text(self) -> Optional[str]:
        return "Damage"

    def get_title_text(self) -> Optional[str]:
        return "Damage Flow by Shot or Round Number"

    def get_under_title_text(self) -> Optional[str]:
        return """Damage Flow by Round highlights what damage actually landed on shields and hull after all 
        mitigation (iso-defense, Apex, and other reductions). It is not the same as “Total Damage” 
        in the log."""

    def get_under_chart_text(self) -> Optional[str]:
        return  """This chart stacks disjoint components of a hit. 
        Blue/red are damage taken (shield/hull). Greens are damage prevented by mitigation 
        (normal/isolytic) and Apex Barrier."""

    def get_log_title(self) -> str:
        return "Damage Flow by Round"

    def get_log_description(self) -> str:
        return "Upload a battle log to visualize post-mitigation damage applied to shields and hull."

    def get_lens_key(self) -> str:
        return "actual_damage"

    def get_derived_dataframes(self, df: pd.DataFrame, lens) -> Optional[list[pd.DataFrame]]:
        display_df = df.copy()
        display_df.attrs = {}

        required_columns = ("event_type", "round", "shield_damage", "hull_damage")
        missing_columns = [col for col in required_columns if col not in display_df.columns]
        if missing_columns:
            st.error(f"Missing required columns: {', '.join(missing_columns)}")
            return None

        try:
            display_df = _coerce_pool_damage(display_df)
            display_df = _normalize_round(display_df)
            damage_mask = _build_damage_mask(display_df)
        except KeyError as exc:
            st.error(f"Missing required column: {exc.args[0]}")
            return None

        shot_df = display_df.loc[damage_mask].copy()
        shot_df = shot_df[shot_df["shot_index"].notna()]
        shot_df = apply_combat_lens(shot_df, lens)

        if shot_df.empty:
            st.warning("No matching damage events found for this selection.")
            return None

        self.view_by = self._resolve_view_by()
        hover_columns = _resolve_hover_columns(shot_df)

        if self.view_by == "Round":
            round_df = prepare_round_view(shot_df)
            if round_df is None:
                return None
            long_df = _build_long_df(round_df, hover_columns, include_shot_index=False)
            long_df = (
                long_df.groupby(["round", "segment"], dropna=False)["amount"]
                .sum()
                .reset_index()
            )
            self.x_axis = "round"
            self.hover_columns = [column for column in hover_columns if column in long_df.columns]
        else:
            long_df = _build_long_df(shot_df, hover_columns, include_shot_index=True)
            self.hover_columns = [column for column in hover_columns if column in long_df.columns]
            long_df["accounted_total"] = long_df.groupby("shot_index")["amount"].transform(
                "sum"
            )
            self.x_axis = "shot_index"
        return [long_df, shot_df]

    def display_plots(self, dfs: list[pd.DataFrame] ) -> None:
        long_df = dfs[0]
        fig = px.area(
            long_df,
            x=self.x_axis,
            y="amount",
            color="segment",
            # facet_col="round",
            # facet_col_wrap=4,
            color_discrete_map=SEGMENT_COLORS,
            category_orders={"segment": SEGMENT_ORDER},
            title=self.get_title_text(),
            hover_data=self.hover_columns,
        )
        max_value = long_df[self.x_axis].max()
        if pd.notna(max_value):
            fig.update_xaxes(range=[1, int(max_value)])
        st.plotly_chart(fig, width="stretch")

    def display_tables(self, dfs: list[pd.DataFrame]) -> None:
        long_df = dfs[0]
        shot_df = dfs[1]

        show_table = st.checkbox("Show raw table", value=False)
        if show_table:
            st.caption("Raw rows include per-shot pools and mitigation columns from the combat log.")
            if self.view_by == "Round":
                summary = (
                    long_df.pivot_table(
                        index="round",
                        columns="segment",
                        values="amount",
                        aggfunc="sum",
                        fill_value=0,
                    )
                    .reset_index()
                    .rename_axis(None, axis=1)
                )
                st.dataframe(summary, width="stretch")
            else:
                preview_cols = [
                    "shot_index",
                    "round",
                    "shield_damage",
                    "hull_damage",
                    "mitigated_normal",
                    "mitigated_iso",
                    "mitigated_apex",
                ]
                preview_cols.extend(
                    col for col in OPTIONAL_PREVIEW_COLUMNS if col in shot_df.columns
                )
                preview_cols = list(dict.fromkeys(preview_cols))
                st.dataframe(shot_df.loc[:, preview_cols], width="stretch")

    @override
    def get_debug_info(self, df: pd.DataFrame) -> None:
        return None
