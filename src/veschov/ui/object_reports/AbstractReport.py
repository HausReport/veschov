from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional
import pandas as pd
import streamlit as st

from veschov.io.parser_stub import parse_battle_log
from veschov.ui.chirality import Lens
from veschov.ui.components.combat_log_upload import render_sidebar_combat_log_upload
from veschov.ui.components.number_format import format_number


class AbstractReport(ABC):
    """Shared lifecycle for combat-log reports.

    Reports follow the same rendering pipeline:
    1. Optional introductory Markdown under the title.
    2. Sidebar upload of a combat log, parsed into a dataframe.
    3. Header controls to establish context (e.g., lens selection).
    4. Derived dataframes for charts/tables.
    5. Chart, caption, and table output.
    6. Optional debug output for power users.

    Subclasses override the template methods to customize each step.
    """
    lens: Lens | None

    def render(self) -> None:
        """Run the full report lifecycle using the template methods."""
        utt = self.get_under_title_text()
        # st.warning("This page is using the new system.")
        if utt is not None:
            st.markdown(utt, unsafe_allow_html=True)
        df = self.add_log_uploader(
            title=self.get_log_title(),
            description=self.get_log_description(),
        )
        if df is None:
            return
        self.lens = self.render_header(df)
        dfs = self.get_derived_dataframes(df, self.lens)
        if dfs is None:
            return
        self.display_above_plots(dfs)
        self.display_plots(dfs)
        self.display_under_chart()
        self.display_tables(dfs)
        self.render_debug_info(dfs)

    def display_above_plots(self, dfs: list[pd.DataFrame]) -> None:
        """Render optional summary text or metadata above the plot area."""
        return None

    def display_under_chart(self) -> None:
        """Render optional descriptive text beneath the main chart."""
        utt = self.get_under_chart_text()
        if utt is not None:
            st.markdown(utt, unsafe_allow_html=True)

    @abstractmethod
    def get_under_title_text(self) -> Optional[str]:
        """Return optional Markdown shown beneath the page title."""
        return None

    @abstractmethod
    def get_under_chart_text(self) -> Optional[str]:
        """Return optional Markdown shown beneath the chart section."""
        return None

    @abstractmethod
    def get_log_title(self) -> str:
        """Return the sidebar title for the combat log uploader."""
        return ""

    @abstractmethod
    def get_log_description(self) -> str:
        """Return the sidebar description for the combat log uploader."""
        return ""

    def add_log_uploader(self, *, title: str, description: str) -> Optional[pd.DataFrame]:
        """Render the log uploader and parse the battle log into a dataframe."""
        df = render_sidebar_combat_log_upload(
            title=title,
            description=description,
            parser=parse_battle_log
        )
        if df is None:
            st.info("No battle data loaded yet.")
        return df

    @abstractmethod
    def render_header(self, df: pd.DataFrame) -> Lens | None:
        """Render header controls and return the chosen lens, if any."""
        pass

    @abstractmethod
    def get_derived_dataframes(
            self,
            df: pd.DataFrame,
            lens: Lens | None,
    ) -> Optional[list[pd.DataFrame]]:
        """Produce report-specific dataframes derived from the raw log."""
        pass

    def get_plot_titles(self) -> list[str]:
        return ["Plot Title"]

    @abstractmethod
    def display_plots(self, dfs: list[pd.DataFrame]) -> None:
        """Render the main charts for the report."""
        pass

    @abstractmethod
    def display_tables(self, dfs: list[pd.DataFrame]) -> None:
        """Render any supporting tables beneath the charts."""
        pass

    @abstractmethod
    def render_debug_info(self, dfs: list[pd.DataFrame]) -> None:
        """Render optional debug output used during report development."""
        pass

    @abstractmethod
    def get_x_axis_text(self) -> Optional[str]:
        """Return optional x-axis label text for charts."""
        return None

    @abstractmethod
    def get_y_axis_text(self) -> Optional[str]:
        """Return optional y-axis label text for charts."""
        return None

    @abstractmethod
    def get_title_text(self) -> Optional[str]:
        """Return the main title text for the report page."""
        return None

    def _format_large_number(self, value: object, number_format: str) -> str:
        return format_number(value, number_format=number_format, humanize_format="%.1f")

    def _format_large_number_series(
            self,
            series: pd.Series,
            number_format: str,
    ) -> pd.Series:
        """Format a series of values with the configured large-number formatter."""
        return series.map(lambda value: self._format_large_number(value, number_format))
