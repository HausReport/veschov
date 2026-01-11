"""Streamlit UI for Apex Barrier per shot POC."""

from __future__ import annotations

import logging

from veschov.ui.object_reports.ApexBarrierReport import ApexBarrierReport

logger = logging.getLogger(__name__)


def render_apex_barrier_poc() -> None:
    """Render the Apex Barrier report."""
    report = ApexBarrierReport()
    report.render()
