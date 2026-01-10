"""Streamlit UI for player information and cards."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

import pandas as pd
import streamlit as st

from veschov.io.parser_stub import parse_battle_log
from veschov.ui.components.combat_log_header import (
    get_number_format,
    render_sidebar_combat_log_upload,
)
from veschov.ui.components.combat_summary import (
    render_player_card,
    total_shots_by_attacker,
)


def _tab_label(row: pd.Series, index: int) -> str:
    name = str(row.get("Player Name") or "").strip()
    ship = str(row.get("Ship Name") or "").strip()
    if name and ship and ship != name:
        return f"{name} — {ship}"
    if name:
        return name
    if ship:
        return ship
    return f"Player {index + 1}"


def render_player_info_report() -> None:
    """Render the player info report with tabs per player."""
    st.markdown(
        "Player Info shows the player combat cards for each participant in the battle log "
        "(excluding the NPC row)."
    )

    df = render_sidebar_combat_log_upload(
        "Player Info",
        "Upload a battle log to view player metadata and combat cards.",
        parser=parse_battle_log,
    )
    if df is None:
        st.info("No battle data loaded yet.")
        return

    players_df = df.attrs.get("players_df")
    fleets_df = df.attrs.get("fleets_df")
    number_format = get_number_format()

    if not isinstance(players_df, pd.DataFrame) or players_df.empty:
        st.info("No player metadata found in this file.")
        return

    if len(players_df) <= 1:
        st.warning(
            "No player rows were found in the metadata. The log file may be missing player rows."
        )
        return

    total_shots = total_shots_by_attacker(df)

    player_rows = players_df.iloc[:-1]
    tab_labels = [
        _tab_label(row, position)
        for position, (_, row) in enumerate(player_rows.iterrows())
    ]
    tabs = st.tabs(tab_labels)

    for position, ((index, row), tab) in enumerate(zip(player_rows.iterrows(), tabs)):
        with tab:
            fleet_row = None
            if isinstance(fleets_df, pd.DataFrame) and position < len(fleets_df):
                fleet_row = fleets_df.iloc[position]
            render_player_card(
                row,
                number_format,
                fleet_row=fleet_row,
                total_shots=total_shots.get(row.get("Player Name")),
            )
