import logging
from typing import Optional, override

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from veschov.ui.chirality import Lens
from veschov.ui.object_reports.AbstractReport import AbstractReport
from veschov.ui.object_reports.RoundOrShotsReport import RoundOrShotsReport
from veschov.ui.pretty_stats.Statistic import Statistic

logger = logging.getLogger(__name__)

# Color Palette for the "Gamer-Nerd" Aesthetic
BASE_HIT_COLOR = "#7f7f7f"  # Gray for standard hits
CRIT_POINT_COLOR = "#1f77b4"  # Blue for individual crits
SMOOTHED_LINE_COLOR = "#d62728"  # Red for the "True Power" trend
CI_FILL_COLOR = "rgba(31, 119, 180, 0.15)"  # Soft blue for the "Luck Zone"


class CritMultiplierTrendsReport(RoundOrShotsReport):
    """
    Renders a report analyzing the magnitude of Critical Hits (The Multiplier)
    over the course of a battle.
    """
    VIEW_BY_KEY = "crit_multiplier_trends_view_by"
    under_title_text = "This report analyzes your **Damage Multiplier**—the ratio of Crit Damage to "
    "standard hits. It helps you see if your crits are consistently hitting "
    "their theoretical maximum or if 'Mini-Crits' are dragging down your DPS."
    under_chart_text = "**How to read this:** The **Red Line** is your smoothed average power. "
    "The **Blue Band** is the 'Confidence Zone'—as long as the red line is inside it, "
    "your performance is statistically normal. If it dips below, you're hitting 'wet noodle' crits."
    x_axis_text = "x-axis title"
    y_axis_text = "y-axis-text"
    title_text = "Crit Multiplier & Power Trends"
    lens_key = f"key_crit_multiplier_{AbstractReport.key_suffix}"
    Z_SCORE = 1.96  # 95% Confidence

    def __init__(self) -> None:
        super().__init__()
        self.title = "Critical Multiplier Power"
        self.x_axis = "shot_index_global"

    @override
    def get_derived_dataframes(self, df: pd.DataFrame, lens: Lens | None) -> Optional[list[pd.DataFrame]]:
        display_df = df.copy()

        # 1. Standard Attack Filtering (from example)
        typ = display_df["event_type"].astype("string").str.strip().str.lower()
        total_normal = display_df["total_normal"].fillna(0)
        total_iso = display_df["total_iso"].fillna(0)

        # Only rows with 'attack' type and non-zero damage
        attack_mask = typ.eq("attack") & ((total_normal + total_iso) > 0)
        shot_df = display_df.loc[attack_mask].copy()

        # 2. Sort for Chronological Accuracy
        if "battle_event" in shot_df.columns:
            shot_df = shot_df.sort_values("battle_event", kind="stable")

        # 3. Apply the Attacker/Target Lens
        # This filters the DF based on the UI selections for Attacker/Target
        shot_df = self.apply_combat_lens(shot_df, lens)

        if shot_df.empty:
            logger.warning("No matching attack events found for this selection.")
            st.warning("No matching attack events found for this selection.")
            return None

        # Resolve view mode (Round vs Shot)
        self.view_by = self._resolve_view_by()

        # 2. Establish the Baseline (Expected Base Damage)
        # We calculate a cumulative average of non-crits to find the 'Standard Hit'
        nc_mask = ~shot_df['is_crit'] & (shot_df['total_normal'] > 0)
        shot_df['nc_val'] = np.where(nc_mask, shot_df['total_normal'], np.nan)
        shot_df['expected_base'] = shot_df['nc_val'].expanding().mean().ffill().bfill()

        # 3. Calculate the Multiplier for every Crit
        shot_df['multiplier'] = np.where(
            shot_df['is_crit'],
            shot_df['total_normal'] / shot_df['expected_base'],
            np.nan
        )

        # 4. Multiplier Math & View Building
        # Build the specific DF for the plot based on the toggled view
        if self.view_by == "Round":
            round_df = self._build_multiplier_round_df(shot_df)
            return [round_df, shot_df] if round_df is not None else None

        shot_view_df = self._build_multiplier_shot_df(shot_df)
        return [shot_view_df, shot_df] if shot_view_df is not None else None

    def _build_multiplier_shot_df(self, df: pd.DataFrame) -> pd.DataFrame:
        """Global Shot View: Shows every crit's impact."""
        crit_only = df[df['is_crit']].copy()
        crit_only['shot_index_global'] = range(1, len(crit_only) + 1)

        # Statistical smoothing
        crit_only['smoothed'] = crit_only['multiplier'].rolling(window=5, center=True).mean().fillna(
            method='ffill').fillna(method='bfill')

        # Simplified Confidence Band based on Standard Error
        std_err = crit_only['multiplier'].expanding().std().fillna(0) / np.sqrt(crit_only['shot_index_global'])
        crit_only['ci_upper'] = crit_only['multiplier'].expanding().mean() + (self.Z_SCORE * std_err)
        crit_only['ci_lower'] = crit_only['multiplier'].expanding().mean() - (self.Z_SCORE * std_err)

        return crit_only

    def _build_multiplier_round_df(self, df: pd.DataFrame) -> pd.DataFrame:
        """Round View: Groups multipliers to show round-over-round performance."""
        round_stats = df[df['is_crit']].groupby('round').agg(
            multiplier=('multiplier', 'mean'),
            crit_count=('is_crit', 'count')
        ).reset_index()

        round_stats['smoothed'] = round_stats['multiplier'].rolling(window=3, center=True).mean().fillna(
            method='ffill').fillna(method='bfill')

        # Confidence logic for rounds
        global_mean = round_stats['multiplier'].mean()
        global_std = round_stats['multiplier'].std()
        round_stats['ci_upper'] = global_mean + (self.Z_SCORE * (global_std / np.sqrt(round_stats['crit_count'])))
        round_stats['ci_lower'] = global_mean - (self.Z_SCORE * (global_std / np.sqrt(round_stats['crit_count'])))

        return round_stats

    @override
    def display_plots(self, dfs: list[pd.DataFrame]) -> None:
        plot_df = dfs[0]
        x_col = "round" if self.view_by == "Round" else "shot_index_global"

        fig = go.Figure()

        # 1. The Confidence "Luck Zone"
        fig.add_trace(go.Scatter(
            x=plot_df[x_col], y=plot_df['ci_upper'], mode='lines',
            line=dict(width=0), showlegend=False, hoverinfo='skip'
        ))
        fig.add_trace(go.Scatter(
            x=plot_df[x_col], y=plot_df['ci_lower'], mode='lines',
            fill='tonexty', fillcolor=CI_FILL_COLOR, line=dict(width=0),
            name="95% Power Expectation"
        ))

        # 2. Raw Data Points
        fig.add_trace(go.Scatter(
            x=plot_df[x_col], y=plot_df['multiplier'],
            mode='markers', name="Actual Crit Power",
            marker=dict(color=CRIT_POINT_COLOR, size=8, opacity=0.6),
            hovertemplate="Round: %{x}<br>Multiplier: %{y:.2f}x<extra></extra>"
        ))

        # 3. Smoothed Trend Line
        fig.add_trace(go.Scatter(
            x=plot_df[x_col], y=plot_df['smoothed'],
            mode='lines', name="Performance Trend",
            line=dict(color=SMOOTHED_LINE_COLOR, width=3)
        ))

        # 4. The 1.0x "Standard Hit" Baseline
        fig.add_hline(y=1.0, line_dash="dash", line_color=BASE_HIT_COLOR,
                      annotation_text="Standard Hit (1.0x)")

        fig.update_layout(
            xaxis_title="Battle Progression (" + self.view_by + ")",
            yaxis_title="Multiplier (x Base Damage)",
            hovermode="x unified",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )

        st.plotly_chart(fig, use_container_width=True)

    @override
    def get_descriptive_statistics(self) -> list[Statistic]:
        # Implementation of gamer-friendly top-line stats (Mean Multiplier, Max Multiplier)
        return []
