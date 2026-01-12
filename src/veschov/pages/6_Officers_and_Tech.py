from __future__ import annotations
import streamlit as st
from veschov.ui.object_reports.OfficersAndTechReport import OfficersAndTechReport


st.set_page_config(page_title="petaQmey je janmey.  Jerks and gizmos.", layout="wide")
# st.title("🖖 Officers & Tech Procs")

report = OfficersAndTechReport()
report.render()
