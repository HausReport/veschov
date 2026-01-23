from __future__ import annotations

"""Apply a combat "lens" to filter combat dataframes.

The combat lens concept is a lightweight wrapper around attacker/target selection. A
`Lens` instance (resolved via :mod:`veschov.ui.chirality`) carries:

* `attacker_specs` and `target_specs`: canonical ship specifiers chosen in the UI.
* Optional `actor_name` and `target_name`: human-friendly labels for single-ship selections.
* A display `label` describing the perspective ("Player → NPC", "NPC → Player", etc.).

This module bridges the lens with raw dataframes. It resolves which dataframe columns
contain attacker and target names, then filters rows based on the selected lens. The
filtering prefers the stronger identity match provided by `SessionInfo` when available
in `st.session_state["session_info"]`, falling back to column-name filtering when the
session info is unavailable or a spec-based selection is empty.

Usage patterns:
* Reports that already inherit the attacker/target selector can call
  :func:`apply_combat_lens` directly on derived dataframes.
* When `Lens` is ``None`` (no selection), the function returns the input unchanged.
"""

from typing import Iterable

import pandas as pd
import streamlit as st

from veschov.io.SessionInfo import SessionInfo
from veschov.ui.chirality import Lens

PROC_EVENT_TYPES = {"officer", "forbiddentechability"}


def apply_combat_lens(
        df: pd.DataFrame,
        lens: Lens | None,
        *,
        skip_target_filter_for_procs: bool = False,
) -> pd.DataFrame:
    """Filter combat data using a resolved combat lens.

    This function applies an attacker/target "lens" to a dataframe that represents
    combat events. It performs two passes:

    1. **Attacker filtering**:
       * If `st.session_state["session_info"]` is a :class:`SessionInfo` and the lens
         includes `attacker_specs`, filter by the index set of combat rows that match
         those ship specifiers (this is the most authoritative match).
       * Otherwise, leave attacker rows unfiltered.
    2. **Target filtering**:
       * If `st.session_state["session_info"]` is a :class:`SessionInfo` and the lens
         includes `target_specs`, filter by the index set of combat rows that match
         those ship specifiers.
       * Otherwise, leave target rows unfiltered.

    If a column cannot be resolved or the lens does not provide matching names/specs,
    the function leaves that dimension unfiltered.

    Args:
        df: Input dataframe containing combat events.
        lens: The resolved lens from :mod:`veschov.ui.chirality`. If ``None``, the
            dataframe is returned unmodified.
        skip_target_filter_for_procs: When ``True``, proc event rows (Officer/ForbiddenTechAbility)
            bypass target filtering so they remain visible even when target metadata is blank.

    Returns:
        The filtered dataframe, constrained by the lens selection if possible.
    """
    if lens is None:
        return df

    session_info = st.session_state.get("session_info")
    filtered = df

    attacker_mask = pd.Series(True, index=filtered.index)
    attacker_specs = lens.attacker_specs
    if isinstance(session_info, SessionInfo) and attacker_specs:
        attacker_df = session_info.get_combat_df_filtered_by_attackers(attacker_specs)
        attacker_mask = filtered.index.isin(attacker_df.index)

    filtered = filtered.loc[attacker_mask]

    target_mask = pd.Series(True, index=filtered.index)
    target_specs = lens.target_specs
    if isinstance(session_info, SessionInfo) and target_specs:
        target_df = session_info.get_combat_df_filtered_by_targets(target_specs)
        target_mask = filtered.index.isin(target_df.index)

    if skip_target_filter_for_procs and "event_type" in filtered.columns:
        event_types = filtered["event_type"].fillna("").astype(str).str.strip().str.lower()
        proc_mask = event_types.isin(PROC_EVENT_TYPES)
        if proc_mask.any():
            target_mask = target_mask | proc_mask

    filtered = filtered.loc[target_mask]

    return filtered
