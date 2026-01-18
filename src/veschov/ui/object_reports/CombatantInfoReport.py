"""Streamlit UI for player information and cards."""

from __future__ import annotations

import logging

import pandas as pd
import streamlit as st

from veschov.io.SessionInfo import SessionInfo, ShipSpecifier
from veschov.ui.chirality import Lens
from veschov.ui.components.combat_summary import render_player_card, total_shots_by_attacker
from veschov.ui.components.number_format import get_number_format
from veschov.ui.object_reports.AttackerAndTargetReport import AttackerAndTargetReport

logger = logging.getLogger(__name__)


class CombatantInfoReport(AttackerAndTargetReport):
    """Render player cards for selected combatants."""

    def __init__(self) -> None:
        self._selected_cards: list[tuple[pd.Series, pd.Series | None]] = []
        self._selected_specs: list[ShipSpecifier] = []
        self._total_shots: dict[str, int] = {}

    def get_under_title_text(self) -> str | None:
        return (
            "Player Info shows the combat cards for each participant in the battle log, "
            "including the NPC entry when available."
        )

    def get_under_chart_text(self) -> str | None:
        return None

    def get_log_title(self) -> str:
        return "Player Info"

    def get_log_description(self) -> str:
        return "Upload a battle log to view player metadata and combat cards."

    def get_lens_key(self) -> str:
        return "player_info"

    def get_derived_dataframes(self, df: pd.DataFrame, lens: Lens | None) -> list[pd.DataFrame] | None:
        players_df = df.attrs.get("players_df")
        fleets_df = df.attrs.get("fleets_df")
        if not isinstance(players_df, pd.DataFrame):
            logger.warning("Player info report missing players_df in combat log attrs.")
            st.info("No player metadata found in this file.")
            return None
        if players_df.empty:
            logger.warning("Player info report players_df is empty.")
            st.info("Player metadata is empty in this file.")
            return None

        session_info = st.session_state.get("session_info")
        if not isinstance(session_info, SessionInfo):
            session_info = SessionInfo(df)
            st.session_state["session_info"] = session_info

        selected_specs = self._resolve_selected_specs(lens, session_info)
        if not selected_specs:
            logger.warning("Player info report has no selected combatants.")
            st.info("Select combatants to display their cards.")
            return None

        self._selected_specs = selected_specs
        self._total_shots = total_shots_by_attacker(df)
        self._selected_cards = self._resolve_selected_cards(
            players_df,
            fleets_df if isinstance(fleets_df, pd.DataFrame) else None,
            selected_specs,
        )
        if not self._selected_cards:
            logger.warning("Player info report could not match selected combatants to player rows.")
            st.warning("No matching player rows found for the selected combatants.")
            return None

        return [players_df]

    def _resolve_selected_specs(
        self,
        lens: Lens | None,
        session_info: SessionInfo | None,
    ) -> list[ShipSpecifier]:
        specs: list[ShipSpecifier] = []
        if lens is not None:
            specs.extend(lens.attacker_specs)
            specs.extend(lens.target_specs)
        if not specs:
            attackers, targets = self._resolve_selected_specs_from_state(session_info)
            specs = list(attackers) + list(targets)
        return self._dedupe_ship_specs(specs)

    def _dedupe_ship_specs(self, specs: list[ShipSpecifier]) -> list[ShipSpecifier]:
        seen: set[tuple[str, str, str]] = set()
        deduped: list[ShipSpecifier] = []
        for spec in specs:
            key = self._normalize_spec_key(spec.name, spec.alliance, spec.ship)
            if key in seen:
                continue
            seen.add(key)
            deduped.append(spec)
        return deduped

    def _resolve_selected_cards(
        self,
        players_df: pd.DataFrame,
        fleets_df: pd.DataFrame | None,
        specs: list[ShipSpecifier],
    ) -> list[tuple[pd.Series, pd.Series | None]]:
        cards: list[tuple[pd.Series, pd.Series | None]] = []
        for spec in specs:
            match = self._match_player_row(players_df, spec)
            if match is None:
                logger.warning(
                    "No player row match found for combatant %s; using fallback row.",
                    spec,
                )
                fallback_row = self._build_fallback_player_row(players_df, spec)
                cards.append((fallback_row, None))
                continue
            index, row = match
            fleet_row = None
            if isinstance(fleets_df, pd.DataFrame) and index < len(fleets_df):
                fleet_row = fleets_df.iloc[index]
            cards.append((row, fleet_row))
        return cards

    def _build_fallback_player_row(
        self,
        players_df: pd.DataFrame,
        spec: ShipSpecifier,
    ) -> pd.Series:
        """Build a minimal player metadata row for a combatant spec."""
        base_columns = list(players_df.columns) if not players_df.empty else []
        default_columns = ["Player Name", "Ship Name", "Alliance", "Player Alliance"]
        columns = list(dict.fromkeys(base_columns + default_columns))
        row_data = {column: pd.NA for column in columns}
        row_data["Player Name"] = spec.name or pd.NA
        row_data["Ship Name"] = spec.ship or pd.NA
        if "Alliance" in row_data:
            row_data["Alliance"] = spec.alliance or pd.NA
        if "Player Alliance" in row_data:
            row_data["Player Alliance"] = spec.alliance or pd.NA
        return pd.Series(row_data)

    def _match_player_row(
        self,
        players_df: pd.DataFrame,
        spec: ShipSpecifier,
    ) -> tuple[int, pd.Series] | None:
        spec_name = self._normalize_text(spec.name)
        spec_ship = self._normalize_text(spec.ship)
        spec_alliance = self._normalize_text(spec.alliance)
        if not any([spec_name, spec_ship, spec_alliance]):
            logger.warning("Empty combatant spec encountered while matching player rows.")
            return None

        best_match: tuple[int, pd.Series] | None = None
        best_score = -1
        for index, row in players_df.iterrows():
            row_name = self._normalize_text(row.get("Player Name"))
            row_ship = self._normalize_text(row.get("Ship Name"))
            row_alliance = self._resolve_player_alliance(row)

            if spec_name and row_name != spec_name:
                continue
            if spec_ship and row_ship != spec_ship:
                continue
            if spec_alliance and row_alliance and row_alliance != spec_alliance:
                continue

            score = 0
            if spec_name:
                score += 1
            if spec_ship:
                score += 1
            if spec_alliance and row_alliance == spec_alliance:
                score += 1
            if score > best_score:
                best_score = score
                best_match = (index, row)
        return best_match

    def display_plots(self, dfs: list[pd.DataFrame]) -> None:
        if not self._selected_cards:
            logger.warning("Player info report has no cards to render.")
            st.info("No combatants selected to display.")
            return

        number_format = get_number_format()
        for position, (row, fleet_row) in enumerate(self._selected_cards):
            if position:
                st.divider()
            name = self._normalize_text(row.get("Player Name"))
            render_player_card(
                row,
                number_format,
                fleet_row=fleet_row,
                total_shots=self._total_shots.get(name),
            )

    def display_tables(self, dfs: list[pd.DataFrame]) -> None:
        return None

    def render_debug_info(self, dfs: list[pd.DataFrame]) -> None:
        return None

    def get_x_axis_text(self) -> str | None:
        return None

    def get_y_axis_text(self) -> str | None:
        return None

    def get_title_text(self) -> str | None:
        return None


def render_player_info_report() -> None:
    """Render the player info report with roster-based selections."""
    report = CombatantInfoReport()
    report.render()
