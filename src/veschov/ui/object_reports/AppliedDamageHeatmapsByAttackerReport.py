from __future__ import annotations

import logging
from typing import Optional, override

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
        selected_attackers, selected_targets = self._resolve_selected_specs_from_state(
            resolved_session_info,
        )
        self.selected_attackers = list(selected_attackers)
        self.selected_targets = list(selected_targets)
        resolved_session_info = (
            resolved_session_info
            if isinstance(resolved_session_info, SessionInfo)
            else None
        )
        self.outcome_lookup = self._build_outcome_lookup(resolved_session_info, df)

    def _format_applied_damage_value(self, value: object) -> str:
        if value is None or pd.isna(value):
            return "—"
        numeric_value = float(value)
        if self.number_format == "Human" and abs(numeric_value) >= 1_000_000:
            return humanize.intword(numeric_value, format="%.1f")
        if numeric_value.is_integer():
            return f"{int(numeric_value):,}"
        return f"{numeric_value:,}"
