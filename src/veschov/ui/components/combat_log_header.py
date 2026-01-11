"""Shared header helpers for combat-log-based reports."""

from __future__ import annotations

import hashlib
import logging
from typing import Callable, Iterable, Set

import pandas as pd
import streamlit as st

from veschov.io.SessionInfo import SessionInfo, ShipSpecifier
from veschov.transforms.columns import ATTACKER_COLUMN_CANDIDATES, TARGET_COLUMN_CANDIDATES, resolve_column
from veschov.ui.chirality import Lens, resolve_lens
from veschov.ui.components.combat_summary import render_combat_summary

logger = logging.getLogger(__name__)

DEFAULT_UPLOAD_TYPES: Iterable[str] = ("tsv", "csv", "txt")

NUMBER_FORMAT_SESSION_KEY = "number_format"
NUMBER_FORMAT_OPTIONS: tuple[str, ...] = ("Human", "Exact")
NUMBER_FORMAT_DEFAULT = "Human"
NUMBER_FORMAT_HELP = "Choose how numbers over 999,999 are formatted."


def get_number_format() -> str:
    """Return the configured large-number formatting preference."""
    stored_value = st.session_state.get(NUMBER_FORMAT_SESSION_KEY, NUMBER_FORMAT_DEFAULT)
    if stored_value not in NUMBER_FORMAT_OPTIONS:
        stored_value = NUMBER_FORMAT_DEFAULT
    st.session_state[NUMBER_FORMAT_SESSION_KEY] = stored_value
    return stored_value

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
        return st.session_state.get("battle_df")

    data = uploaded.getvalue()
    upload_hash = hashlib.md5(data).hexdigest()
    if st.session_state.get("battle_upload_hash") == upload_hash:
        return st.session_state.get("battle_df")

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
    return df


def apply_combat_lens(
        df: pd.DataFrame,
        lens: Lens | None,
        *,
        attacker_column_candidates: Iterable[str] = ATTACKER_COLUMN_CANDIDATES,
        target_column_candidates: Iterable[str] = TARGET_COLUMN_CANDIDATES,
        include_nan_attackers: bool = False,
        include_nan_targets: bool = False,
) -> pd.DataFrame:
    """Filter combat data using the selected attacker specs and column-based targets."""
    if lens is None:
        return df

    session_info = st.session_state.get("session_info")
    filtered = df

    attacker_column = resolve_column(filtered, attacker_column_candidates)
    target_column = resolve_column(filtered, target_column_candidates)

    attacker_mask = pd.Series(True, index=filtered.index)
    attacker_specs = lens.attacker_specs
    if isinstance(session_info, SessionInfo) and attacker_specs:
        attacker_df = session_info.get_combat_df_filtered_by_attackers(attacker_specs)
        attacker_mask = filtered.index.isin(attacker_df.index)
    elif attacker_column:
        attacker_names = lens.attacker_names()
        if attacker_names:
            attacker_mask = filtered[attacker_column].isin(attacker_names)

    if include_nan_attackers and attacker_column:
        attacker_mask |= filtered[attacker_column].isna()

    filtered = filtered.loc[attacker_mask]

    if target_column:
        target_names = lens.target_names()
        if target_names:
            target_series = filtered[target_column]
            target_mask = target_series.isin(target_names)
            if include_nan_targets:
                target_mask |= target_series.isna()
            filtered = filtered.loc[target_mask]

    return filtered
