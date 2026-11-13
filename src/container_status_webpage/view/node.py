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
# Views of the Node page: header, timeline, threads, experiments
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
Views of the Node page (documentation/DESIGN.md section 7): header, timeline figure, detail of a
segment, threads and experiments tables, parameters of an experiment.

Integrations:
    1. model.pages.NodeData - node, networks, timeline rows and segments, threads, experiments.

Sample code:
```python
import pandas as pd
from container_status_webpage.model import pages
from container_status_webpage.model.snapshot import load
from container_status_webpage.view import node

data = pages.node(load("synthetic", pd.Timestamp("2026-11-06 12:00")), 90001, None)
node.header(data.node_id, data.node, data.networks)
```
"""

import json
import math
from typing import Any, List, Optional, Tuple

import dash_ag_grid as dag
import pandas as pd
import plotly.graph_objects as go
from dash import dcc, html

from container_status_webpage.model import limits, status
from container_status_webpage.view import grid, palette
from container_status_webpage.view.formatting import blank, duration, hours_span, when


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


def header(node_id: int, node: pd.Series, networks: pd.DataFrame) -> html.Div:
    """
    Header of a node: id, status, municipality, the counts of active interfaces and experiments,
    and the networks of its active experiments.

    Args:
        node_id (int): Node identifier of a reported node.
        node (pd.Series): Its row of the nodes frame.
        networks (pd.DataFrame): Networks of its active experiments (pages.NodeData.networks).

    Returns:
        html.Div: The header (id node-header).
    """
    municipality = blank(node.municipality)
    return html.Div(
        [
            html.Span(f"Node {node_id}", className="node-id"),
            chip(node.status.capitalize(), palette.STATUS_COLOUR[node.status]),
            *([html.Span(municipality)] if municipality else []),
            html.Span(f"{node.interfaces} interfaces · {node.experiments} experiments"),
            *[chip(n.display_name, n.color) for n in networks.itertuples()],
        ],
        id="node-header",
        className="node-header",
    )


def gap(value: Any) -> str:
    """
    Text of a gap around a run.

    Args:
        value (Any): pd.Timedelta, or None / NaT.

    Returns:
        str: Duration, "–" for none.
    """
    return "–" if pd.isna(value) else duration(value.total_seconds())


def timeline(
    rows: List[Tuple[str, str, str]],
    segments: pd.DataFrame,
    shown: List[pd.Timestamp],
    container: Optional[str] = None,
) -> dcc.Graph:
    """
    Timeline of a node: one row per thread, bars of segments in the colours of the grid, diamonds
    for version changes; the x range shown first (DEFAULT_RANGE), the range buttons of the page set
    the others (x_range). The rows of a container are highlighted (Grid cell click).

    Args:
        rows (List[Tuple[str, str, str]]): Timeline rows (container, thread, kind).
        segments (pd.DataFrame): Segments of the rows (model.timeline.segments).
        shown (List[pd.Timestamp]): X range shown first.
        container (Optional[str], optional): Container to highlight. Defaults to None.

    Returns:
        dcc.Graph: The chart (id node-timeline); customdata of every point feeds run_detail.
    """
    # 1. Labels "<container> · <thread>" of the rows and the segments
    labels = [f"{status.NAME[c]} · {t}" for c, t, _ in rows]
    frame = segments.assign(
        row=[
            f"{status.NAME[c]} · {t}"
            for c, t in zip(segments.container, segments.thread)
        ],
        title=[
            {"run": f"Run ({cls})", "down": "Down", "silent": f"Silent ({cls})"}.get(
                kind, "Version change"
            )
            for kind, cls in zip(segments.kind, segments.cls)
        ],
        start_text=segments.start.map(when),
        end_text=segments.end.map(when),
        length=(segments.end - segments.start).map(gap),
        version_text=[
            version if kind != "version" else f"{previous} → {version}"
            for kind, version, previous in zip(
                segments.kind, segments.version, segments.previous
            )
        ],
        before_text=segments.before.map(gap),
        after_text=segments.after.map(gap),
    )
    custom = ["row", "title", "start_text", "end_text", "length", "version_text"]
    custom += ["before_text", "after_text"]
    hover = (
        "<b>%{customdata[0]}</b><br>%{customdata[1]}<br>%{customdata[2]} – "
        "%{customdata[3]} (%{customdata[4]})<br>%{customdata[5]}<extra></extra>"
    )
    # 2. Bars: one trace per kind and class
    figure = go.Figure()
    down_gap = hours_span(limits.DOWN_AFTER / pd.Timedelta(hours=1), math.inf)
    names = {"run": "{}", "down": f"Down (gap {down_gap})", "silent": "Silent: {}"}
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
                "line": {"color": palette.TIMELINE_BAR_LINE, "width": 1},
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
        marker={"symbol": "diamond", "size": 9, "color": palette.VERSION_MARKER},
        customdata=versions[custom].to_numpy(),
        hovertemplate=hover,
    )
    # 4. Rows: orphans in dark red, never seen marked, the highlighted container in bold
    ticks = []
    for (c, _, kind), label in zip(rows, labels):
        text = {
            "never": f"{label} ({status.state_text('never')})",
            "orphan": f"⚠ {label}",
        }.get(kind, label)
        text = (
            f"<span style='color:{palette.ORPHAN}'>{text}</span>"
            if kind == "orphan"
            else text
        )
        ticks.append(f"<b>{text}</b>" if c == container else text)
    figure.update_layout(
        height=120 + 26 * len(rows),
        margin={"l": 10, "r": 10, "t": 40, "b": 30},
        barmode="overlay",
        plot_bgcolor=palette.TIMELINE_BACKGROUND,
        hoverlabel=palette.HOVER_BOX,
        legend={"orientation": "h", "y": 1.02, "yanchor": "bottom", "x": 0},
        xaxis={
            "type": "date",
            "title": "UTC",
            "range": shown,
            "showgrid": True,
            "gridcolor": palette.TIMELINE_GRID,
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


def threads_table(
    threads: List[Tuple[str, str, str, Optional[status.ThreadState]]],
) -> dag.AgGrid:
    """
    Threads of a node in the order of the timeline: latest run of every thread, the state on its
    colour.

    Args:
        threads (List[Tuple[str, str, str, Optional[status.ThreadState]]]): Container, thread,
            kind and state of every timeline row (pages.NodeData.threads).

    Returns:
        dag.AgGrid: The table (id node-threads).
    """
    rows = []
    for container, thread, kind, state in threads:
        row = (
            grid.orphan_row(thread, state)
            if kind == "orphan"
            else grid.thread_row(thread, state)
        )
        rows.append({"container": status.NAME[container], **row})
    columns = [
        {"headerName": "Container", "field": "container", "width": 130},
        {"headerName": "Thread", "field": "thread", "width": 150},
        {
            "headerName": "State",
            "field": "state",
            "width": 210,
            "cellStyle": {
                "function": "({backgroundColor: params.data.colour, color: params.data.text})"
            },
        },
        {"headerName": "Version", "field": "version", "width": 150},
        {"headerName": "Up", "field": "up", "width": 90},
        {"headerName": "Last seen (UTC)", "field": "seen", "width": 160},
        {"headerName": "Ago", "field": "ago", "width": 90},
        {"headerName": "Starts 24 h / 7 d", "field": "starts", "width": 140},
        # Below its minimum width the table scrolls instead of cutting "314,076 (479/h)"
        {
            "headerName": "Receiver restarts",
            "field": "restarts",
            "flex": 1,
            "minWidth": 170,
        },
    ]
    return dag.AgGrid(
        id="node-threads",
        rowData=rows,
        columnDefs=columns,
        # The order of the timeline; durations as text do not sort
        defaultColDef={**grid.DEFAULT_COLUMN, "sortable": False},
        dashGridOptions={**grid.GRID_OPTIONS, "domLayout": "autoHeight"},
        className="nne-grid",
    )


def experiments_table(frame: pd.DataFrame) -> dag.AgGrid:
    """
    Measurement instances of a node, active first; the parameters JSON stays in the rows for
    parameters_view.

    Args:
        frame (pd.DataFrame): Experiments of the node with network names, active first
            (pages.NodeData.experiments).

    Returns:
        dag.AgGrid: The table (id node-experiments, rows identified by the experiment id).
    """

    def measurement(desc: int) -> str:
        name = status.NAME.get(status.CONFIGURED_BY.get(desc))
        return f"{desc} ({name})" if name else str(desc)

    rows = [
        {
            "id": int(e.id),
            "measurement": measurement(e.measurement_desc_id),
            "network": e.display_name,
            "iccid": blank(e.iccid),
            "start": when(e.start_time),
            "stop": "active" if e.active else when(e.stop_time),
            "parameters": e.parameters,
        }
        for e in frame.itertuples()
    ]
    columns = [
        {"headerName": "Id", "field": "id", "width": 100},
        {"headerName": "Measurement", "field": "measurement", "width": 150},
        {"headerName": "Network", "field": "network", "width": 140},
        {"headerName": "ICCID", "field": "iccid", "width": 190},
        {"headerName": "Start (UTC)", "field": "start", "width": 160},
        {"headerName": "Stop (UTC)", "field": "stop", "flex": 1},
    ]
    return dag.AgGrid(
        id="node-experiments",
        rowData=rows,
        columnDefs=columns,
        getRowId="params.data.id",
        rowClassRules={"experiment-stopped": "params.data.stop !== 'active'"},
        defaultColDef=grid.DEFAULT_COLUMN,
        dashGridOptions={**grid.GRID_OPTIONS, "domLayout": "autoHeight"},
        className="nne-grid",
    )


def parameters_view(experiment_id: int, parameters: Any) -> html.Div:
    """
    Parameters of an experiment, indented JSON (the text as it is when it is not JSON).

    Args:
        experiment_id (int): Experiment id.
        parameters (Any): parameters of measurement_instance.

    Returns:
        html.Div: Caption and the parameters.
    """
    try:
        text = json.dumps(json.loads(parameters), indent=2, sort_keys=True)
    except TypeError, ValueError:
        text = str(parameters)
    return html.Div(
        [
            html.P(f"Parameters of experiment {experiment_id}", className="data-info"),
            html.Pre(text, className="parameters"),
        ]
    )
