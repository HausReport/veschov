"""Battle log parser stub."""

from __future__ import annotations

import io
import logging
from typing import IO, Any

import pandas as pd

from veschov.columns import resolve_event_type, add_alias_columns
from veschov.io.StartsWhen import extract_sections, section_to_dataframe, SECTION_HEADERS, StartsWhen
from veschov.transforms.derive_metrics import add_shot_index

logger = logging.getLogger(__name__)

NA_TOKENS = ("--", "—", "–", "")

POOL_DAMAGE_COLUMNS = ("Shield Damage", "Hull Damage")
RAW_NUMERIC_COLUMNS = (
    "Round",
    "Total Damage",
    "Mitigated Damage",
    "Mitigated Isolytic Damage",
    "Mitigated Apex Barrier",
    "Total Isolytic Damage",
    "Ability Value",
    *POOL_DAMAGE_COLUMNS,
)

COMBAT_COLUMN_RENAMES = {
    "Critical Hit?": "is_crit",
    "Hull Damage": "hull_damage",
    "Shield Damage": "shield_damage",
    "Mitigated Damage": "mitigated_normal",
    "Mitigated Isolytic Damage": "mitigated_iso",
    "Mitigated Apex Barrier": "mitigated_apex",
    "Total Damage": "total_normal",
    "Total Isolytic Damage": "total_iso",
    "Round": "round",
    "Battle Event": "battle_event",
    "Type": "event_type",
    "Attacker Name": "attacker_name",
    "Attacker Alliance": "attacker_alliance",
    "Attacker Ship": "attacker_ship",
    "Attacker - Is Armada?": "attacker_is_armada",
    "Target Name": "target_name",
    "Target Alliance": "target_alliance",
    "Target Ship": "target_ship",
    "Target - Is Armada?": "target_is_armada",
    "Ability Type": "ability_type",
    "Ability Value": "ability_value",
    "Ability Name": "ability_name",
    "Ability Owner Name": "ability_owner_name",
    "Target Defeated": "target_defeated",
    "Target Destroyed": "target_destroyed",
}

FLEET_COLUMN_RENAMES = {
    "Buff applied": "buff_applied",
    "Debuff applied": "debuff_applied",
}

NORMALIZED_NUMERIC_COLUMNS = (
    "round",
    "total_normal",
    "mitigated_normal",
    "mitigated_iso",
    "mitigated_apex",
    "total_iso",
    "ability_value",
    "shield_damage",
    "hull_damage",
)

COMBAT_BOOLEAN_COLUMNS = ("is_crit", "attacker_is_armada", "target_is_armada")
FLEET_BOOLEAN_COLUMNS = ("buff_applied", "debuff_applied")

COLUMN_ORDER = [
    "round",
    "battle_event",
    "event_type",
    "is_crit",
    "attacker_name",
    "attacker_ship",
    "attacker_alliance",
    "attacker_is_armada",
    "target_name",
    "target_ship",
    "target_alliance",
    "target_is_armada",
    "applied_damage",
    "damage_after_apex",
    "shield_damage",
    "hull_damage",
    "mitigated_apex",
    "damage_before_apex",
    "apex_r",
    "apex_barrier_hit",
    "total_iso",
    "mitigated_iso",
    "iso_remain",
    "total_normal",
    "mitigated_normal",
    "normal_remain",
    "remain_before_apex",
    "accounting_delta",
    "ability_type",
    "ability_value",
    "ability_name",
    "ability_owner_name",
    "target_defeated",
    "target_destroyed",
]


def _read_text(file_bytes: bytes | str | IO[Any]) -> str:
    if isinstance(file_bytes, bytes):
        return file_bytes.decode("utf-8", errors="replace")
    if isinstance(file_bytes, str):
        return file_bytes
    if hasattr(file_bytes, "read"):
        content = file_bytes.read()
        if isinstance(content, bytes):
            return content.decode("utf-8", errors="replace")
        return str(content)
    return str(file_bytes)


def _normalize_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    cleaned = df.copy()
    for column in cleaned.columns:
        if pd.api.types.is_object_dtype(cleaned[column]) or pd.api.types.is_string_dtype(
            cleaned[column]
        ):
            cleaned[column] = cleaned[column].astype("string").str.strip()
    cleaned = cleaned.replace(list(NA_TOKENS), pd.NA)
    return cleaned


def _coerce_numeric_columns(df: pd.DataFrame, columns: tuple[str, ...]) -> pd.DataFrame:
    updated = df.copy()
    for column in columns:
        if column not in updated.columns:
            continue
        cleaned = updated[column].astype("string").str.replace(",", "", regex=False).str.strip()
        updated[column] = pd.to_numeric(cleaned, errors="coerce")
    return updated


def _coerce_yes_no_columns(df: pd.DataFrame, columns: tuple[str, ...]) -> pd.DataFrame:
    updated = df.copy()
    for column in columns:
        if column not in updated.columns:
            continue
        cleaned = updated[column].astype("string").str.strip().str.upper()
        updated[column] = cleaned.map({"YES": True, "NO": False}).astype("boolean")
    return updated


def _fallback_players_df(
    combat_df: pd.DataFrame, npc_name: str | None
) -> pd.DataFrame:
    """Return player rows inferred from combat data when player metadata is missing."""
    required_columns = {
        "attacker_name",
        "attacker_ship",
        "target_name",
        "target_ship",
    }
    if not required_columns.issubset(combat_df.columns):
        return pd.DataFrame(columns=["Player Name", "Ship Name"])

    frames: list[pd.DataFrame] = []
    for name_col, ship_col in (
        ("attacker_name", "attacker_ship"),
        ("target_name", "target_ship"),
    ):
        subset = (
            combat_df.loc[:, [name_col, ship_col]]
            .dropna(how="all")
            .fillna("")
            .astype(str)
            .rename(columns={name_col: "Player Name", ship_col: "Ship Name"})
        )
        frames.append(subset)

    combined = pd.concat(frames, ignore_index=True).drop_duplicates().reset_index(drop=True)
    if npc_name:
        combined = combined[combined["Player Name"].str.strip() != npc_name]

    combined = combined[
        (combined["Player Name"].str.strip() != "")
        | (combined["Ship Name"].str.strip() != "")
    ]
    combined = combined.replace({"": pd.NA})
    return combined.loc[:, ["Player Name", "Ship Name"]].reset_index(drop=True)


def _align_players_columns(source_df: pd.DataFrame, columns: pd.Index) -> pd.DataFrame:
    """Align inferred player data to the export metadata columns."""
    aligned = {
        column: source_df[column] if column in source_df.columns else pd.NA
        for column in columns
    }
    return pd.DataFrame(aligned)


def _augment_players_df(players_df: pd.DataFrame, combat_df: pd.DataFrame) -> pd.DataFrame:
    """Augment player metadata with entries inferred from the combat log."""
    if len(players_df) > 1:
        return players_df

    npc_name = None
    if not players_df.empty:
        npc_name = str(players_df.iloc[-1].get("Player Name") or "").strip() or None

    fallback_df = _fallback_players_df(combat_df, npc_name)
    if fallback_df.empty:
        return players_df

    aligned_fallback = _align_players_columns(fallback_df, players_df.columns)
    if players_df.empty:
        return aligned_fallback

    npc_row = players_df.iloc[-1:]
    aligned_fallback = aligned_fallback.dropna(axis="columns", how="all")
    combined = pd.concat([aligned_fallback, npc_row], ignore_index=True)
    return combined.reindex(columns=players_df.columns)


def _numeric_series(df: pd.DataFrame, column: str) -> pd.Series:
    if column not in df.columns:
        return pd.Series(pd.NA, index=df.index, dtype="Float64")
    return pd.to_numeric(df[column], errors="coerce")


def _normalize_combat_df(df: pd.DataFrame) -> pd.DataFrame:
    cleaned = _normalize_dataframe(df)
    cleaned = _coerce_numeric_columns(cleaned, RAW_NUMERIC_COLUMNS)
    renamed = cleaned.rename(columns=COMBAT_COLUMN_RENAMES, inplace=False)
    renamed = _coerce_numeric_columns(renamed, NORMALIZED_NUMERIC_COLUMNS)
    renamed = _coerce_yes_no_columns(renamed, COMBAT_BOOLEAN_COLUMNS)
    resolved_event_type = resolve_event_type(renamed)
    if resolved_event_type is not None:
        renamed["event_type"] = resolved_event_type

    # Damage pipeline (per-shot, per row):
    # 1) Raw lane totals (pre mitigation): total_iso, total_normal.
    # 2) Lane mitigation: mitigated_iso, mitigated_normal.
    # 3) Lane remainders: iso_remain = total_iso - mitigated_iso,
    #    normal_remain = total_normal - mitigated_normal.
    # 4) Combine lanes: remain_before_apex = iso_remain + normal_remain.
    # 5) Apex applies last on the combined remainder (conceptually damage_before_apex = remain_before_apex):
    #    damage_after_apex = damage_before_apex - mitigated_apex.
    # 6) Pool split after Apex: applied_damage = shield_damage + hull_damage,
    #    and observed applied_damage ≈ damage_after_apex (rounding).
    shield_damage = _numeric_series(renamed, "shield_damage")
    hull_damage = _numeric_series(renamed, "hull_damage")
    # applied_damage: final damage applied to pools (after all mitigation).
    renamed["applied_damage"] = shield_damage + hull_damage
    renamed = add_alias_columns(renamed)

    mitigated_apex = _numeric_series(renamed, "mitigated_apex")
    # damage_before_apex: undo Apex (damage_before_apex = damage_after_apex + mitigated_apex).
    renamed["damage_before_apex"] = renamed["damage_after_apex"] + mitigated_apex

    total_iso = _numeric_series(renamed, "total_iso")
    mitigated_iso = _numeric_series(renamed, "mitigated_iso")
    # iso_remain: isolytic lane remainder after iso mitigation (total_iso - mitigated_iso).
    renamed["iso_remain"] = total_iso - mitigated_iso

    # total_normal is *pre-Apex* raw normal-lane damage, not final applied damage.
    # It is the normal-lane "total" before normal mitigation or pool split.
    total_normal = _numeric_series(renamed, "total_normal")
    mitigated_normal = _numeric_series(renamed, "mitigated_normal")
    # normal_remain: normal lane remainder after normal mitigation.
    renamed["normal_remain"] = total_normal - mitigated_normal

    # remain_before_apex: combined lane remainders (iso_remain + normal_remain).
    renamed["remain_before_apex"] = renamed["iso_remain"] + renamed["normal_remain"]

    damage_before_apex = _numeric_series(renamed, "damage_before_apex")
    damage_after_apex = _numeric_series(renamed, "damage_after_apex")
    # apex_r: fraction of pre-Apex remainder that survives Apex (damage_after / damage_before).
    renamed["apex_r"] = damage_after_apex.div(damage_before_apex).where(
        damage_before_apex != 0
    )
    # apex_barrier_hit: inferred barrier value (S=10000) from mitigated_apex vs post-Apex damage.
    # Example (brief): if mitigated_apex=200 and damage_after_apex=800, hit≈10k*(200/800)=2500.
    renamed["apex_barrier_hit"] = (
        (10_000 * mitigated_apex.div(damage_after_apex).where(damage_after_apex != 0))
        .round()
    )
    # Sanity check: disjoint accounting identity (≈ raw_total).
    # mitigated_iso + mitigated_normal + mitigated_apex + shield_damage + hull_damage
    # ≈ total_iso + total_normal
    raw_total = total_iso + total_normal
    accounted_total = (
        mitigated_iso + mitigated_normal + mitigated_apex + shield_damage + hull_damage
    )
    # accounting_delta should be ~0 (rounding noise).
    renamed["accounting_delta"] = raw_total - accounted_total

    ordered = [column for column in COLUMN_ORDER if column in renamed.columns]
    extras = [column for column in renamed.columns if column not in ordered]
    renamed = renamed.loc[:, ordered + extras]
    return renamed


def parse_battle_log(file_bytes: bytes, filename: str) -> pd.DataFrame:
    """
    Should return a pandas DataFrame with at least:
      - 'mitigated_apex'
      - 'total_normal'
    """
    text = _read_text(file_bytes)
    f = io.StringIO(text)

    sections = extract_sections(text)
    players_df = section_to_dataframe(sections.get("players"), SECTION_HEADERS["players"])
    fleets_df = section_to_dataframe(sections.get("fleets"), SECTION_HEADERS["fleets"])

    wrapped = StartsWhen(f, "Round\t")
    df = pd.read_csv(wrapped, sep="\t", dtype=str, na_values=NA_TOKENS)
    raw_df = df.copy()
    df = _normalize_combat_df(df)
    df = add_shot_index(df)

    players_df = _normalize_dataframe(players_df)
    players_df = _augment_players_df(players_df, df)
    fleets_df = _normalize_dataframe(fleets_df)
    fleets_df = fleets_df.rename(columns=FLEET_COLUMN_RENAMES, inplace=False)
    fleets_df = _coerce_yes_no_columns(fleets_df, FLEET_BOOLEAN_COLUMNS)
    df.attrs["players_df"] = players_df
    df.attrs["fleets_df"] = fleets_df
    df.attrs["raw_combat_df"] = raw_df
    return df
