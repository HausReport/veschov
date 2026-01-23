from __future__ import annotations

from typing import Optional, override

import humanize
import pandas as pd
import plotly.express as px
import streamlit as st

from veschov.ui.damage_flow_by_round import _coerce_pool_damage, _normalize_round, _build_damage_mask, \
    _resolve_hover_columns, _build_long_df, SEGMENT_COLORS, SEGMENT_ORDER, OPTIONAL_PREVIEW_COLUMNS
from veschov.ui.object_reports.RoundOrShotsReport import RoundOrShotsReport
from veschov.ui.view_by import prepare_round_view

SEGMENT_LABELS = {
    "Hull": "Hull Damage",
    "Shield": "Shield Damage",
    "Mitigated Normal": "Mitigated by Shield/Dodge/Armor",
    "Mitigated Isolytic": "Mitigated by Isolytic Defense",
    "Mitigated Apex": "Mitigated by Apex Barrier",
}
LEGEND_TITLE = "Final Damage Destination"

HOVER_LABELS = {
    "hull_damage": "Hull Damage",
    "shield_damage": "Shield Damage",
    "mitigated_normal": "Mitigated by Shield/Dodge/Armor",
    "mitigated_iso": "Mitigated by Isolytic Defense",
    "mitigated_apex": "Mitigated by Apex Barrier",
    "battle_event": "Battle Event",
    "is_crit": "Critical Hit",
}


def _format_hover_value(value: object, number_format: str) -> str:
    """Format hover values using the configured large-number preference."""
    if pd.isna(value):
        return "—"
    if isinstance(value, bool):
        return str(value)
    numeric = pd.to_numeric(value, errors="coerce")
    if pd.notna(numeric):
        if abs(numeric) >= 1_000_000 and number_format == "Human":
            return humanize.intword(numeric, format="%.1f")
        if float(numeric).is_integer():
            return f"{int(numeric):,}"
        return f"{numeric:,}"
    return str(value)


class DamageFlowByRoundReport(RoundOrShotsReport):
    VIEW_BY_KEY = "damage_flow_by_round_view_by"

    def get_x_axis_text(self) -> Optional[str]:
        return "Shot or Round Number"

    def get_y_axis_text(self) -> Optional[str]:
        return "Damage"

    def get_title_text(self) -> Optional[str]:
        return "Damage Flow by Shot or Round Number"

    def get_under_title_text(self) -> Optional[str]:
        return """This report shows where damage 'ends up' - whether it lands on the hull, the shields, or  
        is blocked by normal mitigation (shields, dodge, and armor), by isolytic defense, or by Apex Barrier."""

    def get_under_chart_text(self) -> Optional[str]:
        return """This chart shows how total damage was distributed to the selected target(s).  The blue layer shows danage to the target's
        shield, the red layer to their hull, and the green layers represent damage absorbed by standard mitigation (shield, dodge, and armor), isolytic
        defense, and apex barrier."""

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
        shot_df = self.apply_combat_lens(shot_df, lens)

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

    def get_plot_titles(self) -> list[str]:
        kind = self._resolve_view_by().lower()
        return [f"Damage Distribution - Where did it go? (by {kind})"]

    def display_plots(self, dfs: list[pd.DataFrame]) -> None:
        long_df = dfs[0]
        number_format = self.number_format or "Human"
        plot_df = long_df.copy()
        plot_df["segment_display"] = (
            plot_df["segment"].map(SEGMENT_LABELS).fillna(plot_df["segment"])
        )
        segment_display_order = [SEGMENT_LABELS.get(segment, segment) for segment in SEGMENT_ORDER]
        segment_display_colors = {
            SEGMENT_LABELS.get(segment, segment): color
            for segment, color in SEGMENT_COLORS.items()
        }
        plot_df["amount_display"] = plot_df["amount"].apply(
            lambda value: _format_hover_value(value, number_format)
        )
        hover_display_columns: list[str] = []
        hover_display_labels: list[str] = []
        for column in self.hover_columns:
            display_column = f"{column}_display"
            plot_df[display_column] = plot_df[column].apply(
                lambda value: _format_hover_value(value, number_format)
            )
            hover_display_columns.append(display_column)
            hover_display_labels.append(HOVER_LABELS.get(column, column.replace("_", " ").title()))

        custom_data_columns = ["amount_display", *hover_display_columns]
        x_label = self.get_x_axis_text() or self.x_axis.replace("_", " ").title()
        hover_lines = [
            f"{x_label}: %{{x}}",
            f"{LEGEND_TITLE}: %{{fullData.name}}",
            "Amount: %{customdata[0]}",
        ]
        for index, label in enumerate(hover_display_labels, start=1):
            hover_lines.append(f"{label}: %{{customdata[{index}]}}")
        hover_template = "<br>".join(hover_lines) + "<extra></extra>"
        fig = px.area(
            plot_df,
            x=self.x_axis,
            y="amount",
            color="segment_display",
            # facet_col="round",
            # facet_col_wrap=4,
            color_discrete_map=segment_display_colors,
            category_orders={"segment_display": segment_display_order},
            title=self.get_plot_titles()[0],
            custom_data=custom_data_columns,
            labels={"segment_display": LEGEND_TITLE},
        )
        fig.update_traces(hovertemplate=hover_template)
        fig.update_layout(legend_title_text=LEGEND_TITLE)
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
    def render_debug_info(self, df: pd.DataFrame) -> None:
        return None
