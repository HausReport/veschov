from __future__ import annotations

import logging

import pandas as pd

from veschov.io.AbstractSectionParser import AbstractSectionParser
from veschov.io.StartsWhen import SECTION_HEADERS, section_to_dataframe

logger = logging.getLogger(__name__)


class PlayerSectionParser(AbstractSectionParser):
    """Parse and augment the players section of a battle log."""

    section_key = "players"
    header_prefix = SECTION_HEADERS["players"]

    def parse_section(self, text: str, sections: dict[str, str]) -> pd.DataFrame:
        """Parse the players section and normalize it."""
        section_text = sections.get(self.section_key)
        df = section_to_dataframe(section_text, self.header_prefix)
        return self._normalize_dataframe(df)

    def post_process(self, df: pd.DataFrame, context: dict[str, object]) -> pd.DataFrame:
        """Augment player metadata with combat-derived rows."""
        combat_df = context.get("combat_df")
        if not isinstance(combat_df, pd.DataFrame):
            logger.warning("Player augmentation skipped: combat_df missing in context.")
            return df
        return self._augment_players_df(df, combat_df)

    def _augment_players_df(self, players_df: pd.DataFrame, combat_df: pd.DataFrame) -> pd.DataFrame:
        """Augment player metadata with entries inferred from the combat log."""
        if len(players_df) > 1:
            return players_df

        npc_name = None
        if not players_df.empty:
            npc_name = str(players_df.iloc[-1].get("Player Name") or "").strip() or None

        fallback_df = self._fallback_players_df(combat_df, npc_name)
        if fallback_df.empty:
            return players_df

        aligned_fallback = self._align_players_columns(fallback_df, players_df.columns)
        if players_df.empty:
            return aligned_fallback

        npc_row = players_df.iloc[-1:]
        aligned_fallback = aligned_fallback.dropna(axis="columns", how="all")
        combined = pd.concat([aligned_fallback, npc_row], ignore_index=True)
        return combined.reindex(columns=players_df.columns)

    def _fallback_players_df(
        self, combat_df: pd.DataFrame, npc_name: str | None
    ) -> pd.DataFrame:
        """Return player rows inferred from combat data when player metadata is missing."""
        required_columns = {
            "attacker_name",
            "attacker_ship",
            "target_name",
            "target_ship",
        }
        if not required_columns.issubset(combat_df.columns):
            return pd.DataFrame(columns=["Player Name", "Ship Name"])

        frames: list[pd.DataFrame] = []
        for name_col, ship_col in (
            ("attacker_name", "attacker_ship"),
            ("target_name", "target_ship"),
        ):
            subset = (
                combat_df.loc[:, [name_col, ship_col]]
                .dropna(how="all")
                .fillna("")
                .astype(str)
                .rename(columns={name_col: "Player Name", ship_col: "Ship Name"})
            )
            frames.append(subset)

        combined = pd.concat(frames, ignore_index=True).drop_duplicates().reset_index(drop=True)
        if npc_name:
            combined = combined[combined["Player Name"].str.strip() != npc_name]

        combined = combined[
            (combined["Player Name"].str.strip() != "")
            | (combined["Ship Name"].str.strip() != "")
        ]
        combined = combined.replace({"": pd.NA})
        return combined.loc[:, ["Player Name", "Ship Name"]].reset_index(drop=True)

    @staticmethod
    def _align_players_columns(source_df: pd.DataFrame, columns: pd.Index) -> pd.DataFrame:
        """Align inferred player data to the export metadata columns."""
        aligned = {
            column: source_df[column] if column in source_df.columns else pd.NA
            for column in columns
        }
        return pd.DataFrame(aligned)
