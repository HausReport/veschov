from __future__ import annotations
import streamlit as st
from veschov.ui.object_reports.ApexBarrierReport import ApexBarrierReport

st.set_page_config(page_title="yoD Dung ghaH yoDwIj’e’.  My shield is the apex barrier.", layout="wide")
# st.title("🖖 Apex Barrier Analysis")
report = ApexBarrierReport()
report.render()

