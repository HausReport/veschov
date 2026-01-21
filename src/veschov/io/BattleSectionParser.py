from __future__ import annotations

import logging

import pandas as pd

from veschov.io.AbstractSectionParser import AbstractSectionParser
from veschov.io.StartsWhen import SECTION_HEADERS, section_to_dataframe
from veschov.io.columns import add_alias_columns, resolve_event_type
from veschov.transforms.derive_metrics import add_shot_index

logger = logging.getLogger(__name__)

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


class BattleSectionParser(AbstractSectionParser):
    """Parse and normalize the combat section of a battle log."""

    section_key = "combat"
    header_prefix = SECTION_HEADERS["combat"]

    def __init__(self) -> None:
        self.raw_df: pd.DataFrame | None = None

    def parse_section(self, text: str, sections: dict[str, str]) -> pd.DataFrame:
        """Parse the combat section and return the normalized dataframe."""
        section_text = sections.get(self.section_key)
        df = section_to_dataframe(section_text, self.header_prefix)
        self.raw_df = df.copy()
        normalized = self._normalize_combat_df(df)
        return add_shot_index(normalized)

    @staticmethod
    def _numeric_series(df: pd.DataFrame, column: str) -> pd.Series:
        if column not in df.columns:
            return pd.Series(pd.NA, index=df.index, dtype="Float64")
        return pd.to_numeric(df[column], errors="coerce")

    def _normalize_combat_df(self, df: pd.DataFrame) -> pd.DataFrame:
        cleaned = self._normalize_dataframe(df)
        cleaned = self._coerce_numeric_columns(cleaned, RAW_NUMERIC_COLUMNS)
        renamed = cleaned.rename(columns=COMBAT_COLUMN_RENAMES, inplace=False)
        renamed = self._coerce_numeric_columns(renamed, NORMALIZED_NUMERIC_COLUMNS)
        renamed = self._coerce_yes_no_columns(renamed, COMBAT_BOOLEAN_COLUMNS)
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
        shield_damage = self._numeric_series(renamed, "shield_damage")
        hull_damage = self._numeric_series(renamed, "hull_damage")
        # applied_damage: final damage applied to pools (after all mitigation).
        renamed["applied_damage"] = shield_damage + hull_damage
        renamed = add_alias_columns(renamed)

        mitigated_apex = self._numeric_series(renamed, "mitigated_apex")
        # damage_before_apex: undo Apex (damage_before_apex = damage_after_apex + mitigated_apex).
        renamed["damage_before_apex"] = renamed["damage_after_apex"] + mitigated_apex

        total_iso = self._numeric_series(renamed, "total_iso")
        mitigated_iso = self._numeric_series(renamed, "mitigated_iso")
        # iso_remain: isolytic lane remainder after iso mitigation (total_iso - mitigated_iso).
        renamed["iso_remain"] = total_iso - mitigated_iso

        # total_normal is *pre-Apex* raw normal-lane damage, not final applied damage.
        # It is the normal-lane "total" before normal mitigation or pool split.
        total_normal = self._numeric_series(renamed, "total_normal")
        mitigated_normal = self._numeric_series(renamed, "mitigated_normal")
        # normal_remain: normal lane remainder after normal mitigation.
        renamed["normal_remain"] = total_normal - mitigated_normal

        # remain_before_apex: combined lane remainders (iso_remain + normal_remain).
        renamed["remain_before_apex"] = renamed["iso_remain"] + renamed["normal_remain"]

        damage_before_apex = self._numeric_series(renamed, "damage_before_apex")
        damage_after_apex = self._numeric_series(renamed, "damage_after_apex")
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
