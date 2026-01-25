from __future__ import annotations

from abc import ABC, abstractmethod
from functools import lru_cache
import logging
from pathlib import Path
from typing import Optional
import pandas as pd
import streamlit as st
import toml
from streamlit.runtime.scriptrunner_utils import script_run_context

from veschov.io.parser_stub import parse_battle_log
from veschov.ui.chirality import Lens
from veschov.ui.components.combat_log_upload import render_sidebar_combat_log_upload
from veschov.ui.components.number_format import format_number
from veschov.ui.pretty_stats.Statistic import Statistic, render_stats

LOGGER = logging.getLogger(__name__)


class AbstractReport(ABC):
    """Shared lifecycle for combat-log reports.

    Reports follow the same rendering pipeline:
    1. Header row with title, under-title Markdown, and optional metadata slot.
    2. Sidebar upload of a combat log, parsed into a dataframe.
    3. Header controls to establish context (e.g., lens selection).
    4. Derived dataframes for charts/tables.
    5. Chart, caption, and table output.
    6. Optional debug output for power users.

    Subclasses override the template methods to customize each step.

    Title emojis are derived automatically from `.streamlit/pages.toml` based on
    the current page script path. Report authors should keep the `get_title_text`
    output free of emoji prefixes unless they want to override the configured
    icon.
    """
    lens: Lens | None
    meta_slot: st.delta_generator.DeltaGenerator | None

    def render(self) -> None:
        """Run the full report lifecycle using the template methods."""
        self.meta_slot = None
        left, right = st.columns([3, 1], vertical_alignment="top")
        with left:
            title_text = self._prepend_page_icon(self.get_title_text())
            if title_text is not None:
                st.title(title_text)
            utt = self.get_under_title_text()
            if utt is not None:
                st.markdown(utt, unsafe_allow_html=True)
        with right:
            self.meta_slot = st.container()
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
        self.fill_meta_slot()
        self.display_above_plots(dfs)
        self.display_plots(dfs)
        self.display_under_chart()
        self.display_tables(dfs)
        self.render_debug_info(dfs)

    def display_above_plots(self, dfs: list[pd.DataFrame]) -> None:
        """Render optional summary text or metadata above the plot area."""
        descriptive_stats = self.get_descriptive_statistics()
        if descriptive_stats:
            render_stats(descriptive_stats)
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
    def get_descriptive_statistics(self) -> list[Statistic]:
        """Return descriptive statistics to render above the plot area."""
        return []

    @abstractmethod
    def get_log_title(self) -> str:
        """Return the sidebar title for the combat log uploader."""
        return ""

    @abstractmethod
    def get_log_description(self) -> str:
        """Return the sidebar description for the combat log uploader."""
        return ""

    @abstractmethod
    def fill_meta_slot(self) -> None:
        """Render optional header metadata in the right-hand slot."""
        return None

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

    def _prepend_page_icon(self, title_text: Optional[str]) -> Optional[str]:
        """Ensure the title includes the page icon from `.streamlit/pages.toml`."""
        if title_text is None:
            return None
        icon = self._get_page_icon()
        if icon is None:
            return title_text
        if title_text.lstrip().startswith(icon):
            return title_text
        return f"{icon} {title_text}"

    def _get_page_icon(self) -> Optional[str]:
        """Look up the current page icon using Streamlit's ScriptRunContext."""
        ctx = script_run_context.get_script_run_ctx()
        if ctx is None:
            LOGGER.warning("Unable to resolve page icon: ScriptRunContext missing.")
            return None
        pages = ctx.pages_manager.get_pages()
        page_info = pages.get(ctx.page_script_hash)
        if page_info is None:
            LOGGER.warning("Unable to resolve page icon: page info missing for hash %s.", ctx.page_script_hash)
            return None
        script_path = page_info.get("script_path")
        if script_path is None:
            LOGGER.warning("Unable to resolve page icon: script path missing for page hash %s.", ctx.page_script_hash)
            return None
        pages_toml_path = self._find_pages_toml(Path(ctx.main_script_path).parent)
        if pages_toml_path is None:
            LOGGER.warning("Unable to resolve page icon: .streamlit/pages.toml not found.")
            return None
        icon_map = self._load_pages_toml_icons(
            str(pages_toml_path),
            str(Path(ctx.main_script_path).parent),
        )
        resolved_script_path = Path(script_path).resolve()
        icon = icon_map.get(resolved_script_path)
        if icon is None:
            LOGGER.warning("No icon configured for page path %s.", resolved_script_path)
        return icon

    @staticmethod
    def _find_pages_toml(start_dir: Path) -> Path | None:
        for parent in [start_dir, *start_dir.parents]:
            candidate = parent / ".streamlit" / "pages.toml"
            if candidate.exists():
                return candidate
        return None

    @staticmethod
    @lru_cache(maxsize=4)
    def _load_pages_toml_icons(pages_toml_path_str: str, main_script_parent_str: str) -> dict[Path, str]:
        pages_toml_path = Path(pages_toml_path_str)
        main_script_parent = Path(main_script_parent_str)
        if not pages_toml_path.exists():
            LOGGER.warning("pages.toml missing at %s", pages_toml_path)
            return {}
        try:
            data = toml.loads(pages_toml_path.read_text(encoding="utf-8"))
        except toml.TomlDecodeError as exc:
            LOGGER.warning("Failed to parse pages.toml at %s: %s", pages_toml_path, exc)
            return {}
        pages = data.get("pages", [])
        if not isinstance(pages, list):
            LOGGER.warning("Unexpected pages.toml format in %s", pages_toml_path)
            return {}
        icon_map: dict[Path, str] = {}
        for page in pages:
            if not isinstance(page, dict):
                continue
            path_value = page.get("path")
            icon_value = page.get("icon")
            if not path_value or not icon_value:
                continue
            resolved_path = (main_script_parent / path_value).resolve()
            icon_map[resolved_path] = icon_value
        return icon_map
