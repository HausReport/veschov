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
from veschov.transforms.columns import ATTACKER_COLUMN_CANDIDATES, TARGET_COLUMN_CANDIDATES, resolve_column
from veschov.ui.chirality import Lens


def apply_combat_lens(
        df: pd.DataFrame,
        lens: Lens | None
) -> pd.DataFrame:
    """Filter combat data using a resolved combat lens.

    This function applies an attacker/target "lens" to a dataframe that represents
    combat events. It performs two passes:

    1. **Attacker filtering**:
       * If `st.session_state["session_info"]` is a :class:`SessionInfo` and the lens
         includes `attacker_specs`, filter by the index set of combat rows that match
         those ship specifiers (this is the most authoritative match).
       * Otherwise, try to resolve an attacker column and match against the name set
         derived from the lens (`Lens.attacker_names()`), which uses spec names first
         and falls back to the lens actor label.
       * Optionally include rows where the attacker column is ``NaN``.
    2. **Target filtering**:
       * Resolve a target column and filter by `Lens.target_names()`, again falling
         back from spec names to lens target labels.
       * Optionally include rows where the target column is ``NaN``.

    If a column cannot be resolved or the lens does not provide matching names/specs,
    the function leaves that dimension unfiltered.

    Args:
        df: Input dataframe containing combat events.
        lens: The resolved lens from :mod:`veschov.ui.chirality`. If ``None``, the
            dataframe is returned unmodified.

    Returns:
        The filtered dataframe, constrained by the lens selection if possible.
    """
    if lens is None:
        return df

    session_info = st.session_state.get("session_info")
    filtered = df

    attacker_column = resolve_column(filtered, ATTACKER_COLUMN_CANDIDATES)
    target_column = resolve_column(filtered, TARGET_COLUMN_CANDIDATES)

    attacker_mask = pd.Series(True, index=filtered.index)
    attacker_specs = lens.attacker_specs
    if isinstance(session_info, SessionInfo) and attacker_specs:
        attacker_df = session_info.get_combat_df_filtered_by_attackers(attacker_specs)
        attacker_mask = filtered.index.isin(attacker_df.index)
    elif attacker_column:
        attacker_names = lens.attacker_names()
        if attacker_names:
            attacker_mask = filtered[attacker_column].isin(attacker_names)

    filtered = filtered.loc[attacker_mask]

    if target_column:
        target_names = lens.target_names()
        if target_names:
            target_series = filtered[target_column]
            target_mask = target_series.isin(target_names)
            filtered = filtered.loc[target_mask]

    return filtered
