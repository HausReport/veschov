"""Base class for shared helpers used when parsing sectioned battle logs."""

from __future__ import annotations

import logging
from typing import IO, Any

import pandas as pd

from veschov.io.StartsWhen import NA_TOKENS as STARTSWHEN_NA_TOKENS

logger = logging.getLogger(__name__)


class AbstractSectionParser:
    """Provide shared parsing helpers for sectioned battle log exports."""

    NA_TOKENS = STARTSWHEN_NA_TOKENS

    def _read_text(self, file_bytes: bytes | str | IO[Any]) -> str:
        """Return a UTF-8 decoded string from a bytes, str, or file-like input."""
        if isinstance(file_bytes, bytes):
            return file_bytes.decode("utf-8", errors="replace")
        if isinstance(file_bytes, str):
            return file_bytes
        if hasattr(file_bytes, "read"):
            content = file_bytes.read()
            if isinstance(content, bytes):
                return content.decode("utf-8", errors="replace")
            return str(content)
        return str(file_bytes)

    def _normalize_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """Return a cleaned copy of the dataframe with trimmed strings and NA tokens."""
        cleaned = df.copy()
        for column in cleaned.columns:
            if pd.api.types.is_object_dtype(cleaned[column]) or pd.api.types.is_string_dtype(
                cleaned[column]
            ):
                cleaned[column] = cleaned[column].astype("string").str.strip()
        cleaned = cleaned.replace(list(self.NA_TOKENS), pd.NA)
        return cleaned

    def _coerce_numeric_columns(self, df: pd.DataFrame, columns: tuple[str, ...]) -> pd.DataFrame:
        """Return a copy of the dataframe with numeric columns coerced to numbers."""
        updated = df.copy()
        for column in columns:
            if column not in updated.columns:
                continue
            cleaned = updated[column].astype("string").str.replace(",", "", regex=False).str.strip()
            updated[column] = pd.to_numeric(cleaned, errors="coerce")
        return updated

    def _coerce_yes_no_columns(self, df: pd.DataFrame, columns: tuple[str, ...]) -> pd.DataFrame:
        """Return a copy of the dataframe with YES/NO strings mapped to booleans."""
        updated = df.copy()
        for column in columns:
            if column not in updated.columns:
                continue
            cleaned = updated[column].astype("string").str.strip().str.upper()
            updated[column] = cleaned.map({"YES": True, "NO": False}).astype("boolean")
        return updated

    def _numeric_series(self, df: pd.DataFrame, column: str) -> pd.Series:
        """Return a numeric series for a column, defaulting to nullable floats."""
        if column not in df.columns:
            return pd.Series(pd.NA, index=df.index, dtype="Float64")
        return pd.to_numeric(df[column], errors="coerce")

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

    def _align_players_columns(self, source_df: pd.DataFrame, columns: pd.Index) -> pd.DataFrame:
        """Align inferred player data to the export metadata columns."""
        aligned = {
            column: source_df[column] if column in source_df.columns else pd.NA
            for column in columns
        }
        return pd.DataFrame(aligned)

    def _augment_players_df(
        self, players_df: pd.DataFrame, combat_df: pd.DataFrame
    ) -> pd.DataFrame:
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
