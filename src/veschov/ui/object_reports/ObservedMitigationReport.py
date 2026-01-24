"""Streamlit UI for observed mitigation analysis."""

from __future__ import annotations

import logging
from typing import Optional, Sequence, override

import pandas as pd
import plotly.express as px
import streamlit as st

from veschov.io.SessionInfo import SessionInfo
from veschov.io.ShipSpecifier import ShipSpecifier
from veschov.ui.object_reports.RoundOrShotsReport import RoundOrShotsReport
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


class ObservedMitigationReport(RoundOrShotsReport):
    """Render observed mitigation per shot or round."""

    VIEW_BY_KEY = "observed_mitigation_view_by"

    def __init__(self) -> None:
        super().__init__()
        self.battle_filename = "Session battle data"
        self.number_format = "Human"
        self.x_axis = "shot_index"

    def get_x_axis_text(self) -> Optional[str]:
        return "Shot or Round Number"

    def get_y_axis_text(self) -> Optional[str]:
        return "Observed Mitigation (Normal Lane)"

    def get_title_text(self) -> Optional[str]:
        return "Observed Mitigation per Shot"

    def get_under_title_text(self) -> Optional[str]:
        return (
            "Shows observed normal-lane mitigation per hit using mitigated_normal / total_normal. "
            "Round view is damage-weighted across all hits in the round."
        )

    def get_under_chart_text(self) -> Optional[str]:
        return "Use the view selector to switch between shot-level values and round-level averages."

    def get_log_title(self) -> str:
        return "Observed Mitigation Analysis"

    def get_log_description(self) -> str:
        return "Upload a battle log to inspect observed normal-lane mitigation."

    def get_lens_key(self) -> str:
        return "observed_mitigation"

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

    def _build_attacker_key(self, df: pd.DataFrame) -> pd.DataFrame:
        if "attacker_name" not in df.columns:
            raise KeyError("attacker_name")
        session_info = st.session_state.get("session_info")
        outcome_lookup = self._build_outcome_lookup(
            session_info if isinstance(session_info, SessionInfo) else None,
            self.battle_df if isinstance(self.battle_df, pd.DataFrame) else None,
        )
        alliance_series = (
            df["attacker_alliance"]
            if "attacker_alliance" in df.columns
            else pd.Series("", index=df.index)
        )
        ship_series = (
            df["attacker_ship"]
            if "attacker_ship" in df.columns
            else pd.Series("", index=df.index)
        )
        if "attacker_alliance" not in df.columns:
            logger.warning("Attacker alliance column missing; attacker labels omit alliance.")
        if "attacker_ship" not in df.columns:
            logger.warning("Attacker ship column missing; attacker labels omit ship.")
        labels = [
            self._format_ship_spec_label(
                ShipSpecifier(
                    name=name or None,
                    alliance=alliance or None,
                    ship=ship or None,
                ),
                outcome_lookup,
            )
            for name, alliance, ship in zip(
                df["attacker_name"].fillna("").astype(str),
                alliance_series.fillna("").astype(str),
                ship_series.fillna("").astype(str),
            )
        ]
        return df.assign(attacker_key=pd.Series(labels, index=df.index, dtype="string"))

    @staticmethod
    def _compute_observed_mitigation(
            mitigated: pd.Series,
            total: pd.Series,
    ) -> pd.Series:
        ratio = mitigated.div(total)
        return ratio.clip(lower=0, upper=1)

    def _build_hover_data(self, df: pd.DataFrame, columns: Sequence[str]) -> dict[str, bool]:
        return {column: True for column in columns if column in df.columns}

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
        plot_df = dfs[0]
        hover_columns = (
            "round",
            "total_normal",
            "mitigated_normal",
            "sum_total",
            "sum_mitigated",
            "observed_mitigation",
            "attacker_key",
        )
        plot_args = {
            "data_frame": plot_df,
            "x": self.x_axis,
            "y": "observed_mitigation",
            "color": "attacker_key",
            "hover_data": self._build_hover_data(plot_df, hover_columns),
        }
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
            xaxis_title=self.get_x_axis_text(),
            yaxis_title=self.get_y_axis_text(),
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
