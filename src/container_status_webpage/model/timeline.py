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
# Timeline of a node: thread rows, segments, time span and ranges
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
Timeline of a node (documentation/DESIGN.md section 7): its rows (threads), the segments of every
thread (runs, down periods, silence to now, version changes), the time span and the x ranges of the
range buttons and the date pickers. Pandas only, no Dash.

Integrations:
    1. model.snapshot.Snapshot - frames and summary.

Sample code:
```python
import pandas as pd
from container_status_webpage.model import timeline
from container_status_webpage.model.snapshot import load

snapshot = load("synthetic", pd.Timestamp("2026-11-06 12:00"))
timeline.segments(snapshot, 90001)
```
"""

from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from container_status_webpage.model import status
from container_status_webpage.model.snapshot import Snapshot

# A gap longer than this between the last heartbeat of a run and the next start: the thread was down
DOWN_AFTER: pd.Timedelta = pd.Timedelta(hours=1)


# Columns of segments
SEGMENT_COLUMNS: Tuple[str, ...] = (
    "container",
    "thread",
    "kind",
    "cls",
    "start",
    "end",
    "version",
    "previous",
    "before",
    "after",
)


# Ranges of the timeline (days back from the load time, "all" from the first start) and the default
RANGES: Tuple[str, ...] = ("1", "3", "7", "14", "all")


DEFAULT_RANGE: str = "7"


def thread_rows(snapshot: Snapshot, node_id: int) -> List[Tuple[str, str, str]]:
    """
    Rows of the timeline: the expected threads of every deployed container, then its orphans; main
    containers first.

    Args:
        snapshot (Snapshot): Loaded data.
        node_id (int): Node identifier.

    Returns:
        List[Tuple[str, str, str]]: Container, thread and kind ("expected", "never", "orphan").
    """
    rows = []
    for container in status.MAIN + status.EXTRA:
        cell = snapshot.summary.cells[node_id, container]
        if cell.state == "none":
            continue
        rows += [
            (container, name, "never" if state is None else "expected")
            for name, state in cell.threads
        ]
        rows += [(container, name, "orphan") for name in cell.orphans]
    return rows


def segments(snapshot: Snapshot, node_id: int) -> pd.DataFrame:
    """
    Timeline segments of a node (container_rawdata holds one row per run):
    run (start to last heartbeat, class of its length), down (next start more than DOWN_AFTER
    after the last heartbeat), silent (last heartbeat to now, last seen class when not running) and
    version (start of a run with another version than the run before).

    Args:
        snapshot (Snapshot): Loaded data.
        node_id (int): Node identifier.

    Returns:
        pd.DataFrame: Columns of SEGMENT_COLUMNS; before / after are the gaps around a run.
    """
    now = snapshot.summary.now
    raw = snapshot.raw[snapshot.raw.node_id == node_id]
    out: List[Dict[str, Any]] = []
    for container, thread, _ in thread_rows(snapshot, node_id):
        runs = list(
            raw[(raw.container == container) & (raw.process == thread)]
            .sort_values("start_ts")
            .itertuples()
        )
        for i, run in enumerate(runs):
            base = {"container": container, "thread": thread, "version": run.version}
            previous = runs[i - 1] if i else None
            following = runs[i + 1] if i + 1 < len(runs) else None
            # 1. Down period and version change before the run
            if previous is not None and run.start_ts - previous.seen_ts > DOWN_AFTER:
                out.append(
                    {
                        **base,
                        "kind": "down",
                        "cls": "down",
                        "start": previous.seen_ts,
                        "end": run.start_ts,
                    }
                )
            if previous is not None and run.version != previous.version:
                out.append(
                    {
                        **base,
                        "kind": "version",
                        "start": run.start_ts,
                        "end": run.start_ts,
                        "previous": previous.version,
                    }
                )
            # 2. The run
            hours = (run.seen_ts - run.start_ts).total_seconds() / 3600
            out.append(
                {
                    **base,
                    "kind": "run",
                    "cls": status.uptime_class(hours),
                    "start": run.start_ts,
                    "end": run.seen_ts,
                    "before": (
                        None if previous is None else run.start_ts - previous.seen_ts
                    ),
                    "after": (
                        None if following is None else following.start_ts - run.seen_ts
                    ),
                }
            )
        # 3. Silent since the last heartbeat
        if runs:
            seen = status.seen_class((now - runs[-1].seen_ts).total_seconds() / 3600)
            if seen != "running":
                out.append(
                    {
                        "container": container,
                        "thread": thread,
                        "version": runs[-1].version,
                        "kind": "silent",
                        "cls": seen,
                        "start": runs[-1].seen_ts,
                        "end": now,
                    }
                )
    return pd.DataFrame(out, columns=list(SEGMENT_COLUMNS))


def span(snapshot: Snapshot, node_id: int) -> Tuple[pd.Timestamp, pd.Timestamp]:
    """
    Time span of the timeline of a node: first start of a shown thread, load time.

    Args:
        snapshot (Snapshot): Loaded data.
        node_id (int): Node identifier.

    Returns:
        Tuple[pd.Timestamp, pd.Timestamp]: First start (DEFAULT_RANGE days back without runs) and
            load time.
    """
    now = snapshot.summary.now
    shown = {
        (container, thread) for container, thread, _ in thread_rows(snapshot, node_id)
    }
    raw = snapshot.raw[snapshot.raw.node_id == node_id]
    starts = [
        start
        for container, thread, start in zip(raw.container, raw.process, raw.start_ts)
        if (container, thread) in shown
    ]
    return (min(starts) if starts else now - pd.Timedelta(days=int(DEFAULT_RANGE))), now


def x_range(first: pd.Timestamp, now: pd.Timestamp, choice: str) -> List[pd.Timestamp]:
    """
    X range of the timeline for a range button.

    Args:
        first (pd.Timestamp): First start (span).
        now (pd.Timestamp): Load time (span).
        choice (str): Value of RANGES.

    Returns:
        List[pd.Timestamp]: Start and end.
    """
    return [first if choice == "all" else now - pd.Timedelta(days=int(choice)), now]


def picker_range(
    from_date: Optional[str], to_date: Optional[str], now: pd.Timestamp
) -> Optional[List[pd.Timestamp]]:
    """
    X range of the timeline from the From / To date pickers (UTC days as the timeline): From at
    00:00, To to the end of its day, at most the load time (the newest data).

    Args:
        from_date (Optional[str]): From date, YYYY-MM-DD.
        to_date (Optional[str]): To date, YYYY-MM-DD.
        now (pd.Timestamp): Load time (span).

    Returns:
        Optional[List[pd.Timestamp]]: Start and end; None for an empty or malformed date or an
            end not after the start.
    """
    if not (from_date and to_date):
        return None
    try:
        start, end = (pd.Timestamp(value).normalize() for value in (from_date, to_date))
    except ValueError:
        return None
    end = min(end + pd.Timedelta(days=1), now)
    return [start, end] if start < end else None
