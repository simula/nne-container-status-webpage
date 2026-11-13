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
# AG Grid tables of the pages Overview, Grid and Problems
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
AG Grid tables of the container pages (documentation/DESIGN.md section 7): the overview counts, the
colour grid of nodes and containers with its legend, the problem list. Cell styles come from
view.palette: dash-ag-grid applies the first matching style condition only, so every cell gets
the id of its complete style and every container column one condition per style id.

Integrations:
    1. model.snapshot.Snapshot - frames and summary.
    2. dash-ag-grid - tables; CSS in assets/style.css (class nne-grid).

Sample code:
```python
import pandas as pd
from container_status_webpage.model.snapshot import load
from container_status_webpage.view import grid

snapshot = load("synthetic", pd.Timestamp("2026-11-06 12:00"))
grid.status_grid(snapshot)
```
"""

import json
import math
from typing import Any, Dict, List, Optional, Tuple

import dash_ag_grid as dag
from dash import html

from container_status_webpage.model import status
from container_status_webpage.model.snapshot import Snapshot
from container_status_webpage.view import palette
from container_status_webpage.view.formatting import blank, duration, when

# Column options of every table: filtered by the toolbars (filter_rows), not by column filters
DEFAULT_COLUMN: Dict[str, Any] = {"sortable": True, "filter": False, "resizable": True}

# Columns of the overview tables: share the width, headers wrap (the tables fit the narrow half of
# the Overview)
FIT_COLUMN: Dict[str, Any] = {
    "flex": 1,
    "minWidth": 80,
    "wrapHeaderText": True,
    "autoHeaderHeight": True,
}

# Grid options of every table: tooltips after 300 ms
GRID_OPTIONS: Dict[str, Any] = {"tooltipShowDelay": 300, "animateRows": False}

# Node column of the grid and the problem list: a click on the row opens the Node page
# (controller/grid.py, controller/problems.py), rows are identified by the node id (getRowId)
NODE_COLUMN: Dict[str, Any] = {
    "headerName": "Node",
    "field": "node_id",
    "width": 90,
    "cellClass": "node-link",
}

# States and markers of the grid filter: a node matches when any of its cells has one
STATES: Tuple[str, ...] = status.SEVERITY + (
    "partial",
    "orphan",
    "flapping",
    "restarts",
)


def status_column(field: str = "status") -> Dict[str, Any]:
    """
    Column of the node status with the colour of its chip.

    Args:
        field (str, optional): Field of the status. Defaults to "status".

    Returns:
        Dict[str, Any]: AG Grid column definition.
    """
    conditions = [
        {
            "condition": f"params.value === '{name.capitalize()}'",
            "style": {"backgroundColor": colour, "color": "#ffffff"},
        }
        for name, colour in palette.STATUS_COLOUR.items()
    ]
    return {
        "headerName": "Status",
        "field": field,
        "width": 110,
        "cellStyle": {"styleConditions": conditions},
    }


def thread_row(name: str, state: Optional[Dict[str, Any]]) -> Dict[str, str]:
    """
    Row of the tooltip table and the threads table of the Node page: the latest run of a thread.

    Args:
        name (str): Thread name.
        state (Optional[Dict[str, Any]]): Thread state (status.thread_states), None when never seen.

    Returns:
        Dict[str, str]: thread, state, colour and text colour of the state, version, up, seen,
            ago, starts, restarts (receivers: count and rate, ↻ with a warning; empty otherwise).
    """
    if state is None:
        return {
            "thread": name,
            "state": "never",
            "colour": palette.COLOUR["never"][0],
            "text": palette.COLOUR["never"][1],
            **dict.fromkeys(("version", "up", "seen", "ago", "starts"), "–"),
            "restarts": "",
        }
    running = state["seen"] == "running"
    colour, text = palette.COLOUR[state["up"] if running else state["seen"]]
    rate = status.restart_rate(state)
    restarts = (
        ""
        if rate is None
        else f"{state['restarts']:,.0f} ({status.rate_text(rate)})"
        + (" ↻" if status.restart_warning(state) else "")
    )
    return {
        "restarts": restarts,
        "thread": name,
        "state": state["seen"],
        "colour": colour,
        "text": text,
        "version": state["version"],
        "up": duration(state["uptime"]),
        "seen": when(state["seen_ts"]),
        "ago": duration(state["age_h"] * 3600),
        "starts": f"{state['starts_24h']} / {state['starts_7d']}",
    }


def orphan_row(name: str, state: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Row of a thread running for an inactive experiment: the inactive experiment as state.

    Args:
        name (str): Thread name (sender-<id> / receiver-<id>).
        state (Optional[Dict[str, Any]]): Thread state (status.thread_states).

    Returns:
        Dict[str, Any]: thread_row with the state replaced and orphan True.
    """
    return {
        **thread_row(name, state),
        "state": f"inactive experiment {status.experiment_id(name)}",
        "colour": palette.ORPHAN,
        "text": "#ffffff",
        "orphan": True,
    }


def hover(
    node_id: int,
    node_status: str,
    container: str,
    cell: status.Cell,
    states: Dict[Tuple[int, str, str], Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Tooltip of a grid cell, drawn as a table by ThreadTable
    (assets/dashAgGridComponentFunctions.js): a title with the cell, one row per expected thread,
    then the orphans.

    Args:
        node_id (int): Node identifier.
        node_status (str): Status of the node.
        container (str): Container name.
        cell (status.Cell): The cell.
        states (Dict[Tuple[int, str, str], Dict[str, Any]]): Thread states of the summary.

    Returns:
        Dict[str, Any]: title (str) and rows (thread_row, orphans with orphan True).
    """
    # 1. The cell
    markers = [
        text
        for flag, text in ((cell.partial, "partial"), (cell.flapping, "flapping"))
        if flag
    ]
    title = " · ".join(
        [
            f"Node {node_id}",
            node_status.capitalize(),
            f"{status.NAME[container]}: {cell.state}",
            *markers,
        ]
    )
    # 2. Expected threads, then the orphans with the inactive experiment as state
    rows = [thread_row(name, state) for name, state in cell.threads]
    rows += [
        orphan_row(name, states.get((node_id, container, name)))
        for name in cell.orphans
    ]
    return {"title": title, "rows": rows}


def status_grid(snapshot: Snapshot) -> dag.AgGrid:
    """
    Colour grid: one row per node, the main and the extra containers as column groups.

    Args:
        snapshot (Snapshot): Loaded data.

    Returns:
        dag.AgGrid: The grid (id status-grid).
    """
    # 1. Rows: text, style id and tooltip of every container cell, states and markers for the
    #    filter
    styles: Dict[str, int] = {}
    rows = []
    for node in status.ordered(snapshot.nodes).itertuples():
        row: Dict[str, Any] = {
            "node_id": node.node_id,
            "status": node.status.capitalize(),
            "municipality": blank(node.municipality),
        }
        states = set()
        for container in status.MAIN + status.EXTRA:
            cell = snapshot.summary.cells[node.node_id, container]
            states |= {cell.state} - {"none"}
            states |= {
                marker
                for marker, flag in (
                    ("partial", cell.partial),
                    ("orphan", cell.orphans or cell.orphan_container),
                    ("flapping", cell.flapping),
                    ("restarts", cell.restart_warnings),
                )
                if flag
            }
            style = json.dumps(
                palette.cell_style(cell, node.status == "TESTING"), sort_keys=True
            )
            row[container] = palette.cell_text(cell)
            row[f"{container}__style"] = styles.setdefault(style, len(styles))
            row[f"{container}__tip"] = hover(
                node.node_id, node.status, container, cell, snapshot.summary.states
            )
        row["states"] = sorted(states)
        rows.append(row)

    # 2. Container columns: one style condition per style id
    def column(container: str) -> Dict[str, Any]:
        conditions = [
            {
                "condition": f"params.data.{container}__style === {number}",
                "style": json.loads(style),
            }
            for style, number in styles.items()
        ]
        return {
            "headerName": status.NAME[container],
            "field": container,
            "tooltipField": f"{container}__tip",
            "tooltipComponent": "ThreadTable",
            "width": 130,
            "cellStyle": {"styleConditions": conditions},
        }

    # 3. Grid: filtered by the toolbar (filter_rows), not by column filters
    columns = [
        {**NODE_COLUMN, "pinned": "left"},
        {**status_column(), "pinned": "left"},
        {
            "headerName": "Municipality",
            "field": "municipality",
            "width": 130,
            "pinned": "left",
        },
        {"headerName": "Main containers", "children": [column(c) for c in status.MAIN]},
        {
            "headerName": "Extra containers",
            "children": [column(c) for c in status.EXTRA],
        },
    ]
    return dag.AgGrid(
        id="status-grid",
        rowData=rows,
        getRowId="params.data.node_id",
        columnDefs=columns,
        defaultColDef=DEFAULT_COLUMN,
        dashGridOptions=GRID_OPTIONS,
        className="nne-grid",
        style={"height": "70vh"},
    )


def filter_rows(
    rows: List[Dict[str, Any]],
    statuses: List[str],
    states: List[str],
    nodes: List[int],
    municipalities: List[str],
    *,
    text: str = "",
) -> List[Dict[str, Any]]:
    """
    Rows of the colour grid or the problem list that match the toolbar; an empty control does not
    filter.

    Args:
        rows (List[Dict[str, Any]]): Rows of status_grid or problems_grid.
        statuses (List[str]): Displayed statuses, e.g. ["Deployed"].
        states (List[str]): Values of STATES; a node matches when any of its cells has one (grid).
        nodes (List[int]): Node ids.
        municipalities (List[str]): Municipalities.
        text (str, optional): Text anywhere in the issues, case-insensitive (problem list).
            Defaults to "".

    Returns:
        List[Dict[str, Any]]: Matching rows in their order.
    """
    needle = text.strip().lower()
    return [
        row
        for row in rows
        if (not statuses or row["status"] in statuses)
        and (not states or set(states) & set(row["states"]))
        and (not nodes or row["node_id"] in nodes)
        and (not municipalities or row["municipality"] in municipalities)
        and (not needle or needle in row["issues"].lower())
    ]


def legend() -> html.Div:
    """
    Legend of the colour grid: classes with their limits, markers.

    Returns:
        html.Div: Swatches with text.
    """

    def item(style: Dict[str, str], text: str) -> html.Span:
        return html.Span([html.I(style=style), text])

    items = [
        item({"backgroundColor": palette.COLOUR[name][0]}, f"✓ Running, uptime {limit}")
        for name, limit in (
            ("fresh", "< 1 h"),
            ("young", "1 h – 1 d"),
            ("stable", "1–7 d"),
            ("long-run", "> 7 d"),
        )
    ]
    items += [
        item(
            {"backgroundColor": palette.COLOUR[name][0]},
            f"{palette.SYMBOL[name]} {name.capitalize()}: last seen {limit}",
        )
        for name, limit in (
            ("late", "2–6 h"),
            ("stale", "6–24 h"),
            ("down", "1–7 d"),
            ("long down", "> 7 d"),
        )
    ]
    items += [
        item(
            {
                "backgroundColor": palette.COLOUR["never"][0],
                "backgroundImage": palette.HATCH,
            },
            "– Configured, never seen",
        ),
        item({"border": palette.NONE_BORDER}, "Not configured"),
        item(
            {"boxShadow": f"inset 0 0 0 3px {palette.PARTIAL}"},
            "Partial: some threads not running (count)",
        ),
        item(
            {"boxShadow": f"inset 0 0 0 3px {palette.ORPHAN}"},
            f"⚠ {status.NAME['udpping']} thread of an inactive experiment, ⚠ container running "
            "without a configured instance",
        ),
        item(
            {"backgroundImage": palette.FLAP_DOT},
            f"Flapping: ≥ {status.FLAPPING} starts in 24 h",
        ),
        item(
            {"backgroundImage": palette.RESTART_DOT},
            f"↻ Receiver restarts: > {status.RESTARTS_PER_HOUR:g} per hour, or > "
            f"{status.RESTARTS_PER_DAY:g} per day after {status.RESTARTS_LONG_RUN_H / 24:g} days",
        ),
        item({"border": palette.TESTING_BORDER}, "Testing node"),
    ]
    return html.Div(items, className="legend")


def problems_grid(snapshot: Snapshot) -> dag.AgGrid:
    """
    Problem list: nodes that are not fully OK, DEPLOYED first, then the longest silent.

    Args:
        snapshot (Snapshot): Loaded data.

    Returns:
        dag.AgGrid: The grid (id problems-grid).
    """
    found = status.problems(snapshot.nodes, snapshot.summary, snapshot.raw)
    rows = [
        {
            "node_id": row.node_id,
            "status": row.status.capitalize(),
            "municipality": blank(row.municipality),
            "issues": row.issues,
            # Sort key of the last heartbeat column: None (never) first, then the oldest
            "last_seen": (
                None if math.isinf(row.silent_h) else row.last_seen.isoformat()
            ),
            "last_heartbeat": (
                "Never"
                if math.isinf(row.silent_h)
                else f"{when(row.last_seen)} ({duration(row.silent_h * 3600)} ago)"
            ),
        }
        for row in found.itertuples()
    ]
    columns = [
        NODE_COLUMN,
        status_column(),
        {"headerName": "Municipality", "field": "municipality", "width": 130},
        {
            "headerName": "Issues",
            "field": "issues",
            "flex": 1,
            "wrapText": True,
            "autoHeight": True,
        },
        {
            "headerName": "Last heartbeat (UTC)",
            "field": "last_seen",
            "valueFormatter": {"function": "params.data.last_heartbeat"},
            "width": 230,
        },
    ]
    return dag.AgGrid(
        id="problems-grid",
        rowData=rows,
        getRowId="params.data.node_id",
        columnDefs=columns,
        defaultColDef=DEFAULT_COLUMN,
        dashGridOptions=GRID_OPTIONS,
        className="nne-grid",
        style={"height": "70vh"},
    )


def overview(snapshot: Snapshot) -> html.Div:
    """
    Overview: node counts per status group, nodes running each container per status group.

    Args:
        snapshot (Snapshot): Loaded data.

    Returns:
        html.Div: Two tables.
    """
    # 1. Node counts per status group
    counts = status.overview(snapshot.nodes, snapshot.summary)
    nodes_per_group = dict(zip(counts.status, counts.nodes))
    by_status = dag.AgGrid(
        id="overview-status",
        rowData=[
            {**row, "status": row["status"].capitalize()}
            for row in counts.to_dict("records")
        ],
        columnDefs=[
            {"headerName": "Status", "field": "status", "minWidth": 100},
            {"headerName": "Nodes", "field": "nodes"},
            {"headerName": "All main OK", "field": "all_main_ok"},
            {"headerName": "Some issue", "field": "some_issue"},
            {"headerName": "Nothing running", "field": "nothing_running"},
        ],
        defaultColDef=FIT_COLUMN,
        dashGridOptions={**GRID_OPTIONS, "domLayout": "autoHeight"},
        className="nne-grid",
    )
    # 2. Nodes running each container per status group: "running / nodes"
    running = status.container_counts(snapshot.nodes, snapshot.summary)
    groups = [column for column in running.columns if column != "container"]
    rows: List[Dict[str, Any]] = [
        {
            "container": status.NAME[row["container"]],
            **{g: f"{row[g]} / {nodes_per_group[g]}" for g in groups},
        }
        for row in running.to_dict("records")
    ]
    by_container = dag.AgGrid(
        id="overview-containers",
        rowData=rows,
        columnDefs=[{"headerName": "Container", "field": "container", "minWidth": 120}]
        + [
            {"headerName": f"{g.capitalize()} (running / nodes)", "field": g}
            for g in groups
        ],
        defaultColDef=FIT_COLUMN,
        dashGridOptions={**GRID_OPTIONS, "domLayout": "autoHeight"},
        className="nne-grid",
    )
    return html.Div(
        [
            html.H3("Nodes by status"),
            by_status,
            html.H3("Running containers by node status"),
            by_container,
        ]
    )
