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
# AG Grid tables of the Containers page: overview, grid, problems
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
AG Grid tables of the Containers page (documentation/DESIGN.md section 7): the overview counts, the
colour grid of nodes and containers with its legend, the problem list. Cell styles come from
components.palette: dash-ag-grid applies the first matching style condition only, so every cell gets
the id of its complete style and every container column one condition per style id.

Integrations:
    1. data.cache.Snapshot - frames and summary.
    2. dash-ag-grid - tables; CSS in assets/style.css (class nne-grid).

Sample code:
```python
from container_status_webpage.components import grid
from container_status_webpage.data.cache import CACHE

grid.status_grid(CACHE.get())
```
"""

import json
import math
from typing import Any, Dict, List

import dash_ag_grid as dag
from dash import html

from container_status_webpage.components import palette
from container_status_webpage.components.formatting import blank, duration, when
from container_status_webpage.data import status
from container_status_webpage.data.cache import Snapshot

# Column options of every table
DEFAULT_COLUMN: Dict[str, Any] = {"sortable": True, "filter": True, "resizable": True}

# Grid options of every table: tooltips after 300 ms
GRID_OPTIONS: Dict[str, Any] = {"tooltipShowDelay": 300, "animateRows": False}


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
            "condition": f"params.value === '{name}'",
            "style": {"backgroundColor": colour, "color": "#ffffff"},
        }
        for name, colour in palette.STATUS_COLOUR.items()
    ]
    return {
        "headerName": "status",
        "field": field,
        "width": 110,
        "cellStyle": {"styleConditions": conditions},
    }


def hover(node_id: int, node_status: str, container: str, cell: status.Cell) -> str:
    """
    Tooltip of a grid cell: the cell, then one line per thread.

    Args:
        node_id (int): Node identifier.
        node_status (str): Status of the node.
        container (str): Container name.
        cell (status.Cell): The cell.

    Returns:
        str: Lines separated by newlines.
    """
    # 1. The cell
    markers = [
        text
        for flag, text in ((cell.partial, "partial"), (cell.flapping, "flapping"))
        if flag
    ]
    lines = [
        " · ".join(
            [f"node {node_id}", node_status, f"{container}: {cell.state}", *markers]
        )
    ]
    # 2. Expected threads
    for name, state in cell.threads:
        if state is None:
            lines.append(f"{name}: never seen")
            continue
        lines.append(
            f"{name}: {state['seen']}, {state['version']}, up {duration(state['uptime'])}, "
            f"last seen {when(state['seen_ts'])} ({duration(state['age_h'] * 3600)} ago), "
            f"starts 24 h / 7 d: {state['starts_24h']} / {state['starts_7d']}"
        )
    # 3. Orphans
    lines += [
        f"{name}: running for inactive experiment {status.experiment_id(name)}"
        for name in cell.orphans
    ]
    return "\n".join(lines)


def status_grid(snapshot: Snapshot) -> dag.AgGrid:
    """
    Colour grid: one row per node, the main and the extra containers as column groups.

    Args:
        snapshot (Snapshot): Loaded data.

    Returns:
        dag.AgGrid: The grid (id status-grid).
    """
    # 1. Rows: text, style id and tooltip of every container cell
    styles: Dict[str, int] = {}
    rows = []
    for node in status.ordered(snapshot.nodes).itertuples():
        row: Dict[str, Any] = {
            "node_id": node.node_id,
            "status": node.status,
            "municipality": blank(node.municipality),
        }
        for container in status.MAIN + status.EXTRA:
            cell = snapshot.summary.cells[node.node_id, container]
            style = json.dumps(
                palette.cell_style(cell, node.status == "TESTING"), sort_keys=True
            )
            row[container] = palette.cell_text(cell)
            row[f"{container}__style"] = styles.setdefault(style, len(styles))
            row[f"{container}__tip"] = hover(node.node_id, node.status, container, cell)
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
            "headerName": container,
            "field": container,
            "tooltipField": f"{container}__tip",
            "width": 130,
            "cellStyle": {"styleConditions": conditions},
        }

    # 3. Grid
    columns = [
        {
            "headerName": "node",
            "field": "node_id",
            "width": 90,
            "pinned": "left",
            "filter": "agNumberColumnFilter",
        },
        {**status_column(), "pinned": "left"},
        {
            "headerName": "municipality",
            "field": "municipality",
            "width": 130,
            "pinned": "left",
        },
        {"headerName": "main containers", "children": [column(c) for c in status.MAIN]},
        {
            "headerName": "extra containers",
            "children": [column(c) for c in status.EXTRA],
        },
    ]
    return dag.AgGrid(
        id="status-grid",
        rowData=rows,
        columnDefs=columns,
        defaultColDef=DEFAULT_COLUMN,
        dashGridOptions=GRID_OPTIONS,
        className="nne-grid",
        style={"height": "70vh"},
    )


def legend() -> html.Div:
    """
    Legend of the colour grid: classes with their limits, markers.

    Returns:
        html.Div: Swatches with text.
    """

    def item(style: Dict[str, str], text: str) -> html.Span:
        return html.Span([html.I(style=style), text])

    items = [
        item({"backgroundColor": palette.COLOUR[name][0]}, f"✓ running, uptime {limit}")
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
            f"{palette.SYMBOL[name]} {name}: last seen {limit}",
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
            "– never seen (main)",
        ),
        item({"border": palette.NONE_BORDER}, "not deployed (extra)"),
        item(
            {"boxShadow": f"inset 0 0 0 3px {palette.PARTIAL}"},
            "partial: some threads not running (count)",
        ),
        item(
            {"boxShadow": f"inset 0 0 0 3px {palette.ORPHAN}"},
            "⚠ udpping thread of an inactive experiment",
        ),
        item(
            {"backgroundImage": palette.FLAP_DOT},
            f"flapping: ≥ {status.FLAPPING} starts in 24 h",
        ),
        item({"border": palette.TESTING_BORDER}, "TESTING node"),
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
            "status": row.status,
            "municipality": blank(row.municipality),
            "issues": row.issues,
            "last_heartbeat": (
                "never"
                if math.isinf(row.silent_h)
                else f"{when(row.last_seen)} ({duration(row.silent_h * 3600)} ago)"
            ),
        }
        for row in found.itertuples()
    ]
    columns = [
        {
            "headerName": "node",
            "field": "node_id",
            "width": 90,
            "filter": "agNumberColumnFilter",
        },
        status_column(),
        {"headerName": "municipality", "field": "municipality", "width": 130},
        {
            "headerName": "issues",
            "field": "issues",
            "flex": 1,
            "wrapText": True,
            "autoHeight": True,
        },
        {
            "headerName": "last heartbeat (UTC)",
            "field": "last_heartbeat",
            "width": 230,
            "sortable": False,
        },
    ]
    return dag.AgGrid(
        id="problems-grid",
        rowData=rows,
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
        rowData=counts.to_dict("records"),
        columnDefs=[
            {"headerName": "status", "field": "status", "width": 130},
            {"headerName": "nodes", "field": "nodes"},
            {"headerName": "all main OK", "field": "all_main_ok"},
            {"headerName": "some issue", "field": "some_issue"},
            {"headerName": "nothing running", "field": "nothing_running"},
        ],
        dashGridOptions={**GRID_OPTIONS, "domLayout": "autoHeight"},
        className="nne-grid",
    )
    # 2. Nodes running each container per status group: "running / nodes"
    running = status.container_counts(snapshot.nodes, snapshot.summary)
    groups = [column for column in running.columns if column != "container"]
    rows: List[Dict[str, Any]] = [
        {
            "container": row["container"],
            **{g: f"{row[g]} / {nodes_per_group[g]}" for g in groups},
        }
        for row in running.to_dict("records")
    ]
    by_container = dag.AgGrid(
        id="overview-containers",
        rowData=rows,
        columnDefs=[{"headerName": "container", "field": "container", "width": 150}]
        + [{"headerName": f"{g} running", "field": g} for g in groups],
        dashGridOptions={**GRID_OPTIONS, "domLayout": "autoHeight"},
        className="nne-grid",
    )
    return html.Div([by_status, html.H3("Nodes running each container"), by_container])
