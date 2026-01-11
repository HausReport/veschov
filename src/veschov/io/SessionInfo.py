from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import pandas as pd


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
        self.players_df = combat_df.attrs["players_df"]
        self.fleets_df = combat_df.attrs["fleets_df"]

    def get_combat_df_filtered_by_attacker(self, spec: ShipSpecifier) -> pd.DataFrame:
        """Return combat rows matching a single attacker spec."""
        df = self.combat_df

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

    def get_every_ship(self) -> set[ShipSpecifier]:
        """Return unique attacker combinations across the combat log."""
        df = self.combat_df
        cols = ["attacker_name", "attacker_alliance", "attacker_ship"]

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
