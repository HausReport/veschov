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
from veschov.ui.components.actor_target_selector import render_actor_target_selector
from veschov.ui.components.combat_summary import render_combat_summary

logger = logging.getLogger(__name__)

DEFAULT_UPLOAD_TYPES: Iterable[str] = ("tsv", "csv", "txt")

def render_combat_log_upload(
    title: str,
    description: str,
    *,
    uploader_label: str = "Battle log file",
    uploader_types: Iterable[str] = DEFAULT_UPLOAD_TYPES,
    uploader_help: str = "Upload a battle log export to compute Apex Barrier per shot.",
) -> st.runtime.uploaded_file_manager.UploadedFile | None:
    """Render the shared upload widget for combat-log-driven reports."""
    st.subheader(title)
    st.caption(description)
    return st.file_uploader(
        uploader_label,
        type=list(uploader_types),
        help=uploader_help,
    )


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
    st.subheader(title)
    st.caption(description)
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
    st.rerun()
    return df


def render_combat_log_header(
    players_df: pd.DataFrame | None,
    fleets_df: pd.DataFrame | None,
    battle_df: pd.DataFrame | None,
    *,
    lens_key: str,
    number_format_label: str = "Large Number Display",
    number_format_options: Iterable[str] = ("Human", "Exact"),
    number_format_help: str = "Choose how numbers over 999,999 are formatted.",
    session_info: SessionInfo | Set[ShipSpecifier] | None = None,
) -> tuple[str, Lens | None]:
    """Render the standard header controls for combat-log reports."""
    number_format = st.selectbox(
        number_format_label,
        list(number_format_options),
        help=number_format_help,
    )

    resolved_session_info = session_info or st.session_state.get("session_info")
    if resolved_session_info is None and battle_df is not None:
        resolved_session_info = SessionInfo(battle_df)
    if resolved_session_info is not None:
        st.session_state["session_info"] = resolved_session_info

    selected_attackers, selected_targets = render_actor_target_selector(
        st.session_state.get("session_info")
    )
    lens = None
    if selected_attackers and selected_targets:
        lens = resolve_lens(lens_key, selected_attackers, selected_targets)
        if len(selected_attackers) == 1 and len(selected_targets) == 1:
            attacker_name = lens.actor_name or "Attacker"
            target_name = lens.target_name or "Target"
            st.caption(f"Lens: {lens.label} ({attacker_name} → {target_name})")
        else:
            attacker_label = "Attacker ships" if len(selected_attackers) != 1 else "Attacker ship"
            target_label = "Target ships" if len(selected_targets) != 1 else "Target ship"
            st.caption(f"Lens: {attacker_label} → {target_label}")

    render_combat_summary(players_df, fleets_df, battle_df=battle_df, number_format=number_format)
    st.divider()
    return number_format, lens


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
