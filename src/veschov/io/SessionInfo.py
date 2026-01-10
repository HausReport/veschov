from dataclasses import dataclass
from typing import Set, Optional, Sequence

import pandas as pd


@dataclass(frozen=True)
class ShipSpecifier:
    name: Optional[str]
    alliance: Optional[str]
    ship: Optional[str]
    # touch

    def __str__(self) -> str:
        ret = self.name
        if self.alliance is not None:
            ret += f" [{self.alliance}]"
        if self.ship is not self.name:
            ret += f" — {self.ship}"
        return ret

class SessionInfo:

    def __init__(self, combat_df):
        self.combat_df = combat_df
        self.players_df = combat_df.attrs["players_df"]
        self.fleets_df = combat_df.attrs["fleets_df"]

    import pandas as pd

    def get_combat_df_filtered_by_attacker(self, spec: ShipSpecifier) -> pd.DataFrame:
        df = self.combat_df

        mask = pd.Series(True, index=df.index)

        # If you use "" as “unspecified”
        if spec.name:
            mask &= (df["attacker_name"] == spec.name)
        if spec.alliance:
            mask &= (df["attacker_alliance"] == spec.alliance)
        if spec.ship:
            mask &= (df["attacker_ship"] == spec.ship)

        return df.loc[mask]

    def get_combat_df_filtered_by_attackers(
        self,
        specs: Sequence[ShipSpecifier],
    ) -> pd.DataFrame:
        if not specs:
            return self.combat_df

        mask = pd.Series(False, index=self.combat_df.index)
        for spec in specs:
            filtered_df = self.get_combat_df_filtered_by_attacker(spec)
            mask |= self.combat_df.index.isin(filtered_df.index)

        return self.combat_df.loc[mask]

    def get_every_ship(self) -> Set[ShipSpecifier]:
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

    #def get_captain_name(self):
    def get_ships(self, combatant_name):
        df = self.combat_df
        print( set( df["event_type"].dropna().astype(str).unique() ) )
        mask = (df["event_type"] == "Attack") & (df["attacker_name"] == combatant_name)
        officers = set(df.loc[mask,"attacker_ship"].dropna().astype(str).unique())
        return officers

    def get_captain_name(self, combatant_name, ship_name):
        df = self.players_df
        mask = (df["Ship Name"] == ship_name) & (df["Player Name"] == combatant_name)
        officer = df.loc[mask,"Officer One"].dropna().astype(str).unique()
        return officer

    def get_1st_officer_name(self, combatant_name, ship_name):
        df = self.players_df
        mask = (df["Ship Name"] == ship_name) & (df["Player Name"] == combatant_name)
        officer = df.loc[mask,"Officer Two"].dropna().astype(str).unique()
        return officer

    def get_2nd_officer_name(self, combatant_name, ship_name):
        df = self.players_df
        mask = (df["Ship Name"] == ship_name) & (df["Player Name"] == combatant_name)
        officer = df.loc[mask,"Officer Three"].dropna().astype(str).unique()
        return officer

    def get_bridge_crew(self, combatant_name, ship_name):
        bc = set ()
        bc.update(self.get_captain_name(combatant_name, ship_name))
        bc.update(self.get_1st_officer_name(combatant_name, ship_name))
        bc.update(self.get_2nd_officer_name(combatant_name, ship_name))
        return bc

    def get_below_deck_officers(self, combatant_name, ship_name):
        set1 = self.all_officer_names()
        set2 = self.get_bridge_crew(combatant_name, ship_name)
        return set1 - set2

    def all_officer_names(self, combatant_name, ship_name) -> Set[str]:
        df = self.combat_df
        print( set( df["event_type"].dropna().astype(str).unique() ) )
        mask = (df["event_type"] == "Officer") & (df["attacker_ship"] == ship_name) & (df["attacker_name"] == combatant_name)
        officers = set(df.loc[mask,"ability_owner_name"].dropna().astype(str).unique())
        return officers

    def combatant_names(self) -> Set[str]:
        # mask = (df["Type"] == "Officer Ability") & (df["Attacker Name"] == "XanOfHanoi")
        df = self.players_df
        # print(df.columns)
        # ['Player Name', 'Player Level', 'Outcome', 'Ship Name', 'Ship Level',
        #        'Ship Strength', 'Ship XP', 'Officer One', 'Officer Two',
        #        'Officer Three', 'Hull Health', 'Hull Health Remaining',
        #        'Shield Health', 'Shield Health Remaining', 'Location', 'Timestamp']
        combatants = set(df["Player Name"].dropna().astype(str).unique())
        df = self.combat_df
        # print(df.columns)
        # ['round', 'battle_event', 'event_type', 'is_crit', 'attacker_name',
        #  'attacker_ship', 'attacker_alliance', 'attacker_is_armada',
        #  'target_name', 'target_ship', 'target_alliance', 'target_is_armada',
        #  'applied_damage', 'damage_after_apex', 'shield_damage', 'hull_damage',
        #  'mitigated_apex', 'damage_before_apex', 'apex_r', 'apex_barrier_hit',
        #  'total_iso', 'mitigated_iso', 'iso_remain', 'total_normal',
        #  'mitigated_normal', 'normal_remain', 'remain_before_apex',
        #  'accounting_delta', 'ability_type', 'ability_value', 'ability_name',
        #  'ability_owner_name', 'target_defeated', 'target_destroyed',
        #  'Hyperthermic Decay %', 'Hyperthermic Stablizer %',
        #  # 'Charging Weapons %', 'shot_index']
        combatants.update(set(df["attacker_name"].dropna().astype(str).unique()))
        return combatants

    def alliance_names(self) -> Set[str]:
        # mask = (df["Type"] == "Officer Ability") & (df["Attacker Name"] == "XanOfHanoi")
        df = self.combat_df
        combatants = set(df["attacker_alliance"].dropna().astype(str).unique())
        return combatants
