from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

from datetime import datetime
from typing import Iterable

import pandas as pd
import plotly.graph_objects as go


def _add_session_spans(fig: go.Figure, sessions: Iterable[dict]) -> None:
    for sess in sessions:
        start = sess.get("clipped_start")
        end = sess.get("clipped_end")
        if pd.isna(start) or pd.isna(end):
            continue
        fig.add_vrect(
            x0=start,
            x1=end,
            fillcolor="blue",
            opacity=0.1,
            line_width=0,
            layer="below",
        )


def build_timeline_figure(
    period_start: datetime,
    period_end: datetime,
    sessions_df: pd.DataFrame,
    attacks_df: pd.DataFrame,
) -> go.Figure:
    """Build a timeline figure with session spans and hull percentage."""
    fig = go.Figure()

    if not sessions_df.empty:
        _add_session_spans(fig, sessions_df.to_dict("records"))

    hull_df = attacks_df.copy()
    if not hull_df.empty and "hull_pct" in hull_df.columns:
        hull_df = hull_df.dropna(subset=["hull_pct"])
    if hull_df is not None and not hull_df.empty:
        fig.add_trace(
            go.Scatter(
                x=hull_df["time"],
                y=hull_df["hull_pct"],
                mode="lines+markers",
                name="Hull %",
            )
        )

    fig.update_layout(
        title=f"Timeline: {period_start.date()} → {period_end.date()}",
        xaxis_title="Time",
        yaxis_title="Hull %",
        yaxis=dict(range=[0, 100]),
        hovermode="x unified",
    )

    fig.update_xaxes(range=[period_start, period_end])

    return fig
