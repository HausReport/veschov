"""Streamlit UI for actual pool damage per shot."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

from typing import Iterable

import pandas as pd
import plotly.express as px
import streamlit as st

from veschov.io.parser_stub import parse_battle_log
from veschov.transforms.columns import (
    ATTACKER_COLUMN_CANDIDATES,
    TARGET_COLUMN_CANDIDATES,
    get_series,
    resolve_column,
)
from veschov.ui.components.combat_log_header import (
    apply_combat_lens,
    render_combat_log_header,
    render_sidebar_combat_log_upload,
)
from veschov.utils.series import coerce_numeric
from veschov.ui.view_by import prepare_round_view, select_view_by


OPTIONAL_PREVIEW_COLUMNS: Iterable[str] = (
    "round",
    "battle_event",
    "is_crit",
    "Ship",
    "Weapon",
)

SEGMENT_ORDER = [
    "Hull",
    "Shield",
    "Mitigated Normal",
    "Mitigated Isolytic",
    "Mitigated Apex",
]
SEGMENT_COLUMNS = {
    "Hull": "hull_damage",
    "Shield": "shield_damage",
    "Mitigated Normal": "mitigated_normal",
    "Mitigated Isolytic": "mitigated_iso",
    "Mitigated Apex": "mitigated_apex",
}
SEGMENT_COLORS = {
    "Hull": "red",
    "Shield": "blue",
    "Mitigated Normal": "#e5f5f9",
    "Mitigated Isolytic": "#99d8c9",
    "Mitigated Apex": "#2ca25f",
}


def _build_damage_mask(df: pd.DataFrame) -> pd.Series:
    if "event_type" not in df.columns:
        raise KeyError("event_type")
    typ = df["event_type"].astype(str).str.strip().str.lower()
    if "total_normal" in df.columns:
        total_damage = coerce_numeric(df["total_normal"])
        shield_damage = coerce_numeric(get_series(df, "shield_damage"))
        hull_damage = coerce_numeric(get_series(df, "hull_damage"))
        pool_positive = (shield_damage > 0) | (hull_damage > 0)
        total_positive = total_damage > 0
        total_missing = total_damage.isna()
        mask = (typ == "attack") & (total_positive | (total_missing & pool_positive))
    else:
        shield_damage = coerce_numeric(get_series(df, "shield_damage"))
        hull_damage = coerce_numeric(get_series(df, "hull_damage"))
        mask = (typ == "attack") & ((shield_damage > 0) | (hull_damage > 0))
    return mask


def _coerce_pool_damage(df: pd.DataFrame) -> pd.DataFrame:
    updated = df.copy()
    updated["shield_damage"] = coerce_numeric(
        get_series(updated, "shield_damage")
    ).fillna(0)
    updated["hull_damage"] = coerce_numeric(get_series(updated, "hull_damage")).fillna(0)
    updated["mitigated_normal"] = coerce_numeric(
        get_series(updated, "mitigated_normal")
    ).fillna(0)
    updated["mitigated_iso"] = coerce_numeric(get_series(updated, "mitigated_iso")).fillna(0)
    updated["mitigated_apex"] = coerce_numeric(
        get_series(updated, "mitigated_apex")
    ).fillna(0)
    return updated


def _normalize_round(df: pd.DataFrame) -> pd.DataFrame:
    if "round" not in df.columns:
        raise KeyError("round")
    updated = df.copy()
    round_series = updated["round"]
    round_numeric = coerce_numeric(round_series)
    if round_numeric.notna().sum() == round_series.notna().sum() and round_series.notna().any():
        updated["round"] = round_numeric.astype("Int64")
    else:
        round_values = round_series.fillna("Unknown").astype(str)
        categories = sorted(round_values.unique())
        updated["round"] = pd.Categorical(round_values, categories=categories, ordered=True)
    return updated


def _build_long_df(
    df: pd.DataFrame,
    hover_columns: list[str],
    *,
    include_shot_index: bool = True,
) -> pd.DataFrame:
    value_vars = list(SEGMENT_COLUMNS.values())
    base_vars: list[str] = ["round", *hover_columns]
    if include_shot_index:
        base_vars.insert(1, "shot_index")
    id_vars = [column for column in dict.fromkeys(base_vars) if column not in value_vars]
    long_df = df.melt(
        id_vars=id_vars,
        value_vars=value_vars,
        var_name="segment",
        value_name="amount",
    )
    long_df["segment"] = long_df["segment"].map(
        {value: key for key, value in SEGMENT_COLUMNS.items()}
    )
    long_df["amount"] = coerce_numeric(long_df["amount"]).fillna(0)
    if include_shot_index and "shot_index" in long_df.columns:
        long_df["shot_index"] = coerce_numeric(long_df["shot_index"])
        long_df = long_df[long_df["shot_index"].notna()].copy()
        long_df["shot_index"] = long_df["shot_index"].astype(int)
    return long_df


def _resolve_hover_columns(df: pd.DataFrame) -> list[str]:
    hover_columns: list[str] = []
    for column in SEGMENT_COLUMNS.values():
        if column in df.columns:
            hover_columns.append(column)
    for column in ("is_crit", "battle_event"):
        if column in df.columns:
            hover_columns.append(column)

    attacker_column = resolve_column(df, ATTACKER_COLUMN_CANDIDATES)
    target_column = resolve_column(df, TARGET_COLUMN_CANDIDATES)
    for column in (attacker_column, target_column):
        if column and column in df.columns:
            hover_columns.append(column)
    return hover_columns


def render_actual_damage_report() -> None:
    """Render the actual damage (post-mitigation) report."""
    #
    # Under-title text
    #
    st.markdown(
        "Damage Flow by Round highlights what damage actually landed on shields and hull after all "
        "mitigation (iso-defense, Apex, and other reductions). It is not the same as “Total Damage” "
        "in the log."
    )

    #
    # Determine if log is present
    #
    df = render_sidebar_combat_log_upload(
        "Damage Flow by Round",
        "Upload a battle log to visualize post-mitigation damage applied to shields and hull.",
        parser=parse_battle_log,
    )
    if df is None:
        st.info("No battle data loaded yet.")
        return

    #
    # Make the data
    #
    battle_filename = st.session_state.get("battle_filename") or "Session battle data"

    players_df = df.attrs.get("players_df")
    fleets_df = df.attrs.get("fleets_df")
    _, lens = render_combat_log_header(
        players_df,
        fleets_df,
        df,
        lens_key="actual_damage",
    )

    display_df = df.copy()
    display_df.attrs = {}

    required_columns = ("event_type", "round", "shield_damage", "hull_damage")
    missing_columns = [col for col in required_columns if col not in display_df.columns]
    if missing_columns:
        st.error(f"Missing required columns: {', '.join(missing_columns)}")
        return

    try:
        display_df = _coerce_pool_damage(display_df)
        display_df = _normalize_round(display_df)
        damage_mask = _build_damage_mask(display_df)
    except KeyError as exc:
        st.error(f"Missing required column: {exc.args[0]}")
        return

    shot_df = display_df.loc[damage_mask].copy()
    shot_df = shot_df[shot_df["shot_index"].notna()]
    shot_df = apply_combat_lens(shot_df, lens)

    if shot_df.empty:
        st.warning("No matching damage events found for this selection.")
        return

    view_by = select_view_by("actual_damage_view_by")
    hover_columns = _resolve_hover_columns(shot_df)

    if view_by == "Round":
        round_df = prepare_round_view(shot_df)
        if round_df is None:
            return
        long_df = _build_long_df(round_df, hover_columns, include_shot_index=False)
        long_df = (
            long_df.groupby(["round", "segment"], dropna=False)["amount"]
            .sum()
            .reset_index()
        )
        x_axis = "round"
        hover_columns = [column for column in hover_columns if column in long_df.columns]
        title = f"Damage Flow by Round — {battle_filename}"
    else:
        long_df = _build_long_df(shot_df, hover_columns, include_shot_index=True)
        hover_columns = [column for column in hover_columns if column in long_df.columns]
        long_df["accounted_total"] = long_df.groupby("shot_index")["amount"].transform(
            "sum"
        )

        # with st.expander("Debug stats", expanded=False):
        #     pool_nonzero = (
        #         long_df.loc[long_df["amount"] > 0].groupby("segment")["amount"]
        #         .size()
        #         .to_dict()
        #     )
        #     st.write(
        #         {
        #             "shot_rows": int(len(shot_df)),
        #             "long_rows": int(len(long_df)),
        #             "shot_index_min": (
        #                 int(long_df["shot_index"].min()) if not long_df.empty else None
        #             ),
        #             "shot_index_max": (
        #                 int(long_df["shot_index"].max()) if not long_df.empty else None
        #             ),
        #             "damage_min": float(long_df["amount"].min())
        #             if not long_df.empty
        #             else None,
        #             "damage_max": float(long_df["amount"].max())
        #             if not long_df.empty
        #             else None,
        #             "nonzero_damage_rows": int((long_df["amount"] > 0).sum()),
        #             "nonzero_rows_by_pool": pool_nonzero,
        #             "accounted_total_min": (
        #                 float(long_df["accounted_total"].min())
        #                 if not long_df.empty
        #                 else None
        #             ),
        #             "accounted_total_max": (
        #                 float(long_df["accounted_total"].max())
        #                 if not long_df.empty
        #                 else None
        #             ),
        #         }
        #     )

        x_axis = "shot_index"
        title = f"Damage Flow by Shot — {battle_filename}"

    #
    # Another explainer
    #
    st.markdown(
        "This chart stacks disjoint components of a hit. "
        "Blue/red are damage taken (shield/hull). Greens are damage prevented by mitigation "
        "(normal/isolytic) and Apex Barrier."
    )

    #
    # Generate the plot
    #
    fig = px.area(
        long_df,
        x=x_axis,
        y="amount",
        color="segment",
        # facet_col="round",
        # facet_col_wrap=4,
        color_discrete_map=SEGMENT_COLORS,
        category_orders={"segment": SEGMENT_ORDER},
        title=title,
        hover_data=hover_columns,
    )
    max_value = long_df[x_axis].max()
    if pd.notna(max_value):
        fig.update_xaxes(range=[1, int(max_value)])
    st.plotly_chart(fig, width="stretch")


    #
    # Show the table
    #
    show_table = st.checkbox("Show raw table", value=False)
    if show_table:
        st.caption("Raw rows include per-shot pools and mitigation columns from the combat log.")
        if view_by == "Round":
            summary = (
                long_df.pivot_table(
                    index="round",
                    columns="segment",
                    values="amount",
                    aggfunc="sum",
                    fill_value=0,
                )
                .reset_index()
                .rename_axis(None, axis=1)
            )
            st.dataframe(summary, width="stretch")
        else:
            preview_cols = [
                "shot_index",
                "round",
                "shield_damage",
                "hull_damage",
                "mitigated_normal",
                "mitigated_iso",
                "mitigated_apex",
            ]
            preview_cols.extend(
                col for col in OPTIONAL_PREVIEW_COLUMNS if col in shot_df.columns
            )
            preview_cols = list(dict.fromkeys(preview_cols))
            st.dataframe(shot_df.loc[:, preview_cols], width="stretch")
