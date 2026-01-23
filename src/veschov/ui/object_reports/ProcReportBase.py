"""Shared helpers and base class for officer/tech proc reports."""

from __future__ import annotations

import logging
from typing import Iterable, Optional

import pandas as pd
import streamlit as st

from veschov.ui.object_reports.AttackerAndTargetReport import AttackerAndTargetReport

logger = logging.getLogger(__name__)

PROC_TYPES: tuple[str, ...] = (
    "Officer",
    "ForbiddenTechAbility",
)
REQUIRED_COLUMNS: tuple[str, ...] = (
    "ability_name",
    "ability_value",
    "ability_owner_name",
    "event_type",
    "round",
)
COLUMN_ALIASES: dict[str, tuple[str, ...]] = {
    "round": ("round", "Round"),
    "event_type": ("event_type", "Type", "type", "Ability Type", "ability_type"),
    "ability_owner_name": (
        "ability_owner_name",
        "Ability Owner Name",
        "Ability Owner",
    ),
    "ability_name": ("ability_name", "Ability Name"),
    "ability_value": ("ability_value", "Ability Value"),
}


def _resolve_column(df: pd.DataFrame, candidates: Iterable[str]) -> str | None:
    """Return the first matching column name in the dataframe."""
    return next((candidate for candidate in candidates if candidate in df.columns), None)


def _normalize_required_columns(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """Normalize required columns and return missing column names."""
    updated = df.copy()
    missing = []
    for canonical, candidates in COLUMN_ALIASES.items():
        resolved = _resolve_column(updated, candidates)
        if resolved is None:
            missing.append(canonical)
            continue
        if resolved != canonical:
            updated = updated.rename(columns={resolved: canonical})
    return updated, missing


def _debug_proc_counts(label: str, df: pd.DataFrame) -> None:
    """Emit debug information about filtered proc rows."""
    if "event_type" not in df.columns:
        logger.debug("%s: event_type column missing; rows=%s", label, len(df))
        return
    event_types = df["event_type"].fillna("").astype(str).str.strip()
    proc_rows = event_types.isin(PROC_TYPES).sum()
    logger.debug("%s: rows=%s proc_rows=%s", label, len(df), proc_rows)


def _coerce_numeric(series: pd.Series) -> pd.Series:
    """Coerce a series to numeric values, ignoring errors."""
    cleaned = series.astype(str).str.replace(",", "", regex=False).str.strip()
    return pd.to_numeric(cleaned, errors="coerce")


def _normalize_round(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize round values to consistent sorting."""
    updated = df.copy()
    round_series = updated["round"]
    round_numeric = _coerce_numeric(round_series)
    if round_numeric.notna().sum() == round_series.notna().sum() and round_series.notna().any():
        updated["round"] = round_numeric.astype("Int64")
    else:
        round_values = round_series.fillna("Unknown").astype(str)
        categories = sorted(round_values.unique())
        updated["round"] = pd.Categorical(round_values, categories=categories, ordered=True)
    return updated


def _normalize_proc_labels(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize owner/ability labels for display."""
    updated = df.copy()
    owner = updated["ability_owner_name"].fillna("Unknown").astype(str).str.strip()
    owner = owner.replace("", "Unknown")

    ability = updated["ability_name"].fillna("--").astype(str).str.strip()
    ability = ability.replace("", "--")
    missing_ability = ability.isin(("", "--"))

    value_series = updated["ability_value"].where(updated["ability_value"].notna(), None)
    value_label = value_series.apply(lambda value: str(value).strip() if value is not None else "")
    fallback_label = value_label.where(value_label != "", "Unknown")
    ability = ability.where(~missing_ability, fallback_label)

    updated["owner"] = owner
    updated["ability"] = ability
    return updated


@st.cache_data(show_spinner=False)
def _get_proc_df(battle_df: pd.DataFrame, include_forbidden_tech: bool) -> pd.DataFrame:
    """Return a normalized dataframe for officer/tech proc rows."""
    if "event_type" not in battle_df.columns:
        logger.warning("event_type column missing before filtering")
        return pd.DataFrame()
    if not battle_df["event_type"].notna().any():
        logger.warning("event_type column has no non-null values")
        return pd.DataFrame()
    allowed_types = PROC_TYPES if include_forbidden_tech else (PROC_TYPES[0],)
    event_type_values = battle_df["event_type"].fillna("").astype(str).str.strip()
    filtered = battle_df[event_type_values.isin(allowed_types)].copy()
    logger.debug("_get_proc_df: after event_type filter row count=%s", len(filtered))
    if filtered.empty:
        return filtered
    filtered = _normalize_round(filtered)
    logger.debug("_get_proc_df: after _normalize_round row count=%s", len(filtered))
    filtered = _normalize_proc_labels(filtered)
    logger.debug("_get_proc_df: after _normalize_proc_labels row count=%s", len(filtered))
    return filtered


@st.cache_data(show_spinner=False)
def build_proc_matrix(
        battle_df: pd.DataFrame,
        include_forbidden_tech: bool,
        show_totals: bool,
        show_distinct: bool,
        owner_filter: tuple[str, ...] | None = None,
) -> pd.DataFrame:
    """Build a round-by-owner matrix of proc counts."""
    proc_df = _get_proc_df(battle_df, include_forbidden_tech)
    if owner_filter:
        proc_df = proc_df[proc_df["owner"].isin(owner_filter)]

    if proc_df.empty:
        return pd.DataFrame()

    counts = proc_df.groupby(["round", "owner", "ability"], dropna=False).size()
    matrix = counts.unstack(["owner", "ability"]).fillna(0).astype(int)
    matrix = matrix.sort_index(axis=1).sort_index(axis=0)

    proc_matrix = matrix.copy()
    if show_totals:
        totals = proc_matrix.sum(axis=1)
        matrix.insert(0, ("", "All Procs"), totals)
    if show_distinct:
        distinct = (proc_matrix > 0).sum(axis=1)
        insert_pos = 0 if not show_totals else 1
        matrix.insert(insert_pos, ("", "Distinct Fired"), distinct)

    return matrix


@st.cache_data(show_spinner=False)
def build_proc_summary(
        battle_df: pd.DataFrame,
        include_forbidden_tech: bool,
        owner_filter: tuple[str, ...] | None = None,
) -> pd.DataFrame:
    """Summarize proc totals and rounds active by owner/ability."""
    proc_df = _get_proc_df(battle_df, include_forbidden_tech)
    if owner_filter:
        proc_df = proc_df[proc_df["owner"].isin(owner_filter)]

    if proc_df.empty:
        return pd.DataFrame()

    counts = proc_df.groupby(["round", "owner", "ability"], dropna=False).size()
    matrix = counts.unstack(["owner", "ability"]).fillna(0).astype(int)
    matrix = matrix.sort_index(axis=1).sort_index(axis=0)

    totals = matrix.sum(axis=0)
    rounds_active = (matrix > 0).sum(axis=0)
    avg_per_active = totals / rounds_active.replace(0, pd.NA)
    first_rounds = []
    for column in matrix.columns:
        active = matrix[column][matrix[column] > 0]
        first_rounds.append(active.index[0] if not active.empty else pd.NA)

    summary = pd.DataFrame(
        {
            "Ability Owner": [column[0] for column in matrix.columns],
            "Ability Name": [column[1] for column in matrix.columns],
            "Total fires": totals.values,
            "Rounds active": rounds_active.values,
            "Avg fires per active round": avg_per_active.values,
            "First round fired": first_rounds,
        }
    )
    summary = summary.sort_values("Total fires", ascending=False, kind="stable").reset_index(
        drop=True
    )
    return summary


def style_heatmap(df: pd.DataFrame, heat_cap: int) -> pd.io.formats.style.Styler:
    """Apply heatmap styling for proc counts."""

    def _style_cell(value: object) -> str:
        if pd.isna(value):
            return ""
        try:
            count = int(value)
        except (TypeError, ValueError):
            return ""
        if count <= 0:
            return ""
        intensity = min(count, heat_cap) / heat_cap
        return f"background-color: rgba(255, 140, 0, {intensity:.2f});"

    return df.style.map(_style_cell).format("{:.0f}")


class ProcReportBase(AttackerAndTargetReport):
    """Base report for officer/tech proc analysis."""

    include_forbidden_tech: bool = True

    def get_under_title_text(self) -> Optional[str]:
        return None

    def get_under_chart_text(self) -> Optional[str]:
        return None

    def get_log_description(self) -> str:
        return "Upload a battle log to visualize officer and forbidden tech proc activity."

    def get_lens_key(self) -> str:
        return "officers_tech"

    def get_x_axis_text(self) -> Optional[str]:
        return None

    def get_y_axis_text(self) -> Optional[str]:
        return None

    def get_title_text(self) -> Optional[str]:
        return None

    def get_derived_dataframes(self, df: pd.DataFrame, lens) -> Optional[list[pd.DataFrame]]:
        display_df = df.copy()
        display_df.attrs = {}
        display_df, missing_columns = _normalize_required_columns(display_df)

        if missing_columns:
            st.warning(f"Missing required columns: {', '.join(missing_columns)}")
            return None

        display_df = self.apply_combat_lens(
            display_df,
            lens,
            skip_target_filter_for_procs=True,
        )
        _debug_proc_counts("display_df after lens", display_df)
        return [display_df]

    def display_plots(self, dfs: list[pd.DataFrame]) -> None:
        return None

    def _get_proc_selection(
            self,
            display_df: pd.DataFrame,
    ) -> tuple[pd.DataFrame, tuple[str, ...]] | None:
        proc_df = _get_proc_df(display_df, self.include_forbidden_tech)
        if proc_df.empty:
            st.info("No officer/tech proc rows found for this battle.")
            return None

        owner_options = sorted(proc_df["owner"].dropna().unique().tolist())
        if not owner_options:
            logger.warning("Proc rows found without owner values.")
            st.info("No officer/tech proc owners found for this battle.")
            return None
        return proc_df, tuple(owner_options)

    def get_debug_info(self, df: pd.DataFrame) -> None:
        return None

    def render_debug_info(self, df: pd.DataFrame) -> None:
        pass
