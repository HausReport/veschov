from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Sequence

import pandas as pd

logger = logging.getLogger(__name__)

OUTCOME_ICONS = {
    "VICTORY": ("Victory", "🏆"),
    "DEFEAT": ("Defeat", "💀"),
    "PARTIAL VICTORY": ("Partial Victory", "⚖️"),
    "PARTIAL": ("Partial Victory", "⚖️"),
}


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


class SessionInfo:
    """Expose filtered views and helpers for combat session data."""

    def __init__(self, combat_df: pd.DataFrame) -> None:
        self.combat_df = combat_df
        players_df = combat_df.attrs.get("players_df")
        if not isinstance(players_df, pd.DataFrame):
            logger.warning("SessionInfo missing players_df in combat_df attrs.")
            players_df = pd.DataFrame()
        fleets_df = combat_df.attrs.get("fleets_df")
        if not isinstance(fleets_df, pd.DataFrame):
            logger.warning("SessionInfo missing fleets_df in combat_df attrs.")
            fleets_df = pd.DataFrame()
        self.players_df = players_df
        self.fleets_df = fleets_df

    def get_combat_df_filtered_by_attacker(self, spec: ShipSpecifier) -> pd.DataFrame:
        """Return combat rows matching a single attacker spec."""
        df = self.combat_df
        for column in ("attacker_name", "attacker_alliance", "attacker_ship"):
            if column not in df.columns:
                logger.warning(
                    "Combat df missing %s column; cannot filter by attacker.",
                    column,
                )
                return df.iloc[0:0]

        mask = pd.Series(True, index=df.index)

        if spec.name:
            mask &= df["attacker_name"] == spec.name
        if spec.alliance:
            mask &= df["attacker_alliance"] == spec.alliance
        if spec.ship:
            mask &= df["attacker_ship"] == spec.ship

        return df.loc[mask]

    def get_combat_df_filtered_by_attackers(
        self,
        specs: Sequence[ShipSpecifier],
    ) -> pd.DataFrame:
        """Return combat rows for any of the provided attacker specs."""
        if not specs:
            return self.combat_df

        mask = pd.Series(False, index=self.combat_df.index)
        for spec in specs:
            filtered_df = self.get_combat_df_filtered_by_attacker(spec)
            mask |= self.combat_df.index.isin(filtered_df.index)

        return self.combat_df.loc[mask]

    @staticmethod
    def normalize_text(value: object) -> str:
        """Normalize values into trimmed strings, mapping nulls to empty."""
        if pd.isna(value) or value is None:
            return ""
        return str(value).strip()

    @classmethod
    def normalize_spec_key(
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

    @classmethod
    def normalize_outcome(cls, outcome: object) -> str:
        """Normalize outcome values into uppercase labels."""
        if pd.isna(outcome) or outcome is None:
            return ""
        normalized = str(outcome).strip().upper().replace("_", " ")
        return normalized

    @classmethod
    def outcome_label_emoji(cls, outcome: object) -> tuple[str, str] | None:
        """Return the label and emoji for a known outcome."""
        normalized = cls.normalize_outcome(outcome)
        if not normalized:
            return None
        return OUTCOME_ICONS.get(normalized)

    @classmethod
    def outcome_emoji(cls, outcome: object) -> str:
        """Return the emoji for a known outcome, or the unknown fallback."""
        label_emoji = cls.outcome_label_emoji(outcome)
        if label_emoji:
            return label_emoji[1]
        return "❔"

    def _resolve_player_alliance(self, row: pd.Series) -> str:
        """Return the alliance field from the players section when available."""
        for column in ("Alliance", "Player Alliance"):
            if column in row.index:
                alliance = self.normalize_text(row.get(column))
                if alliance:
                    return alliance
        return ""

    def build_outcome_lookup(self) -> dict[tuple[str, str, str], object]:
        """Return a lookup of normalized ship specs to Outcome values."""
        if not isinstance(self.players_df, pd.DataFrame) or self.players_df.empty:
            logger.warning("Outcome lookup skipped: players_df missing or empty.")
            return {}
        if "Outcome" not in self.players_df.columns:
            logger.warning("Outcome lookup skipped: 'Outcome' column missing.")
            return {}
        outcome_lookup: dict[tuple[str, str, str], object] = {}
        for _, row in self.players_df.iterrows():
            name = self.normalize_text(row.get("Player Name"))
            ship = self.normalize_text(row.get("Ship Name"))
            alliance = self._resolve_player_alliance(row)
            if not any([name, ship, alliance]):
                continue
            key = self.normalize_spec_key(name, alliance, ship)
            if key in outcome_lookup:
                continue
            outcome_lookup[key] = row.get("Outcome")
        return outcome_lookup

    def get_every_ship(self) -> set[ShipSpecifier]:
        """Return unique attacker combinations across the combat log."""
        df = self.combat_df
        cols = ["attacker_name", "attacker_alliance", "attacker_ship"]
        missing = [column for column in cols if column not in df.columns]
        if missing:
            logger.warning(
                "Combat df missing attacker columns for ship roster: %s",
                missing,
            )
            return set()

        unique_combos_df = (
            df.loc[:, cols]
            .dropna(how="all")
            .fillna("")  # avoid NaN leaking into dataclass
            .astype(str)  # ensure all are strings
            .drop_duplicates()
            .reset_index(drop=True)
        )

        return {
            ShipSpecifier(
                name=row["attacker_name"],
                alliance=row["attacker_alliance"],
                ship=row["attacker_ship"],
            )
            for row in unique_combos_df.to_dict(orient="records")
        }

    def get_ships(self, combatant_name: str) -> set[str]:
        """Return all ships used by a combatant in attack events."""
        df = self.combat_df
        event_type = df["event_type"].astype(str).str.lower()
        mask = (event_type == "attack") & (df["attacker_name"] == combatant_name)
        return set(df.loc[mask, "attacker_ship"].dropna().astype(str).unique())

    def get_captain_name(self, combatant_name: str, ship_name: str) -> set[str]:
        """Return the captain officer name(s) for a combatant and ship."""
        df = self.players_df
        mask = (df["Ship Name"] == ship_name) & (df["Player Name"] == combatant_name)
        return set(df.loc[mask, "Officer One"].dropna().astype(str).unique())

    def get_1st_officer_name(self, combatant_name: str, ship_name: str) -> set[str]:
        """Return the first officer name(s) for a combatant and ship."""
        df = self.players_df
        mask = (df["Ship Name"] == ship_name) & (df["Player Name"] == combatant_name)
        return set(df.loc[mask, "Officer Two"].dropna().astype(str).unique())

    def get_2nd_officer_name(self, combatant_name: str, ship_name: str) -> set[str]:
        """Return the second officer name(s) for a combatant and ship."""
        df = self.players_df
        mask = (df["Ship Name"] == ship_name) & (df["Player Name"] == combatant_name)
        return set(df.loc[mask, "Officer Three"].dropna().astype(str).unique())

    def get_bridge_crew(self, combatant_name: str, ship_name: str) -> set[str]:
        """Return the bridge crew officer names for a combatant and ship."""
        bridge_crew: set[str] = set()
        bridge_crew.update(self.get_captain_name(combatant_name, ship_name))
        bridge_crew.update(self.get_1st_officer_name(combatant_name, ship_name))
        bridge_crew.update(self.get_2nd_officer_name(combatant_name, ship_name))
        return bridge_crew

    def get_below_deck_officers(self, combatant_name: str, ship_name: str) -> set[str]:
        """Return below-deck officer names for a combatant and ship."""
        all_officers = self.all_officer_names(combatant_name, ship_name)
        bridge_crew = self.get_bridge_crew(combatant_name, ship_name)
        return all_officers - bridge_crew

    def all_officer_names(self, combatant_name: str, ship_name: str) -> set[str]:
        """Return all officer names activated by a combatant and ship."""
        df = self.combat_df
        event_type = df["event_type"].astype(str).str.lower()
        mask = (
            (event_type == "officer")
            & (df["attacker_ship"] == ship_name)
            & (df["attacker_name"] == combatant_name)
        )
        return set(df.loc[mask, "ability_owner_name"].dropna().astype(str).unique())

    def combatant_names(self) -> set[str]:
        """Return the union of player and attacker names."""
        df = self.players_df
        combatants = set(df["Player Name"].dropna().astype(str).unique())
        df = self.combat_df
        combatants.update(set(df["attacker_name"].dropna().astype(str).unique()))
        return combatants

    def alliance_names(self) -> set[str]:
        """Return all attacker alliance names in the combat log."""
        df = self.combat_df
        return set(df["attacker_alliance"].dropna().astype(str).unique())
