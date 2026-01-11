"""Streamlit UI for actual pool damage per shot."""

from __future__ import annotations

import logging
from typing import Iterable
import pandas as pd
from veschov.transforms.columns import (
    ATTACKER_COLUMN_CANDIDATES,
    TARGET_COLUMN_CANDIDATES,
    get_series,
    resolve_column,
)
from veschov.utils.series import coerce_numeric

logger = logging.getLogger(__name__)

OPTIONAL_PREVIEW_COLUMNS: Iterable[str] = (
    "round",
    "battle_event",
    "is_crit",
    "Ship",
    "Weapon",
)

SEGMENT_ORDER = [
    "Hull",
    "Shield",
    "Mitigated Normal",
    "Mitigated Isolytic",
    "Mitigated Apex",
]
SEGMENT_COLUMNS = {
    "Hull": "hull_damage",
    "Shield": "shield_damage",
    "Mitigated Normal": "mitigated_normal",
    "Mitigated Isolytic": "mitigated_iso",
    "Mitigated Apex": "mitigated_apex",
}
SEGMENT_COLORS = {
    "Hull": "red",
    "Shield": "blue",
    "Mitigated Normal": "#e5f5f9",
    "Mitigated Isolytic": "#99d8c9",
    "Mitigated Apex": "#2ca25f",
}


def _build_damage_mask(df: pd.DataFrame) -> pd.Series:
    if "event_type" not in df.columns:
        raise KeyError("event_type")
    typ = df["event_type"].astype(str).str.strip().str.lower()
    if "total_normal" in df.columns:
        total_damage = coerce_numeric(df["total_normal"])
        shield_damage = coerce_numeric(get_series(df, "shield_damage"))
        hull_damage = coerce_numeric(get_series(df, "hull_damage"))
        pool_positive = (shield_damage > 0) | (hull_damage > 0)
        total_positive = total_damage > 0
        total_missing = total_damage.isna()
        mask = (typ == "attack") & (total_positive | (total_missing & pool_positive))
    else:
        shield_damage = coerce_numeric(get_series(df, "shield_damage"))
        hull_damage = coerce_numeric(get_series(df, "hull_damage"))
        mask = (typ == "attack") & ((shield_damage > 0) | (hull_damage > 0))
    return mask


def _coerce_pool_damage(df: pd.DataFrame) -> pd.DataFrame:
    updated = df.copy()
    updated["shield_damage"] = coerce_numeric(
        get_series(updated, "shield_damage")
    ).fillna(0)
    updated["hull_damage"] = coerce_numeric(get_series(updated, "hull_damage")).fillna(0)
    updated["mitigated_normal"] = coerce_numeric(
        get_series(updated, "mitigated_normal")
    ).fillna(0)
    updated["mitigated_iso"] = coerce_numeric(get_series(updated, "mitigated_iso")).fillna(0)
    updated["mitigated_apex"] = coerce_numeric(
        get_series(updated, "mitigated_apex")
    ).fillna(0)
    return updated


def _normalize_round(df: pd.DataFrame) -> pd.DataFrame:
    if "round" not in df.columns:
        raise KeyError("round")
    updated = df.copy()
    round_series = updated["round"]
    round_numeric = coerce_numeric(round_series)
    if round_numeric.notna().sum() == round_series.notna().sum() and round_series.notna().any():
        updated["round"] = round_numeric.astype("Int64")
    else:
        round_values = round_series.fillna("Unknown").astype(str)
        categories = sorted(round_values.unique())
        updated["round"] = pd.Categorical(round_values, categories=categories, ordered=True)
    return updated


def _build_long_df(
        df: pd.DataFrame,
        hover_columns: list[str],
        *,
        include_shot_index: bool = True,
) -> pd.DataFrame:
    value_vars = list(SEGMENT_COLUMNS.values())
    base_vars: list[str] = ["round", *hover_columns]
    if include_shot_index:
        base_vars.insert(1, "shot_index")
    id_vars = [column for column in dict.fromkeys(base_vars) if column not in value_vars]
    long_df = df.melt(
        id_vars=id_vars,
        value_vars=value_vars,
        var_name="segment",
        value_name="amount",
    )
    long_df["segment"] = long_df["segment"].map(
        {value: key for key, value in SEGMENT_COLUMNS.items()}
    )
    long_df["amount"] = coerce_numeric(long_df["amount"]).fillna(0)
    if include_shot_index and "shot_index" in long_df.columns:
        long_df["shot_index"] = coerce_numeric(long_df["shot_index"])
        long_df = long_df[long_df["shot_index"].notna()].copy()
        long_df["shot_index"] = long_df["shot_index"].astype(int)
    return long_df


def _resolve_hover_columns(df: pd.DataFrame) -> list[str]:
    hover_columns: list[str] = []
    for column in SEGMENT_COLUMNS.values():
        if column in df.columns:
            hover_columns.append(column)
    for column in ("is_crit", "battle_event"):
        if column in df.columns:
            hover_columns.append(column)

    attacker_column = resolve_column(df, ATTACKER_COLUMN_CANDIDATES)
    target_column = resolve_column(df, TARGET_COLUMN_CANDIDATES)
    for column in (attacker_column, target_column):
        if column and column in df.columns:
            hover_columns.append(column)
    return hover_columns
