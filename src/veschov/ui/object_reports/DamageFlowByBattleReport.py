from __future__ import annotations

import logging
from typing import Optional, override

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from veschov.transforms.columns import get_series
from veschov.ui.object_reports.AttackerAndTargetReport import AttackerAndTargetReport
from veschov.utils.series import coerce_numeric

logger = logging.getLogger(__name__)


class DamageFlowByBattleReport(AttackerAndTargetReport):
    """Render the damage flow Sankey report for an entire battle."""

    def __init__(self) -> None:
        super().__init__()
        self.battle_filename = "Session battle data"
        self.nodes: list[str] = []
        self.edges: list[tuple[str, str, float]] = []
        self.mismatch_ratio = 0.0
        self.mismatch = 0.0
        self.apex_mitigated_total = 0.0
        self.apex_absorbed_derived = 0.0
        self.debug_row_counts: dict[str, int] = {}

    def get_x_axis_text(self) -> Optional[str]:
        return None

    def get_y_axis_text(self) -> Optional[str]:
        return None

    def get_title_text(self) -> Optional[str]:
        return "Damage Flow by Battle"

    def get_under_title_text(self) -> Optional[str]:
        return (
            "Damage Flow by Battle aggregates the entire combat log to show how "
            "isolytic/regular damage moves through mitigation and Apex into shield vs hull."
        )

    def get_under_chart_text(self) -> Optional[str]:
        return "All links represent summed totals across the selected battle log."

    def get_log_title(self) -> str:
        return "Damage Flow by Battle"

    def get_log_description(self) -> str:
        return "Upload a battle log to visualize damage flow (iso/base × crit/non-crit)."

    def get_lens_key(self) -> str:
        return "damage_flow_sankey"

    def get_derived_dataframes(self, df: pd.DataFrame, lens) -> Optional[list[pd.DataFrame]]:
        display_df = df.copy()
        display_df.attrs = {}

        required_columns = (
            "event_type",
            "is_crit",
            "shield_damage",
            "hull_damage",
            "total_iso",
            "total_normal",
            "mitigated_iso",
            "mitigated_normal",
            "mitigated_apex",
        )
        missing_columns = [col for col in required_columns if col not in display_df.columns]
        if missing_columns:
            st.error(f"Missing required columns: {', '.join(missing_columns)}")
            return None

        try:
            damage_mask = self._build_damage_mask(display_df)
        except KeyError as exc:
            st.error(f"Missing required column: {exc.args[0]}")
            return None

        shot_df = display_df.loc[damage_mask].copy()
        shot_df = self.apply_combat_lens(shot_df, lens)

        if shot_df.empty:
            st.warning("No matching damage events found for this selection.")
            return None

        self.battle_filename = st.session_state.get("battle_filename") or "Session battle data"

        is_crit = shot_df["is_crit"].fillna(False).astype(bool)

        total_iso = coerce_numeric(shot_df["total_iso"]).fillna(0)
        total_normal = coerce_numeric(shot_df["total_normal"]).fillna(0)
        mitigated_iso = coerce_numeric(shot_df["mitigated_iso"]).fillna(0)
        mitigated_normal = coerce_numeric(shot_df["mitigated_normal"]).fillna(0)
        mitigated_apex = coerce_numeric(shot_df["mitigated_apex"]).fillna(0)
        shield_damage = coerce_numeric(shot_df["shield_damage"]).fillna(0)
        hull_damage = coerce_numeric(shot_df["hull_damage"]).fillna(0)

        sum_shield_damage = float(shield_damage.sum())
        sum_hull_damage = float(hull_damage.sum())
        sum_applied_damage = sum_shield_damage + sum_hull_damage

        iso_noncrit_raw = float(total_iso.where(~is_crit, 0).sum())
        iso_crit_raw = float(total_iso.where(is_crit, 0).sum())
        reg_noncrit_raw = float(total_normal.where(~is_crit, 0).sum())
        reg_crit_raw = float(total_normal.where(is_crit, 0).sum())

        iso_raw_total = iso_noncrit_raw + iso_crit_raw
        reg_raw_total = reg_noncrit_raw + reg_crit_raw

        iso_mitigated_total = float(mitigated_iso.sum())
        reg_mitigated_total = float(mitigated_normal.sum())
        apex_mitigated_total = float(mitigated_apex.sum())

        iso_remain_total = iso_raw_total - iso_mitigated_total
        reg_remain_total = reg_raw_total - reg_mitigated_total

        pre_apex_total = iso_remain_total + reg_remain_total

        post_apex_series = coerce_numeric(get_series(shot_df, "damage_after_apex"))
        if post_apex_series.notna().any():
            post_apex_total = float(post_apex_series.fillna(0).sum())
        else:
            post_apex_total = sum_applied_damage

        apex_absorbed_derived = pre_apex_total - post_apex_total

        mismatch = abs(apex_absorbed_derived - apex_mitigated_total)
        mismatch_base = abs(pre_apex_total)
        mismatch_ratio = mismatch / mismatch_base if mismatch_base > 0 else 0

        if mismatch_ratio > 0.01:
            st.warning(
                "Apex mitigation mismatch exceeds 1% of pre-Apex total. "
                "Check the totals and diagnostics below."
            )

        share_iso = iso_remain_total / pre_apex_total if pre_apex_total > 0 else 0.0
        share_reg = reg_remain_total / pre_apex_total if pre_apex_total > 0 else 0.0

        apex_from_iso = apex_mitigated_total * share_iso
        apex_from_reg = apex_mitigated_total * share_reg

        shield_from_iso = sum_shield_damage * share_iso
        shield_from_reg = sum_shield_damage * share_reg
        hull_from_iso = sum_hull_damage * share_iso
        hull_from_reg = sum_hull_damage * share_reg

        self.nodes = [
            "Iso Non-Crit",
            "Iso Crit",
            "Regular Non-Crit",
            "Regular Crit",
            "Raw Iso",
            "Raw Regular",
            "Iso Mitigation",
            "Regular Mitigation",
            "Apex Mitigation",
            "Shield Dmg",
            "Hull Dmg",
        ]
        self.edges = [
            ("Iso Non-Crit", "Raw Iso", iso_noncrit_raw),
            ("Iso Crit", "Raw Iso", iso_crit_raw),
            ("Regular Non-Crit", "Raw Regular", reg_noncrit_raw),
            ("Regular Crit", "Raw Regular", reg_crit_raw),
            ("Raw Iso", "Iso Mitigation", iso_mitigated_total),
            ("Raw Regular", "Regular Mitigation", reg_mitigated_total),
            ("Raw Iso", "Apex Mitigation", apex_from_iso),
            ("Raw Regular", "Apex Mitigation", apex_from_reg),
            ("Raw Iso", "Shield Dmg", shield_from_iso),
            ("Raw Regular", "Shield Dmg", shield_from_reg),
            ("Raw Iso", "Hull Dmg", hull_from_iso),
            ("Raw Regular", "Hull Dmg", hull_from_reg),
        ]

        totals = {
            "iso_raw_total": iso_raw_total,
            "reg_raw_total": reg_raw_total,
            "iso_mitigated_total": iso_mitigated_total,
            "reg_mitigated_total": reg_mitigated_total,
            "apex_mitigated_total": apex_mitigated_total,
            "iso_remain_total": iso_remain_total,
            "reg_remain_total": reg_remain_total,
            "pre_apex_total": pre_apex_total,
            "post_apex_total": post_apex_total,
            "apex_absorbed_derived": apex_absorbed_derived,
            "sum_shield_damage": sum_shield_damage,
            "sum_hull_damage": sum_hull_damage,
            "sum_applied_damage": sum_applied_damage,
            "apex_mismatch_ratio": mismatch_ratio,
        }
        totals_df = pd.DataFrame(
            {
                "metric": totals.keys(),
                "value": totals.values(),
            }
        )

        self.mismatch_ratio = mismatch_ratio
        self.mismatch = mismatch
        self.apex_mitigated_total = apex_mitigated_total
        self.apex_absorbed_derived = apex_absorbed_derived
        self.debug_row_counts = {
            "rows_total": int(len(display_df)),
            "rows_damage_events": int(len(shot_df)),
            "rows_filtered": int(len(display_df) - len(shot_df)),
        }
        debug_df = pd.DataFrame(
            {
                "metric": self.debug_row_counts.keys(),
                "value": self.debug_row_counts.values(),
            }
        )

        return [shot_df, totals_df, debug_df]

    def display_plots(self, dfs: list[pd.DataFrame]) -> None:
        st.markdown(
            """
            <style>
            /* Plotly Sankey label shadow/halo can look blurry in Streamlit on desktop */
            .js-plotly-plot .sankey text {
                text-shadow: none !important;
            }
            </style>
            """,
            unsafe_allow_html=True,
        )
        node_index = {label: idx for idx, label in enumerate(self.nodes)}

        sources = []
        targets = []
        values = []
        for source, target, value in self.edges:
            if value <= 0:
                continue
            sources.append(node_index[source])
            targets.append(node_index[target])
            values.append(value)

        fig = go.Figure(
            data=[
                go.Sankey(
                    node={"label": self.nodes, "pad": 18, "thickness": 16},
                    link={"source": sources, "target": targets, "value": values},
                )
            ]
        )
        fig.update_layout(title=f"Damage Flow by Battle — {self.battle_filename}")
        st.plotly_chart(fig, width="stretch")

    def display_tables(self, dfs: list[pd.DataFrame]) -> None:
        self.render_debug_info(dfs)

    def render_debug_info(self, dfs: list[pd.DataFrame]) -> None:
        totals_df = dfs[1]
        debug_df = dfs[2]
        with st.expander("Totals & Checks", expanded=True):
            st.caption("Metrics reconcile raw totals, mitigation, and applied damage for sanity checks.")
            st.dataframe(totals_df, width="stretch")
            st.write(
                {
                    "apex_mismatch": self.mismatch,
                    "apex_mitigated_total": self.apex_mitigated_total,
                    "apex_absorbed_derived": self.apex_absorbed_derived,
                }
            )
            st.caption("Row counts for filtering diagnostics.")
            st.dataframe(debug_df, width="stretch")

        st.caption(f"Diagnostics: {self.debug_row_counts}")

        if self.mismatch_ratio > 0.01:
            st.info("Consider reviewing the raw rows to confirm Apex accounting.")

        st.caption(
            "Note: Apex mitigation, shield, and hull are attributed to iso vs regular in proportion "
            "to their pre-Apex remainder shares."
        )

    @override
    def get_debug_info(self, df: pd.DataFrame) -> None:
        return None

    @staticmethod
    def _build_damage_mask(df: pd.DataFrame) -> pd.Series:
        if "event_type" not in df.columns:
            raise KeyError("event_type")
        typ = df["event_type"].astype(str).str.strip().str.lower()
        total_normal = coerce_numeric(get_series(df, "total_normal"))
        total_iso = coerce_numeric(get_series(df, "total_iso"))
        shield_damage = coerce_numeric(get_series(df, "shield_damage"))
        hull_damage = coerce_numeric(get_series(df, "hull_damage"))
        totals_positive = (total_normal > 0) | (total_iso > 0)
        totals_missing = total_normal.isna() & total_iso.isna()
        pools_positive = (shield_damage > 0) | (hull_damage > 0)
        return (typ == "attack") & (totals_positive | (totals_missing & pools_positive))
