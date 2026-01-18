from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ShipSpecifier:
    """Identify a combatant by name, alliance, and ship."""

    name: str | None
    alliance: str | None
    ship: str | None

    def __str__(self) -> str:
        label = self.name or ""
        if self.alliance is not None:
            label += f" [{self.alliance}]"
        if self.ship and self.ship != self.name:
            label += f" — {self.ship}"
        return label
