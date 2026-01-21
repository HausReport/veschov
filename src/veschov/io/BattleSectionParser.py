"""Parse the combat section of a battle log export."""

from __future__ import annotations

import io
import logging
from typing import IO, Any

import pandas as pd

from veschov.io.AbstractSectionParser import AbstractSectionParser
from veschov.io.StartsWhen import StartsWhen, extract_sections
from veschov.io.columns import resolve_event_type
from veschov.io.schemas import CombatSchema, normalize_dataframe_for_schema, validate_dataframe
from veschov.transforms.derive_metrics import add_shot_index

logger = logging.getLogger(__name__)


class BattleSectionParser(AbstractSectionParser):
    """Parse and normalize the combat section of a battle log."""

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

    def __init__(self, file_bytes: bytes | str | IO[Any]) -> None:
        self.file_bytes = file_bytes

    def parse(self, *, soft: bool = False) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Return the validated combat dataframe plus a raw copy."""
        text = self._read_text(self.file_bytes)
        wrapped = StartsWhen(io.StringIO(text), "Round\t")
        df = pd.read_csv(wrapped, sep="\t", dtype=str, na_values=self.NA_TOKENS)
        raw_df = df.copy()
        df = self._normalize_combat_df(df)
        df = add_shot_index(df)
        df = validate_dataframe(df, CombatSchema, soft=soft, context="combat section")
        return df, raw_df

    def parse_with_sections(
        self, *, soft: bool = False
    ) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, str]]:
        """Return the validated combat dataframe, raw copy, and extracted sections."""
        text = self._read_text(self.file_bytes)
        sections = extract_sections(text)
        df, raw_df = BattleSectionParser(text).parse(soft=soft)
        return df, raw_df, sections

    def _normalize_combat_df(self, df: pd.DataFrame) -> pd.DataFrame:
        cleaned = self._normalize_dataframe(df)
        cleaned = self._coerce_numeric_columns(cleaned, self.RAW_NUMERIC_COLUMNS)
        normalized = normalize_dataframe_for_schema(cleaned, CombatSchema)
        normalized = self._coerce_numeric_columns(
            normalized, self.NORMALIZED_NUMERIC_COLUMNS
        )
        normalized = self._coerce_yes_no_columns(normalized, self.COMBAT_BOOLEAN_COLUMNS)
        resolved_event_type = resolve_event_type(normalized)
        if resolved_event_type is not None:
            normalized["event_type"] = resolved_event_type

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
        shield_damage = self._numeric_series(normalized, "shield_damage")
        hull_damage = self._numeric_series(normalized, "hull_damage")
        # applied_damage: final damage applied to pools (after all mitigation).
        normalized["applied_damage"] = shield_damage + hull_damage
        normalized = normalize_dataframe_for_schema(normalized, CombatSchema)

        mitigated_apex = self._numeric_series(normalized, "mitigated_apex")
        # damage_before_apex: undo Apex (damage_before_apex = damage_after_apex + mitigated_apex).
        normalized["damage_before_apex"] = (
            normalized["damage_after_apex"] + mitigated_apex
        )

        total_iso = self._numeric_series(normalized, "total_iso")
        mitigated_iso = self._numeric_series(normalized, "mitigated_iso")
        # iso_remain: isolytic lane remainder after iso mitigation (total_iso - mitigated_iso).
        normalized["iso_remain"] = total_iso - mitigated_iso

        # total_normal is *pre-Apex* raw normal-lane damage, not final applied damage.
        # It is the normal-lane "total" before normal mitigation or pool split.
        total_normal = self._numeric_series(normalized, "total_normal")
        mitigated_normal = self._numeric_series(normalized, "mitigated_normal")
        # normal_remain: normal lane remainder after normal mitigation.
        normalized["normal_remain"] = total_normal - mitigated_normal

        # remain_before_apex: combined lane remainders (iso_remain + normal_remain).
        normalized["remain_before_apex"] = (
            normalized["iso_remain"] + normalized["normal_remain"]
        )

        damage_before_apex = self._numeric_series(normalized, "damage_before_apex")
        damage_after_apex = self._numeric_series(normalized, "damage_after_apex")
        # apex_r: fraction of pre-Apex remainder that survives Apex (damage_after / damage_before).
        normalized["apex_r"] = damage_after_apex.div(damage_before_apex).where(
            damage_before_apex != 0
        )
        # apex_barrier_hit: inferred barrier value (S=10000) from mitigated_apex vs post-Apex damage.
        # Example (brief): if mitigated_apex=200 and damage_after_apex=800, hit≈10k*(200/800)=2500.
        normalized["apex_barrier_hit"] = (
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
        normalized["accounting_delta"] = raw_total - accounted_total

        return normalize_dataframe_for_schema(normalized, CombatSchema)
