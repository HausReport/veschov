from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from veschov.ui.object_reports.AttackerAndTargetReport import SerializedShipSpec


@dataclass
class AttackerTargetSelection:
    """Container for attacker/target roster and selection state."""
    attacker_roster: list[SerializedShipSpec]
    target_roster: list[SerializedShipSpec]
    selected_attackers: list[SerializedShipSpec]
    selected_targets: list[SerializedShipSpec]