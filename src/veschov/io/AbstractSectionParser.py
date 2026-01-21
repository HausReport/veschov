"""Base class for shared helpers used when parsing sectioned battle logs."""

from __future__ import annotations

import logging
from typing import IO, Any

import pandas as pd

logger = logging.getLogger(__name__)


class AbstractSectionParser:
    """Provide shared parsing helpers for sectioned battle log exports."""

    NA_TOKENS = ("--", "—", "–", "")

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
