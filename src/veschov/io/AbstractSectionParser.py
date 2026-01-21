from __future__ import annotations

import logging
from abc import ABC, abstractmethod

import pandas as pd

from veschov.io.StartsWhen import NA_TOKENS

logger = logging.getLogger(__name__)


class AbstractSectionParser(ABC):
    """Base class for parsing sections of a battle log export."""

    @abstractmethod
    def parse_section(self, text: str, sections: dict[str, str]) -> pd.DataFrame:
        """Parse and return a dataframe for the target section."""

    def post_process(self, df: pd.DataFrame, context: dict[str, object]) -> pd.DataFrame:
        """Optionally post-process a parsed dataframe with shared context."""
        return df

    @staticmethod
    def _normalize_dataframe(df: pd.DataFrame) -> pd.DataFrame:
        """Trim string values and coerce explicit NA tokens to pandas NA."""
        cleaned = df.copy()
        for column in cleaned.columns:
            if pd.api.types.is_object_dtype(cleaned[column]) or pd.api.types.is_string_dtype(
                cleaned[column]
            ):
                cleaned[column] = cleaned[column].astype("string").str.strip()
        cleaned = cleaned.replace(list(NA_TOKENS), pd.NA)
        return cleaned

    @staticmethod
    def _coerce_numeric_columns(
        df: pd.DataFrame, columns: tuple[str, ...]
    ) -> pd.DataFrame:
        """Coerce a list of columns to numeric values when present."""
        updated = df.copy()
        for column in columns:
            if column not in updated.columns:
                continue
            cleaned = updated[column].astype("string").str.replace(",", "", regex=False
            ).str.strip()
            updated[column] = pd.to_numeric(cleaned, errors="coerce")
        return updated

    @staticmethod
    def _coerce_yes_no_columns(
        df: pd.DataFrame, columns: tuple[str, ...]
    ) -> pd.DataFrame:
        """Map YES/NO text to boolean values when present."""
        updated = df.copy()
        for column in columns:
            if column not in updated.columns:
                continue
            cleaned = updated[column].astype("string").str.strip().str.upper()
            updated[column] = cleaned.map({"YES": True, "NO": False}).astype("boolean")
        return updated
