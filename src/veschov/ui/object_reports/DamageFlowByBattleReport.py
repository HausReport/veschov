from __future__ import annotations

import logging
from typing import Optional, override

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from veschov.io.SessionInfo import SessionInfo, ShipSpecifier
from veschov.transforms.columns import ATTACKER_COLUMN_CANDIDATES, get_series, resolve_column
from veschov.ui.object_reports.AbstractReport import AbstractReport
from veschov.ui.object_reports.AttackerAndTargetReport import (
    AttackerAndTargetReport,
    SerializedShipSpec,
)
from veschov.utils.series import coerce_numeric

logger = logging.getLogger(__name__)


class DamageFlowByBattleReport(AttackerAndTargetReport):
    """Render the damage flow Sankey report for an entire battle."""
    under_title_text = "Damage Flow by Battle aggregates the entire combat log to show how "
    "isolytic/regular damage moves through mitigation and Apex into shield vs hull."
    under_chart_text = "All links represent summed totals across the selected battle log."
    title_text = "Damage Flow by Battle"
    lens_key = f"sankey_{AbstractReport.key_suffix}"

    ATTACKER_NODE_COLOR = "#66b3b3"
    ATTACKER_LABEL_COLOR = "#2a9d8f"

    def __init__(self) -> None:
        super().__init__()
        self.battle_filename = "Session battle data"
        self.nodes: list[str] = []
        self.edges: list[tuple[str, str, float]] = []
        self.attacker_labels: list[str] = []
        self.mismatch_ratio = 0.0
        self.mismatch = 0.0
        self.apex_mitigated_total = 0.0
        self.apex_absorbed_derived = 0.0
        self.debug_row_counts: dict[str, int] = {}

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
        attacker_totals = self._build_attacker_totals(
            shot_df,
            lens,
            is_crit,
            total_iso,
            total_normal,
        )
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

        base_nodes = [
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
        self.nodes = self.attacker_labels + base_nodes if self.attacker_labels else base_nodes
        self.edges = []
        if self.attacker_labels:
            for attacker_label in self.attacker_labels:
                attacker_values = attacker_totals.get(attacker_label, {})
                self.edges.extend(
                    [
                        (
                            attacker_label,
                            "Iso Non-Crit",
                            attacker_values.get("iso_noncrit", 0.0),
                        ),
                        (
                            attacker_label,
                            "Iso Crit",
                            attacker_values.get("iso_crit", 0.0),
                        ),
                        (
                            attacker_label,
                            "Regular Non-Crit",
                            attacker_values.get("reg_noncrit", 0.0),
                        ),
                        (
                            attacker_label,
                            "Regular Crit",
                            attacker_values.get("reg_crit", 0.0),
                        ),
                    ]
                )
        self.edges.extend(
            [
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
        )

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

    def _build_attacker_totals(
            self,
            shot_df: pd.DataFrame,
            lens,
            is_crit: pd.Series,
            total_iso: pd.Series,
            total_normal: pd.Series,
    ) -> dict[str, dict[str, float]]:
        """Build per-attacker damage totals for the sankey entry nodes."""
        self.attacker_labels = []
        attacker_totals: dict[str, dict[str, float]] = {}

        session_info = st.session_state.get("session_info")
        selected_attackers = (
            list(lens.attacker_specs)
            if lens is not None and lens.attacker_specs
            else self._resolve_selected_specs_from_state(session_info)[0]
        )
        if len(selected_attackers) <= 1:
            return attacker_totals

        attacker_column = resolve_column(shot_df, ATTACKER_COLUMN_CANDIDATES)
        if attacker_column is None:
            logger.warning("Damage flow missing attacker columns for per-attacker split.")
            st.info("Per-attacker split unavailable: missing attacker name columns.")
            return attacker_totals

        outcome_lookup = self._build_outcome_lookup(
            session_info if isinstance(session_info, SessionInfo) else None,
            shot_df,
        )
        for attacker in selected_attackers:
            if not (attacker.name or attacker.alliance or attacker.ship):
                continue
            attacker_mask = self._build_single_attacker_mask(shot_df, attacker, attacker_column)
            attacker_label = self._format_attacker_label(attacker, outcome_lookup)
            self.attacker_labels.append(attacker_label)
            attacker_totals[attacker_label] = {
                "iso_noncrit": float(total_iso.where(attacker_mask & ~is_crit, 0).sum()),
                "iso_crit": float(total_iso.where(attacker_mask & is_crit, 0).sum()),
                "reg_noncrit": float(total_normal.where(attacker_mask & ~is_crit, 0).sum()),
                "reg_crit": float(total_normal.where(attacker_mask & is_crit, 0).sum()),
            }
        return attacker_totals

    def _format_attacker_label(
            self,
            spec: ShipSpecifier,
            outcome_lookup: dict[SerializedShipSpec, object] | None = None,
    ) -> str:
        """Format attacker labels without alliance tags."""
        return spec.format_label_with_outcome_lookup(
            outcome_lookup,
            include_alliance=False,
        )

    @staticmethod
    def _build_single_attacker_mask(
            df: pd.DataFrame,
            spec: ShipSpecifier,
            attacker_column: str,
    ) -> pd.Series:
        """Match attacker rows by name, alliance, and ship when available."""
        spec_mask = pd.Series(True, index=df.index)
        if spec.name:
            spec_mask &= df[attacker_column] == spec.name
        if "attacker_alliance" in df.columns and spec.alliance:
            spec_mask &= df["attacker_alliance"] == spec.alliance
        if "attacker_ship" in df.columns and spec.ship:
            spec_mask &= df["attacker_ship"] == spec.ship
        return spec_mask

    def _build_node_layout(self) -> dict[str, list[float]]:
        attacker_count = len(self.attacker_labels)
        category_nodes = ["Iso Non-Crit", "Iso Crit", "Regular Non-Crit", "Regular Crit"]

        x: list[float] = []
        y: list[float | None] = []  # allow None for “let plotly decide”

        attacker_i = 0

        for label in self.nodes:
            if label in self.attacker_labels:
                x.append(0.0)
                if attacker_count <= 1:
                    y.append(0.5)
                else:
                    y.append(attacker_i / (attacker_count - 1))
                attacker_i += 1

            elif label in category_nodes:
                x.append(0.28)
                y.append(None)  # <- key change

            elif label in ("Raw Iso", "Raw Regular"):
                x.append(0.48)
                y.append(None)

            elif label in ("Iso Mitigation", "Regular Mitigation", "Apex Mitigation"):
                x.append(0.68)
                y.append(None)

            else:
                x.append(0.88)
                y.append(None)

        return {"x": x, "y": y}

    def _build_node_colors(self) -> list[str]:
        """Assign distinct colors to base nodes and a shared color to attackers."""
        base_colors = {
            "Iso Non-Crit": "#a6cee3",
            "Iso Crit": "#1f78b4",
            "Regular Non-Crit": "#b2df8a",
            "Regular Crit": "#33a02c",
            "Raw Iso": "#6baed6",
            "Raw Regular": "#74c476",
            "Iso Mitigation": "#9ecae1",
            "Regular Mitigation": "#a1d99b",
            "Apex Mitigation": "#41ab5d",
            "Shield Dmg": "#3182bd",
            "Hull Dmg": "#de2d26",
        }
        colors: list[str] = []
        for label in self.nodes:
            if label in self.attacker_labels:
                colors.append(self.ATTACKER_NODE_COLOR)
            else:
                colors.append(base_colors.get(label, "#c7c7c7"))
        return colors

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

        node_config: dict[str, object] = {
            "label": self.nodes,
            "pad": 36,
            "thickness": 25,
            "color": self._build_node_colors(),
        }
        if self.attacker_labels:
            node_config.update(self._build_node_layout())

        attacker_count = max(1, len(self.attacker_labels))
        figure_height = 600 + ((attacker_count - 1) * 50)

        text_color_dark = "rgba(245,245,245,0.95)"
        text_color_light = "rgba(20,20,20,0.90)"
        # link_color = text_color_light
        fig = go.Figure(
            data=[
                go.Sankey(
                    node=node_config,
                    link={"source": sources, "target": targets, "value": values},  # , "color": link_color},
                    textfont={"color": text_color_light},
                    arrangement="fixed"
                )
            ]
        )
        fig.update_layout(
            title=f"Damage Flow by Battle — {self.battle_filename}",
            height=figure_height,
            font=dict(
                size=16,  # try 14–16
                # color=text_color_light,
                family="Segoe UI"
            )
        )
        fig.update_traces(
            node=dict(
                line=dict(color="rgba(0,0,0,0.65)", width=5.2),
                thickness=25,
                pad=36
            )
        )
        st.plotly_chart(fig, width="stretch")

    def render_debug_info(self, dfs: list[pd.DataFrame]) -> None:
        totals_df = dfs[1]
        debug_df = dfs[2]
        with st.expander("Totals & Checks", expanded=False):
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
