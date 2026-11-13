#!/usr/bin/python3
# -*- coding: utf-8 -*-
# =================================================================
#
#    _  ___  ______  _________  _  ___________   _____  _________
#   / |/ / |/ / __/ / ___/ __ \/ |/ /_  __/ _ | /  _/ |/ / __/ _ \
#  /    /    / _/  / /__/ /_/ /    / / / / __ |_/ //    / _// , _/
# /_/|_/_/|_/___/  \___/\____/_/|_/ /_/ /_/ |_/___/_/|_/___/_/|_|
#           _____________ ________  ______  ___  ___  ___  ____
#          / __/_  __/ _ /_  __/ / / / __/ |_  |/ _ \|_  |/ __/
#         _\ \  / / / __ |/ / / /_/ /\ \  / __// // / __// _ \
#        /___/ /_/ /_/ |_/_/  \____/___/ /____/\___/____/\___/
#
#      ---   The NorNet Edge  Container Status Webpage   ---
#                    https://www.nntb.no
# =================================================================
#
# Text formatting of times, durations and missing values
#
# Copyright (C) 2026 by Simulamet CRNA research team
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# Contact: crna-eng@simula.no

"""
Text formatting shared by the tables and the timeline: times, durations, missing values, class
limit ranges.

Sample code:
```python
from container_status_webpage.view.formatting import duration

duration(93784)   # "1d 2h"
```
"""

import math
from typing import Any

import pandas as pd


def blank(value: Any) -> str:
    """
    Text of an optional value.

    Args:
        value (Any): Value, None or NaN.

    Returns:
        str: The value as text, empty when missing.
    """
    return "" if pd.isna(value) else str(value)


def when(ts: Any) -> str:
    """
    Time to the minute.

    Args:
        ts (Any): Timestamp or NaT.

    Returns:
        str: "YYYY-MM-DD HH:MM", "–" when missing.
    """
    return "–" if pd.isna(ts) else f"{ts:%Y-%m-%d %H:%M}"


def duration(seconds: float) -> str:
    """
    Duration with its two largest units.

    Args:
        seconds (float): Duration in seconds.

    Returns:
        str: E.g. "3d 4h", "2h 5m", "7m".
    """
    minutes = int(seconds // 60)
    days, hours, minutes = minutes // 1440, minutes // 60 % 24, minutes % 60
    if days:
        return f"{days}d {hours}h"
    return f"{hours}h {minutes}m" if hours else f"{minutes}m"


def hours_span(low_h: float, high_h: float) -> str:
    """
    Text of a class limit range in hours: hours up to 24 h, days from 24 h on; an open end as
    "< x" or "> x".

    Args:
        low_h (float): Lower limit in hours, 0 for none.
        high_h (float): Upper limit in hours, math.inf for none.

    Returns:
        str: E.g. "< 1 h", "2–6 h", "1–7 d", "> 7 d", "12 h – 2 d".
    """

    def text(hours: float) -> str:
        return f"{hours:g} h" if hours < 24 else f"{hours / 24:g} d"

    if low_h == 0:
        return f"< {text(high_h)}"
    if math.isinf(high_h):
        return f"> {text(low_h)}"
    if high_h <= 24:
        return f"{low_h:g}–{high_h:g} h"
    if low_h >= 24:
        return f"{low_h / 24:g}–{high_h / 24:g} d"
    return f"{text(low_h)} – {text(high_h)}"
