"""Pandera schema for normalized combat log data."""

from __future__ import annotations

from typing import ClassVar

import pandera as pa
from pandera.typing import Series


class CombatSchema(pa.DataFrameModel):
    """Schema definition for normalized combat log rows."""

    round: Series[float] = pa.Field(nullable=True)
    battle_event: Series[str] = pa.Field(nullable=True)
    event_type: Series[str] = pa.Field(nullable=True)
    is_crit: Series[bool] = pa.Field(nullable=True)

    attacker_name: Series[str] = pa.Field(nullable=True)
    attacker_ship: Series[str] = pa.Field(nullable=True)
    attacker_alliance: Series[str] = pa.Field(nullable=True, required=False)
    attacker_is_armada: Series[bool] = pa.Field(nullable=True, required=False)

    target_name: Series[str] = pa.Field(nullable=True)
    target_ship: Series[str] = pa.Field(nullable=True)
    target_alliance: Series[str] = pa.Field(nullable=True, required=False)
    target_is_armada: Series[bool] = pa.Field(nullable=True, required=False)

    applied_damage: Series[float] = pa.Field(nullable=True)
    damage_after_apex: Series[float] = pa.Field(nullable=True)
    shield_damage: Series[float] = pa.Field(nullable=True)
    hull_damage: Series[float] = pa.Field(nullable=True)
    mitigated_apex: Series[float] = pa.Field(nullable=True)
    damage_before_apex: Series[float] = pa.Field(nullable=True)
    apex_r: Series[float] = pa.Field(nullable=True)
    apex_barrier_hit: Series[float] = pa.Field(nullable=True)
    total_iso: Series[float] = pa.Field(nullable=True)
    mitigated_iso: Series[float] = pa.Field(nullable=True)
    iso_remain: Series[float] = pa.Field(nullable=True)
    total_normal: Series[float] = pa.Field(nullable=True)
    mitigated_normal: Series[float] = pa.Field(nullable=True)
    normal_remain: Series[float] = pa.Field(nullable=True)
    remain_before_apex: Series[float] = pa.Field(nullable=True)
    accounting_delta: Series[float] = pa.Field(nullable=True)

    ability_type: Series[str] = pa.Field(nullable=True, required=False)
    ability_value: Series[float] = pa.Field(nullable=True, required=False)
    ability_name: Series[str] = pa.Field(nullable=True, required=False)
    ability_owner_name: Series[str] = pa.Field(nullable=True, required=False)
    target_defeated: Series[str] = pa.Field(nullable=True, required=False)
    target_destroyed: Series[str] = pa.Field(nullable=True, required=False)

    COLUMN_RENAMES: ClassVar[dict[str, str]] = {
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
    COLUMN_ALIASES: ClassVar[dict[str, str]] = {
        "damage_after_apex": "applied_damage",
    }
    COLUMN_ORDER: ClassVar[list[str]] = [
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

    class Config:
        """Enable dtype coercion while allowing extra columns."""

        coerce = True
        strict = False
