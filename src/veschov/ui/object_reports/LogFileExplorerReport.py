"""Streamlit UI for log file explorer tables."""

from __future__ import annotations

import logging
from datetime import datetime

import pandas as pd
import streamlit as st
from st_aggrid import AgGrid, GridOptionsBuilder, JsCode

from veschov.ui.object_reports.AbstractReport import AbstractReport
from veschov.ui.chirality import Lens

logger = logging.getLogger(__name__)

DATE_FORMAT = "%d %b %Y %H:%M"
NULL_DISPLAY = "—"


class LogFileExplorerReport(AbstractReport):
    """Render the Log File Explorer report."""

    def __init__(self) -> None:
        self._battle_df: pd.DataFrame | None = None
        self._players_df: pd.DataFrame | None = None
        self._fleets_df: pd.DataFrame | None = None
        self._loot_df: pd.DataFrame | None = None

    def get_under_title_text(self) -> str | None:
        return (
            "Explore the parsed battle log tables in an Excel-style, read-only grid. "
            "Players and fleets are transposed for readability."
        )

    def get_under_chart_text(self) -> str | None:
        return None

    def get_log_title(self) -> str:
        return "Log File Explorer"

    def get_log_description(self) -> str:
        return "Upload a battle log to explore the parsed tables."

    def render_header(self, df: pd.DataFrame) -> Lens | None:
        return None

    def get_derived_dataframes(
            self,
            df: pd.DataFrame,
            lens: Lens | None,
    ) -> list[pd.DataFrame] | None:
        del lens
        self._battle_df = df
        self._players_df = df.attrs.get("players_df")
        self._fleets_df = df.attrs.get("fleets_df")
        self._loot_df = df.attrs.get("loot_df")
        return [df]

    def display_plots(self, dfs: list[pd.DataFrame]) -> None:
        return None

    def display_tables(self, dfs: list[pd.DataFrame]) -> None:
        del dfs
        tabs = st.tabs(["Battle", "Players", "Fleets", "Loot"])
        with tabs[0]:
            self._render_battle_tab()
        with tabs[1]:
            self._render_transposed_tab(self._players_df, "Players", "logexplorer_players")
        with tabs[2]:
            self._render_transposed_tab(self._fleets_df, "Fleets", "logexplorer_fleets")
        with tabs[3]:
            self._render_loot_tab()

    def render_debug_info(self, dfs: list[pd.DataFrame]) -> None:
        return None

    def get_x_axis_text(self) -> str | None:
        return None

    def get_y_axis_text(self) -> str | None:
        return None

    def get_title_text(self) -> str | None:
        return None

    def _render_battle_tab(self) -> None:
        if not isinstance(self._battle_df, pd.DataFrame):
            logger.warning("Log File Explorer missing battle_df.")
            st.info("Battle data is not available.")
            return
        self._render_dataframe(
            self._battle_df,
            key="logexplorer_battle",
            hidden_columns=[],
            transposed=False,
        )

    def _render_loot_tab(self) -> None:
        if not isinstance(self._loot_df, pd.DataFrame):
            logger.warning("Log File Explorer missing loot_df.")
            st.info("Loot data is not available.")
            return
        self._render_dataframe(
            self._loot_df,
            key="logexplorer_loot",
            hidden_columns=[],
            transposed=False,
        )

    def _render_transposed_tab(self, df: pd.DataFrame | None, label: str, key: str) -> None:
        if not isinstance(df, pd.DataFrame):
            logger.warning("Log File Explorer missing %s data.", label.lower())
            st.info(f"{label} data is not available.")
            return
        transposed = self._transpose_dataframe(df)
        display_df = self._format_transposed_dataframe(transposed)
        self._render_dataframe(
            display_df,
            key=key,
            hidden_columns=[],
            transposed=True,
        )

    def _transpose_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        df_t = df.copy().T.reset_index()
        return df_t.rename(columns={"index": "field"})

    def _format_transposed_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        formatted = df.copy()
        for column in formatted.columns:
            formatted[column] = formatted[column].map(self._format_cell_value)
        return formatted

    def _format_cell_value(self, value: object) -> str:
        if pd.isna(value):
            return NULL_DISPLAY
        if isinstance(value, bool):
            return str(value)
        if isinstance(value, (pd.Timestamp, datetime)):
            return value.strftime(DATE_FORMAT)
        numeric = pd.to_numeric(value, errors="coerce")
        if pd.notna(numeric):
            if float(numeric).is_integer():
                return f"{int(numeric):,}"
            return f"{numeric:,}"
        text = str(value).strip()
        return text or NULL_DISPLAY

    def _render_dataframe(
            self,
            df: pd.DataFrame,
            *,
            key: str,
            hidden_columns: list[str],
            transposed: bool,
    ) -> None:
        safe_df = self._strip_dataframe_attrs(df)
        grid_options = self._build_grid_options(safe_df, hidden_columns, transposed=transposed)
        AgGrid(
            safe_df,
            gridOptions=grid_options,
            height=400,
            key=key,
            allow_unsafe_jscode=True,
            enable_enterprise_modules=True,
            fit_columns_on_grid_load=True,
        )

    def _build_grid_options(
            self,
            df: pd.DataFrame,
            hidden_columns: list[str],
            *,
            transposed: bool,
    ) -> dict[str, object]:
        builder = GridOptionsBuilder.from_dataframe(df)
        builder.configure_default_column(
            editable=False,
            sortable=True,
            filter=True,
            resizable=True,
        )
        builder.configure_grid_options(
            enableRangeSelection=True,
            sideBar=True,
            suppressColumnVirtualisation=False,
        )
        builder.configure_pagination(paginationAutoPageSize=False, paginationPageSize=25)

        if transposed:
            builder.configure_column("field", header_name="field", pinned="left")

        for column in df.columns:
            column_def: dict[str, object] = {}
            if column in hidden_columns:
                column_def["hide"] = True

            if transposed:
                column_def["valueFormatter"] = JsCode(self._build_generic_value_formatter())
                builder.configure_column(column, **column_def)
                continue

            if self._is_datetime_column(df[column]):
                column_def["valueFormatter"] = JsCode(self._build_datetime_formatter())
            elif self._is_bool_column(df[column]):
                column_def["cellRenderer"] = "agCheckboxCellRenderer"
                column_def["filter"] = "agSetColumnFilter"
            elif self._is_numeric_column(df[column]):
                column_def["valueFormatter"] = JsCode(self._build_numeric_formatter())
            else:
                column_def["valueFormatter"] = JsCode(self._build_generic_value_formatter())
            builder.configure_column(column, **column_def)

        return builder.build()

    def _strip_dataframe_attrs(self, df: pd.DataFrame) -> pd.DataFrame:
        safe_df = df.copy()
        safe_df.attrs = {}
        return safe_df

    def _is_datetime_column(self, series: pd.Series) -> bool:
        return pd.api.types.is_datetime64_any_dtype(series)

    def _is_bool_column(self, series: pd.Series) -> bool:
        return pd.api.types.is_bool_dtype(series)

    def _is_numeric_column(self, series: pd.Series) -> bool:
        return pd.api.types.is_numeric_dtype(series)

    def _build_numeric_formatter(self) -> str:
        return f"""
        function(params) {{
            const value = params.value;
            if (value === null || value === undefined || value === '') {{
                return '{NULL_DISPLAY}';
            }}
            if (typeof value === 'number') {{
                return value.toLocaleString('en-US');
            }}
            const parsed = Number(value);
            if (!Number.isNaN(parsed)) {{
                return parsed.toLocaleString('en-US');
            }}
            return value;
        }}
        """

    def _build_datetime_formatter(self) -> str:
        return f"""
        function(params) {{
            const value = params.value;
            if (value === null || value === undefined || value === '') {{
                return '{NULL_DISPLAY}';
            }}
            const dateValue = new Date(value);
            if (Number.isNaN(dateValue.getTime())) {{
                return value;
            }}
            const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
            const day = String(dateValue.getDate()).padStart(2, '0');
            const month = months[dateValue.getMonth()];
            const year = dateValue.getFullYear();
            const hours = String(dateValue.getHours()).padStart(2, '0');
            const minutes = String(dateValue.getMinutes()).padStart(2, '0');
            return `${day} ${month} ${year} ${hours}:${minutes}`;
        }}
        """

    def _build_generic_value_formatter(self) -> str:
        return f"""
        function(params) {{
            const value = params.value;
            if (value === null || value === undefined || value === '') {{
                return '{NULL_DISPLAY}';
            }}
            return value;
        }}
        """


def render_log_file_explorer_report() -> None:
    """Render the Log File Explorer report."""
    report = LogFileExplorerReport()
    report.render()
