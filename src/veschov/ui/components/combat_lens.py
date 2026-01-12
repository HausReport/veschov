from __future__ import annotations

from typing import Iterable

import pandas as pd
import streamlit as st

from veschov.io.SessionInfo import SessionInfo
from veschov.transforms.columns import ATTACKER_COLUMN_CANDIDATES, TARGET_COLUMN_CANDIDATES, resolve_column
from veschov.ui.chirality import Lens


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
