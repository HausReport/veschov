"""Shared header helpers for combat-log-based reports."""

from __future__ import annotations

import hashlib
import logging
from typing import Callable, Iterable

import pandas as pd
import streamlit as st

from veschov.io.SessionInfo import SessionInfo

logger = logging.getLogger(__name__)

DEFAULT_UPLOAD_TYPES: Iterable[str] = ("tsv", "csv", "txt")


def _hydrate_battle_metadata(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure battle metadata dataframes are present in attrs/session state."""
    players_df = df.attrs.get("players_df")
    stored_players_df = st.session_state.get("players_df")
    if isinstance(players_df, pd.DataFrame) and not players_df.empty:
        if not isinstance(stored_players_df, pd.DataFrame) or stored_players_df.empty:
            st.session_state["players_df"] = players_df
    elif isinstance(stored_players_df, pd.DataFrame) and not stored_players_df.empty:
        df.attrs["players_df"] = stored_players_df
        logger.debug("Restored players_df from session state into combat df attrs.")
    else:
        logger.warning("players_df missing or empty in both combat df attrs and session state.")

    fleets_df = df.attrs.get("fleets_df")
    stored_fleets_df = st.session_state.get("fleets_df")
    if isinstance(fleets_df, pd.DataFrame) and not fleets_df.empty:
        if not isinstance(stored_fleets_df, pd.DataFrame) or stored_fleets_df.empty:
            st.session_state["fleets_df"] = fleets_df
    elif isinstance(stored_fleets_df, pd.DataFrame) and not stored_fleets_df.empty:
        df.attrs["fleets_df"] = stored_fleets_df
        logger.debug("Restored fleets_df from session state into combat df attrs.")
    return df


def render_sidebar_combat_log_upload(
        title: str,
        description: str,
        *,
        parser: Callable[[bytes, str], pd.DataFrame],
        uploader_label: str = "Battle log file",
        uploader_types: Iterable[str] = DEFAULT_UPLOAD_TYPES,
        uploader_help: str = "Upload a battle log export to compute Apex Barrier per shot.",
) -> pd.DataFrame | None:
    """Render a shared sidebar upload widget and hydrate battle session data."""
    # st.subheader(title)
    # st.caption(description)
    uploaded = st.sidebar.file_uploader(
        uploader_label,
        type=list(uploader_types),
        help=uploader_help,
    )
    if uploaded is None:
        battle_df = st.session_state.get("battle_df")
        if isinstance(battle_df, pd.DataFrame):
            return _hydrate_battle_metadata(battle_df)
        return battle_df

    data = uploaded.getvalue()
    upload_hash = hashlib.md5(data).hexdigest()
    if st.session_state.get("battle_upload_hash") == upload_hash:
        battle_df = st.session_state.get("battle_df")
        if isinstance(battle_df, pd.DataFrame):
            return _hydrate_battle_metadata(battle_df)
        return battle_df

    try:
        df = parser(data, uploaded.name)
    except NotImplementedError:
        st.warning("Parser not wired yet. Implement parse_battle_log to enable this view.")
        return None
    except Exception as exc:  # pragma: no cover - visual feedback
        st.exception(exc)
        return None

    st.session_state["battle_df"] = df
    st.session_state["battle_filename"] = uploaded.name
    st.session_state["battle_upload_hash"] = upload_hash
    st.session_state["players_df"] = df.attrs.get("players_df")
    st.session_state["fleets_df"] = df.attrs.get("fleets_df")
    st.session_state["session_info"] = SessionInfo(df)
    # st.rerun()
    return _hydrate_battle_metadata(df)
