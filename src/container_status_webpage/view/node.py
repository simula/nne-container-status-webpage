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
    1. model.snapshot.Snapshot - frames and summary.
    2. model.timeline - rows and segments of the timeline.

Sample code:
```python
import pandas as pd
from container_status_webpage.model.snapshot import load
from container_status_webpage.view import node

snapshot = load("synthetic", pd.Timestamp("2026-11-06 12:00"))
node.header(snapshot, 90001)
```
"""

import json
from typing import Any, List, Optional

import dash_ag_grid as dag
import pandas as pd
import plotly.graph_objects as go
from dash import dcc, html

from container_status_webpage.model import status
from container_status_webpage.model.snapshot import Snapshot
from container_status_webpage.model.timeline import (
    DEFAULT_RANGE,
    segments,
    span,
    thread_rows,
    x_range,
)
from container_status_webpage.view import grid, palette
from container_status_webpage.view.formatting import blank, duration, when


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
    Header of a node: id, status, municipality, the counts of active interfaces and experiments,
    and the networks of its active experiments.

    Args:
        snapshot (Snapshot): Loaded data.
        node_id (int): Node identifier of a reported node.

    Returns:
        html.Div: The header (id node-header).
    """
    node = snapshot.nodes.set_index("node_id").loc[node_id]
    experiments = snapshot.experiments
    active = status.networks(
        experiments[(experiments.node_id == node_id) & experiments.stop_time.isna()]
    )
    shown = active[active.network_id != 0].drop_duplicates("display_name")
    municipality = blank(node.municipality)
    return html.Div(
        [
            html.Span(f"Node {node_id}", className="node-id"),
            chip(node.status.capitalize(), palette.STATUS_COLOUR[node.status]),
            *([html.Span(municipality)] if municipality else []),
            html.Span(f"{node.interfaces} interfaces · {node.experiments} experiments"),
            *[
                chip(n.display_name, n.color)
                for n in shown.sort_values("display_name").itertuples()
            ],
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


def threads_table(snapshot: Snapshot, node_id: int) -> dag.AgGrid:
    """
    Threads of a node in the order of the timeline: latest run of every thread, the state on its
    colour.

    Args:
        snapshot (Snapshot): Loaded data.
        node_id (int): Node identifier.

    Returns:
        dag.AgGrid: The table (id node-threads).
    """
    states = snapshot.summary.states
    rows = []
    for container, thread, kind in thread_rows(snapshot, node_id):
        state = states.get((node_id, container, thread))
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


def experiments_table(snapshot: Snapshot, node_id: int) -> dag.AgGrid:
    """
    Measurement instances of a node, active first; the parameters JSON stays in the rows for
    parameters_view.

    Args:
        snapshot (Snapshot): Loaded data.
        node_id (int): Node identifier.

    Returns:
        dag.AgGrid: The table (id node-experiments, rows identified by the experiment id).
    """
    frame = status.networks(
        snapshot.experiments[snapshot.experiments.node_id == node_id]
    )
    frame = frame.assign(active=frame.stop_time.isna()).sort_values(
        ["active", "id"], ascending=[False, True]
    )

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
