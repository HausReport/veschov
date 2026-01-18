from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class ShipSpecifier:
    """Identify a combatant by name, alliance, and ship."""

    name: str | None
    alliance: str | None
    ship: str | None

    @staticmethod
    def normalize_text(value: object) -> str:
        """Normalize values into trimmed strings, mapping nulls to empty."""
        if pd.isna(value) or value is None:
            return ""
        return str(value).strip()

    @classmethod
    def normalize_key(
            cls,
            name: object,
            alliance: object,
            ship: object,
    ) -> tuple[str, str, str]:
        """Normalize a (name, alliance, ship) tuple for stable lookups."""
        return (
            cls.normalize_text(name),
            cls.normalize_text(alliance),
            cls.normalize_text(ship),
        )

    def normalized_name(self) -> str:
        """Return the normalized combatant name."""
        return self.normalize_text(self.name)

    def normalized_alliance(self) -> str:
        """Return the normalized alliance label."""
        return self.normalize_text(self.alliance)

    def normalized_ship(self) -> str:
        """Return the normalized ship label."""
        return self.normalize_text(self.ship)

    def normalized_key(self) -> tuple[str, str, str]:
        """Return the normalized lookup key for this spec."""
        return self.normalize_key(self.name, self.alliance, self.ship)

    def matches_normalized(self, name: object, alliance: object, ship: object) -> bool:
        """Return True when the normalized inputs match this spec."""
        return self.normalized_key() == self.normalize_key(name, alliance, ship)

    def format_label(
            self,
            *,
            include_alliance: bool = True,
            include_ship: bool = True,
            default_name: str = "Unknown",
    ) -> str:
        """Return a formatted label for display."""
        name = self.normalized_name()
        ship = self.normalized_ship()
        alliance = self.normalized_alliance()
        label = name or default_name
        if include_alliance and alliance:
            label = f"{label} [{alliance}]"
        if include_ship and ship and ship != name:
            label = f"{label} — {ship}"
        return label

    def format_label_with_outcome(
            self,
            outcome: object | None,
            *,
            include_alliance: bool = True,
            include_ship: bool = True,
            default_name: str = "Unknown",
    ) -> str:
        """Return a formatted label prefixed by an outcome emoji."""
        from veschov.io.SessionInfo import SessionInfo

        label = self.format_label(
            include_alliance=include_alliance,
            include_ship=include_ship,
            default_name=default_name,
        )
        emoji = SessionInfo.outcome_emoji(outcome)
        return f"{emoji} {label}"

    def format_label_with_outcome_lookup(
            self,
            outcome_lookup: dict[tuple[str, str, str], object] | None,
            *,
            include_alliance: bool = True,
            include_ship: bool = True,
            default_name: str = "Unknown",
    ) -> str:
        """Return a formatted label using an outcome lookup when available."""
        if outcome_lookup is None:
            return self.format_label(
                include_alliance=include_alliance,
                include_ship=include_ship,
                default_name=default_name,
            )
        outcome = outcome_lookup.get(self.normalized_key())
        return self.format_label_with_outcome(
            outcome,
            include_alliance=include_alliance,
            include_ship=include_ship,
            default_name=default_name,
        )

    def __str__(self) -> str:
        return self.format_label(default_name="")
