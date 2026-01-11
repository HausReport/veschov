from __future__ import annotations
from abc import ABC, abstractmethod

import pandas as pd
import streamlit as st
from veschov.io.parser_stub import parse_battle_log
from veschov.ui.components.combat_log_header import render_sidebar_combat_log_upload
from typing import Iterable, Optional
import pandas as pd
import plotly.express as px

class AbstractReport(ABC):


    def render(self) ->None:
        utt = self.get_under_title_text()
        if utt is not None:
            st.markdown(utt, unsafe_allow_html=True)
        df = self.add_log_uploader()
        if df is None:
            return
        dfs = self.get_derived_dataframes(df)
        if dfs is None:
            return
        self.display_plots(dfs)
        utt = self.get_under_chart_text()
        if utt is not None:
            st.markdown(utt, unsafe_allow_html=True)
        self.display_tables(dfs)



    @abstractmethod
    def get_under_title_text(self) -> Optional[str]:
        return None

    @abstractmethod
    def get_under_chart_text(self) -> Optional[str]:
        return None

    def add_log_uploader(self, title, description) -> Optional[pd.DataFrame]:
        df = render_sidebar_combat_log_upload(
            title=title,
            description=description,
            parser=parse_battle_log
        )
        if df is None:
            st.info("No battle data loaded yet.")
        return df

    @abstractmethod
    def get_derived_dataframes(self, df: pd.DataFrame) -> Optional[list[pd.DataFrame]]:
        pass


    @abstractmethod
    def display_plots(self, dfs: list[pd.DataFrame] ) -> None:
        pass

    @abstractmethod
    def display_tables(self, dfs: list[pd.DataFrame]) -> None:
        pass

    @abstractmethod
    def get_debug_info(self, df: pd.DataFrame) -> None:
        pass

    @abstractmethod
    def get_x_axis_text(self) -> Optional[str]:
        return None

    @abstractmethod
    def get_y_axis_text(self) -> Optional[str]:
        return None

    @abstractmethod
    def get_title_text(self) -> Optional[str]:
        return None
