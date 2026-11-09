"""Shamsi presentation and input; source timestamps remain Gregorian."""
from __future__ import annotations

from datetime import date
import re

import jdatetime
import pandas as pd


DATE_COLUMNS = {"date", "StartDateTime", "EndDateTime"}
DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def shamsi_date(value, include_time=False) -> str:
    if pd.isna(value):
        return ""
    timestamp = pd.Timestamp(value)
    result = jdatetime.date.fromgregorian(date=timestamp.date()).strftime("%Y.%m.%d")
    if include_time:
        result += timestamp.strftime(" %H:%M:%S")
    return result


def parse_shamsi(value: str) -> date | None:
    """Parse a valid Shamsi date, accepting Persian/Arabic digits and blank bounds."""
    value = value.strip().translate(DIGITS)
    if not value:
        return None
    if not re.fullmatch(r"[0-9]{4}([./-])[0-9]{1,2}\1[0-9]{1,2}", value):
        raise ValueError("Use a Shamsi date in YYYY.MM.DD format, for example 1405.01.12.")
    year, month, day = map(int, re.split(r"[./-]", value))
    try:
        return jdatetime.date(year, month, day).togregorian()
    except ValueError as exc:
        raise ValueError("Invalid Shamsi date. Check the year, month and day.") from exc


def shamsi_frame(frame: pd.DataFrame) -> pd.DataFrame:
    display = frame.copy()
    for column in DATE_COLUMNS & set(display.columns):
        display[column] = display[column].map(
            lambda value: shamsi_date(value, include_time=column != "date")
        )
    return display


def shamsi_axis(fig, dates):
    """Keep a continuous time axis while showing only Shamsi tick labels."""
    dates = pd.DatetimeIndex(dates).dropna().unique().sort_values()
    if len(dates) > 8:
        dates = dates[[round(index * (len(dates) - 1) / 7) for index in range(8)]]
    fig.update_xaxes(
        type="date", tickmode="array", tickvals=list(dates),
        ticktext=[shamsi_date(value) for value in dates], title="Trip start date (Shamsi)",
    )
    return fig
