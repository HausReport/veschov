"""Report base for charts that display multiple attackers on one graph."""

from __future__ import annotations

import logging

import pandas as pd
import plotly.express as px
import streamlit as st

from veschov.io.SessionInfo import SessionInfo
from veschov.io.ShipSpecifier import ShipSpecifier
from veschov.ui.object_reports.AbstractReport import AbstractReport
from veschov.ui.object_reports.RoundOrShotsReport import RoundOrShotsReport

logger = logging.getLogger(__name__)


class MultiAttackerAndTargetReport(RoundOrShotsReport):
    """Base report with helpers for multi-attacker series charts."""
    lens_key = f"abstract_multi_attacker_{AbstractReport.key_suffix}"

    def _build_attacker_key(
            self,
            df: pd.DataFrame,
            *,
            attacker_name_column: str = "attacker_name",
            attacker_alliance_column: str = "attacker_alliance",
            attacker_ship_column: str = "attacker_ship",
    ) -> pd.DataFrame:
        """Build a stable attacker label column for multi-attacker charts."""
        if attacker_name_column not in df.columns:
            raise KeyError(attacker_name_column)
        session_info = st.session_state.get("session_info")
        outcome_lookup = self._build_outcome_lookup(
            session_info if isinstance(session_info, SessionInfo) else None,
            self.battle_df if isinstance(self.battle_df, pd.DataFrame) else None,
        )
        alliance_series = (
            df[attacker_alliance_column]
            if attacker_alliance_column in df.columns
            else pd.Series("", index=df.index)
        )
        ship_series = (
            df[attacker_ship_column]
            if attacker_ship_column in df.columns
            else pd.Series("", index=df.index)
        )
        if attacker_alliance_column not in df.columns:
            logger.warning(
                "Attacker alliance column missing; attacker labels omit alliance.",
            )
        if attacker_ship_column not in df.columns:
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
                df[attacker_name_column].fillna("").astype(str),
                alliance_series.fillna("").astype(str),
                ship_series.fillna("").astype(str),
            )
        ]
        return df.assign(attacker_key=pd.Series(labels, index=df.index, dtype="string"))

    def _build_attacker_series_style(
            self,
            df: pd.DataFrame,
            *,
            attacker_column: str = "attacker_key",
    ) -> dict[str, object]:
        """Return color/category settings for multi-attacker plotly traces."""
        if attacker_column not in df.columns:
            logger.warning("Attacker column %s missing; skipping trace styling.", attacker_column)
            return {}
        attackers = [
            value for value in df[attacker_column].dropna().astype(str).unique()
        ]
        if not attackers:
            return {}
        colors = px.colors.qualitative.Safe
        color_map = {
            attacker: colors[index % len(colors)]
            for index, attacker in enumerate(attackers)
        }
        return {
            "category_orders": {attacker_column: attackers},
            "color_discrete_map": color_map,
        }
