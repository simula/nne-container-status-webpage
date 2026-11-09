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
# Node detail of the Containers page: header, timeline, threads, experiments
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
Node detail of the Containers page (documentation/DESIGN.md section 7): the header of the selected
node; the timeline, the threads and the experiments follow.

Integrations:
    1. data.cache.Snapshot - nodes and experiments frames.

Sample code:
```python
from container_status_webpage.components import node
from container_status_webpage.data.cache import CONTAINERS_CACHE

node.header(CONTAINERS_CACHE.get(), 90001)
```
"""

from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import plotly.graph_objects as go
from dash import dcc, html

from container_status_webpage.components import palette
from container_status_webpage.components.formatting import blank, duration, when
from container_status_webpage.data import status
from container_status_webpage.data.cache import Snapshot

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


def node_query(node_id: Any, container: Optional[str] = None) -> str:
    """
    URL query of the node detail (pages/containers.py builds the page from it).

    Args:
        node_id (Any): Node id, None for none.
        container (Optional[str], optional): Container to highlight. Defaults to None.

    Returns:
        str: Query string, e.g. "?tab=node&node=90001&container=udpping".
    """
    query = "?tab=node" + ("" if node_id is None else f"&node={node_id}")
    return query + (f"&container={container}" if container else "")


def click_query(cell: Dict[str, Any]) -> str:
    """
    URL query of a clicked grid or problem list cell: its node, and its container for a container
    cell.

    Args:
        cell (Dict[str, Any]): cellClicked of the AG Grid (rowId is the node id).

    Returns:
        str: Query string.
    """
    column = cell["colId"]
    return node_query(cell["rowId"], column if column in status.NAME else None)


def chip(text: str, colour: str) -> html.Span:
    """
    Text on a coloured chip.

    Args:
        text (str): Text.
        colour (str): Background colour.

    Returns:
        html.Span: The chip.
    """
    return html.Span(text, className="chip", style={"backgroundColor": colour})


def header(snapshot: Snapshot, node_id: int) -> html.Div:
    """
    Header of a node: id, status, municipality and the providers of its active experiments.

    Args:
        snapshot (Snapshot): Loaded data.
        node_id (int): Node identifier of a reported node.

    Returns:
        html.Div: The header (id node-header).
    """
    node = snapshot.nodes.set_index("node_id").loc[node_id]
    experiments = snapshot.experiments
    active = experiments[
        (experiments.node_id == node_id) & experiments.stop_time.isna()
    ]
    municipality = blank(node.municipality)
    return html.Div(
        [
            html.Span(f"Node {node_id}", className="node-id"),
            chip(node.status.capitalize(), palette.STATUS_COLOUR[node.status]),
            *([html.Span(municipality)] if municipality else []),
            *[
                chip(provider, palette.PROVIDER.get(provider, palette.PROVIDER_DEFAULT))
                for provider in sorted(set(active.provider))
            ],
        ],
        id="node-header",
        className="node-header",
    )


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


def gap(value: Any) -> str:
    """
    Text of a gap around a run.

    Args:
        value (Any): pd.Timedelta, or None / NaT.

    Returns:
        str: Duration, "–" for none.
    """
    return "–" if pd.isna(value) else duration(value.total_seconds())


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


def timeline(
    snapshot: Snapshot, node_id: int, container: Optional[str] = None
) -> dcc.Graph:
    """
    Timeline of a node: one row per thread (thread_rows), bars of segments in the colours of the
    grid, diamonds for version changes; DEFAULT_RANGE shown, the range buttons of the page set the
    others (x_range). The rows of a container are highlighted (Grid cell click).

    Args:
        snapshot (Snapshot): Loaded data.
        node_id (int): Node identifier.
        container (Optional[str], optional): Container to highlight. Defaults to None.

    Returns:
        dcc.Graph: The chart (id node-timeline); customdata of every point feeds run_detail.
    """
    # 1. Rows and segments; labels "<container> · <thread>"
    rows = thread_rows(snapshot, node_id)
    labels = [f"{status.NAME[c]} · {t}" for c, t, _ in rows]
    frame = segments(snapshot, node_id)
    frame = frame.assign(
        row=[f"{status.NAME[c]} · {t}" for c, t in zip(frame.container, frame.thread)],
        title=[
            {"run": f"Run ({cls})", "down": "Down", "silent": f"Silent ({cls})"}.get(
                kind, "Version change"
            )
            for kind, cls in zip(frame.kind, frame.cls)
        ],
        start_text=frame.start.map(when),
        end_text=frame.end.map(when),
        length=(frame.end - frame.start).map(gap),
        version_text=[
            version if kind != "version" else f"{previous} → {version}"
            for kind, version, previous in zip(
                frame.kind, frame.version, frame.previous
            )
        ],
        before_text=frame.before.map(gap),
        after_text=frame.after.map(gap),
    )
    custom = ["row", "title", "start_text", "end_text", "length", "version_text"]
    custom += ["before_text", "after_text"]
    hover = (
        "<b>%{customdata[0]}</b><br>%{customdata[1]}<br>%{customdata[2]} – "
        "%{customdata[3]} (%{customdata[4]})<br>%{customdata[5]}<extra></extra>"
    )
    # 2. Bars: one trace per kind and class
    figure = go.Figure()
    names = {"run": "{}", "down": "Down (gap > 1 h)", "silent": "Silent: {}"}
    for (kind, cls), part in frame[frame.kind != "version"].groupby(
        ["kind", "cls"], sort=False
    ):
        figure.add_bar(
            y=part.row,
            base=part.start,
            x=(part.end - part.start).dt.total_seconds() * 1000,
            orientation="h",
            name=names[kind].format(cls.capitalize()),
            marker={
                "color": palette.COLOUR[cls][0],
                "line": {"color": "#ffffff", "width": 1},
            },
            opacity=0.4 if kind == "down" else 1,
            customdata=part[custom].to_numpy(),
            hovertemplate=hover,
        )
    # 3. Version changes
    versions = frame[frame.kind == "version"]
    figure.add_scatter(
        x=versions.start,
        y=versions.row,
        mode="markers",
        name="Version change",
        marker={"symbol": "diamond", "size": 9, "color": "#333333"},
        customdata=versions[custom].to_numpy(),
        hovertemplate=hover,
    )
    # 4. Rows: orphans in dark red, never seen marked, the highlighted container in bold
    ticks = []
    for (c, _, kind), label in zip(rows, labels):
        text = {"never": f"{label} (never)", "orphan": f"⚠ {label}"}.get(kind, label)
        text = (
            f"<span style='color:{palette.ORPHAN}'>{text}</span>"
            if kind == "orphan"
            else text
        )
        ticks.append(f"<b>{text}</b>" if c == container else text)
    first, now = span(snapshot, node_id)
    figure.update_layout(
        height=120 + 26 * len(rows),
        margin={"l": 10, "r": 10, "t": 40, "b": 30},
        barmode="overlay",
        plot_bgcolor="#ffffff",
        # One look for every hover box instead of the colour of the bar
        hoverlabel={
            "bgcolor": "#ffffff",
            "bordercolor": "#bbbbbb",
            "font": {"color": "#222222"},
        },
        legend={"orientation": "h", "y": 1.02, "yanchor": "bottom", "x": 0},
        xaxis={
            "type": "date",
            "title": "UTC",
            "range": x_range(first, now, DEFAULT_RANGE),
            "showgrid": True,
            "gridcolor": "#eeeeee",
        },
        yaxis={
            "categoryorder": "array",
            "categoryarray": labels[::-1],
            "tickvals": labels,
            "ticktext": ticks,
            "range": [-0.5, len(labels) - 0.5],
            "automargin": True,
        },
    )
    return dcc.Graph(id="node-timeline", figure=figure, config={"displaylogo": False})


def run_detail(custom: List[str]) -> html.Table:
    """
    Detail of a clicked timeline segment.

    Args:
        custom (List[str]): customdata of the point (timeline).

    Returns:
        html.Table: Label and value per line.
    """
    labels = ("Thread", "Segment", "From", "To", "Length", "Version")
    labels += ("Gap before", "Gap after")
    return html.Table(
        [
            html.Tr([html.Th(label), html.Td(value)])
            for label, value in zip(labels, custom)
        ],
        className="run-detail",
    )
