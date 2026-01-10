from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

from datetime import date, datetime, timedelta


def compute_period_range(
    period: str,
    anchor_date: date,
    custom_range: tuple[date, date] | None,
) -> tuple[datetime, datetime]:
    """Return naive datetime boundaries for the requested period.

    Period ranges are inclusive of ``period_start`` and exclusive of ``period_end``.
    All calculations are performed in local (naive) time to match the stored values
    in SQLite.
    """

    period_lower = period.lower()

    if period_lower == "custom":
        if not custom_range or len(custom_range) != 2:
            raise ValueError("custom_range must contain a start and end date")
        custom_start, custom_end = custom_range
        period_start = datetime.combine(custom_start, datetime.min.time())
        period_end = datetime.combine(custom_end + timedelta(days=1), datetime.min.time())
        return period_start, period_end

    if period_lower == "day":
        period_start = datetime.combine(anchor_date, datetime.min.time())
        period_end = period_start + timedelta(days=1)
    elif period_lower == "week":
        weekday = anchor_date.weekday()
        week_start_date = anchor_date - timedelta(days=weekday)
        period_start = datetime.combine(week_start_date, datetime.min.time())
        period_end = period_start + timedelta(days=7)
    elif period_lower == "month":
        period_start = datetime.combine(anchor_date.replace(day=1), datetime.min.time())
        if anchor_date.month == 12:
            next_month = date(anchor_date.year + 1, 1, 1)
        else:
            next_month = date(anchor_date.year, anchor_date.month + 1, 1)
        period_end = datetime.combine(next_month, datetime.min.time())
    else:
        raise ValueError(f"Unsupported period: {period}")

    return period_start, period_end
