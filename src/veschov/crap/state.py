# """Session state helpers for Streamlit pages."""
#
# from __future__ import annotations
#
# import logging
#
# logger = logging.getLogger(__name__)
#
# import pandas as pd
# import streamlit as st
#
#
# def get_battle_df_or_stop(key: str = "battle_df") -> pd.DataFrame:
#     df = st.session_state.get(key)
#     if df is None:
#         st.info("Upload a battle log file first.")
#         st.stop()
#     return df
