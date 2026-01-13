"""Resolve report lens (actor/target) from player and NPC selection."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

from dataclasses import dataclass
from typing import Iterable, Sequence

from veschov.io.SessionInfo import ShipSpecifier


def _spec_names(specs: Iterable[ShipSpecifier]) -> set[str]:
    return {spec.name for spec in specs if spec.name}


@dataclass(frozen=True)
class Lens:
    actor_name: str | None
    target_name: str | None
    label: str
    attacker_specs: tuple[ShipSpecifier, ...] = ()
    target_specs: tuple[ShipSpecifier, ...] = ()

    def attacker_names(self) -> set[str]:
        names = _spec_names(self.attacker_specs)
        if names:
            return names
        if self.actor_name:
            return {self.actor_name}
        return set()

    def target_names(self) -> set[str]:
        names = _spec_names(self.target_specs)
        if names:
            return names
        if self.target_name:
            return {self.target_name}
        return set()


def resolve_lens(
        page_id: str,
        selected_attackers: Sequence[ShipSpecifier],
        selected_targets: Sequence[ShipSpecifier],
) -> Lens:
    actor_name = selected_attackers[0].name if len(selected_attackers) == 1 else None
    target_name = selected_targets[0].name if len(selected_targets) == 1 else None
    # if page_id == "apex_barrier":
    #     return Lens(
    #         actor_name=target_name,
    #         target_name=actor_name,
    #         label="NPC → Player",
    #         attacker_specs=tuple(selected_targets),
    #         target_specs=tuple(selected_attackers),
    #     )
    # if page_id == "isolytic_damage":
    #     return Lens(
    #         actor_name=actor_name,
    #         target_name=target_name,
    #         label="Player → NPC",
    #         attacker_specs=tuple(selected_attackers),
    #         target_specs=tuple(selected_targets),
    #     )
    return Lens(
        actor_name=actor_name,
        target_name=target_name,
        label="Player → NPC",
        attacker_specs=tuple(selected_attackers),
        target_specs=tuple(selected_targets),
    )
