"""Streamlit UI for critical hit rate analysis."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

import pandas as pd
import plotly.express as px
import streamlit as st

from veschov.io.parser_stub import parse_battle_log
from veschov.ui.components.combat_log_header import (
    apply_combat_lens,
    render_combat_log_header,
    render_sidebar_combat_log_upload,
)
from veschov.ui.view_by import prepare_round_view, select_view_by
from veschov.utils.series import coerce_numeric


NON_CRIT_LABEL = "Non-critical hits"
CRIT_LABEL = "Critical hits"


def _build_attack_mask(df: pd.DataFrame) -> pd.Series:
    if "event_type" not in df.columns:
        raise KeyError("event_type")
    typ = df["event_type"].astype(str).str.strip().str.lower()
    mask = typ == "attack"
    if "total_normal" in df.columns or "total_iso" in df.columns:
        total_normal = coerce_numeric(df.get("total_normal", pd.Series(0, index=df.index)))
        total_iso = coerce_numeric(df.get("total_iso", pd.Series(0, index=df.index)))
        mask &= (total_normal > 0) | (total_iso > 0)
    return mask


def _format_average_shots(shot_df: pd.DataFrame) -> str:
    if "round" not in shot_df.columns:
        return "Average shots/round: N/A (round data missing)."
    round_series = coerce_numeric(shot_df["round"])
    valid_rounds = shot_df.loc[round_series.notna()].copy()
    if valid_rounds.empty:
        return "Average shots/round: N/A (round data missing)."
    valid_rounds = valid_rounds.assign(round=round_series.loc[round_series.notna()].astype(int))
    counts = valid_rounds.groupby("round").size()
    average = counts.mean()
    return f"Average shots/round: {average:.2f}."


def render_crit_hit_report() -> None:
    """Render the critical hit report."""
    st.markdown(
        "Hits per Round summarizes attack volume by shot or round, split into critical and "
        "non-critical hits."
    )

    df = render_sidebar_combat_log_upload(
        "Hits per Round",
        "Upload a battle log to visualize crit vs non-crit hit counts per shot or round.",
        parser=parse_battle_log,
    )
    if df is None:
        st.info("No battle data loaded yet.")
        return

    battle_filename = st.session_state.get("battle_filename") or "Session battle data"

    players_df = df.attrs.get("players_df")
    fleets_df = df.attrs.get("fleets_df")
    _, lens = render_combat_log_header(
        players_df,
        fleets_df,
        df,
        lens_key="crit_hit",
    )

    display_df = df.copy()
    display_df.attrs = {}

    required_columns = ("event_type", "is_crit")
    missing_columns = [col for col in required_columns if col not in display_df.columns]
    if missing_columns:
        st.error(f"Missing required columns: {', '.join(missing_columns)}")
        return

    try:
        attack_mask = _build_attack_mask(display_df)
    except KeyError as exc:
        st.error(f"Missing required column: {exc.args[0]}")
        return

    shot_df = display_df.loc[attack_mask].copy()
    if "battle_event" in shot_df.columns:
        shot_df = shot_df.sort_values("battle_event", kind="stable")

    shot_df = apply_combat_lens(shot_df, lens)

    if shot_df.empty:
        st.warning("No matching attack events found for this selection.")
        return

    crit_flags = shot_df["is_crit"].fillna(False).astype(bool)
    total_shots = int(len(shot_df))
    crit_shots = int(crit_flags.sum())
    crit_rate = crit_shots / total_shots if total_shots else 0.0

    st.markdown(
        f"**Overall critical hit chance:** {crit_shots}/{total_shots} ({crit_rate:.1%}). "
        f"{_format_average_shots(shot_df)}"
    )

    view_by = select_view_by("crit_hit_view_by")

    if view_by == "Round":
        round_df = prepare_round_view(shot_df)
        if round_df is None:
            return
        grouped = round_df.groupby(["round", "is_crit"], dropna=False).size().reset_index()
        pivot = grouped.pivot_table(
            index="round",
            columns="is_crit",
            values=0,
            aggfunc="sum",
            fill_value=0,
        ).sort_index()

        def _count(crit_value: bool) -> pd.Series:
            if crit_value in pivot.columns:
                return pivot[crit_value]
            return pd.Series(0, index=pivot.index, dtype="int")

        series_df = pd.DataFrame(
            {
                "round": pivot.index.astype(int),
                NON_CRIT_LABEL: _count(False),
                CRIT_LABEL: _count(True),
            }
        )
        x_axis = "round"
    else:
        shot_index = pd.Series(
            range(1, len(shot_df) + 1),
            index=shot_df.index,
            dtype="Int64",
        )
        shot_df = shot_df.assign(shot_index=shot_index)
        series_df = pd.DataFrame(
            {
                "shot_index": shot_df["shot_index"],
                NON_CRIT_LABEL: (~crit_flags).astype(int),
                CRIT_LABEL: crit_flags.astype(int),
            }
        )
        x_axis = "shot_index"

    long_df = series_df.melt(
        id_vars=x_axis,
        var_name="series_name",
        value_name="count",
    )
    long_df["count"] = coerce_numeric(long_df["count"]).fillna(0)
    long_df[x_axis] = coerce_numeric(long_df[x_axis]).astype(int)

    CRIT_COLOR = "#C62828"
    NONCRIT_COLOR = "#B07A7A"

    fig = px.area(
        long_df,
        x=x_axis,
        y="count",
        color="series_name",
        title=f"Hits per Round — {battle_filename}",
        category_orders={"series_name": [NON_CRIT_LABEL, CRIT_LABEL]},
        color_discrete_map={
            NON_CRIT_LABEL: NONCRIT_COLOR,
            CRIT_LABEL: CRIT_COLOR,
        },
    )

    max_value = long_df[x_axis].max()
    if pd.notna(max_value):
        fig.update_xaxes(range=[1, int(max_value)])
    st.plotly_chart(fig, use_container_width=True)
    st.caption("Stacked areas show how many shots landed each round, with crits highlighted.")

    show_table = st.checkbox("Show raw table", value=False)
    if show_table:
        st.caption("Raw rows include crit flags and round identifiers for each shot.")
        if view_by == "Round":
            st.dataframe(series_df, use_container_width=True)
        else:
            preview_cols = ["shot_index", "is_crit"]
            if "battle_event" in shot_df.columns:
                preview_cols.append("battle_event")
            if "round" in shot_df.columns:
                preview_cols.append("round")
            st.dataframe(shot_df.loc[:, preview_cols], use_container_width=True)
