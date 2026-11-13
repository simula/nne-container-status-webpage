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
# Page layouts: toolbar, data line and the content of the four pages
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
Layouts of the pages Overview, Grid, Problems and Node (documentation/DESIGN.md section 7) with the
parts they share: labelled toolbar items, the filter toolbar of the tables, the data line. No page
title: the header button names the view.

Integrations:
    1. model.pages - page data built by the controllers.
    2. view.grid, view.node, view.nodemap - tables, Node views and map.

Sample code:
```python
import pandas as pd
from container_status_webpage.model import pages
from container_status_webpage.model.snapshot import load
from container_status_webpage.view import layouts

layouts.overview(pages.overview(load("synthetic", pd.Timestamp("2026-11-06 12:00"))))
```
"""

from typing import Any, Dict, List

import pandas as pd
from dash import dcc, html

from container_status_webpage import settings
from container_status_webpage.model import orders, status
from container_status_webpage.model.pages import (
    GridData,
    NodeData,
    OverviewData,
    ProblemsData,
)
from container_status_webpage.model.timeline import DEFAULT_RANGE, RANGES
from container_status_webpage.view import grid
from container_status_webpage.view.formatting import when
from container_status_webpage.view.node import experiments_table
from container_status_webpage.view.node import header as node_header
from container_status_webpage.view.node import threads_table, timeline
from container_status_webpage.view.nodemap import node_map


def item(label: str, control: Any) -> html.Div:
    """
    One labelled control of a toolbar.

    Args:
        label (str): Label in front of the control.
        control (Any): Dash component.

    Returns:
        html.Div: Label and control.
    """
    return html.Div([html.Span(label), control], className="toolbar-item")


def toolbar(prefix: str, rows: List[Dict[str, Any]], own: html.Div) -> html.Div:
    """
    Filter toolbar of a table: status, the control of the page, node, municipality; the dropdowns
    search their options while typing.

    Args:
        prefix (str): Prefix of the control ids, e.g. "grid".
        rows (List[Dict[str, Any]]): Rows of the table, source of the node and municipality
            options.
        own (html.Div): Control of the page (item).

    Returns:
        html.Div: The controls (ids <prefix>-status, <prefix>-node, <prefix>-municipality).
    """
    statuses = [name.capitalize() for name in orders.STATUS_ORDER]
    municipalities = sorted({row["municipality"] for row in rows} - {""})
    return html.Div(
        [
            item(
                "Status",
                dcc.Checklist(
                    id=f"{prefix}-status", options=statuses, value=statuses, inline=True
                ),
            ),
            own,
            item(
                "Node",
                dcc.Dropdown(
                    id=f"{prefix}-node",
                    options=[row["node_id"] for row in rows],
                    multi=True,
                    placeholder="All nodes",
                    className="toolbar-nodes",
                ),
            ),
            item(
                "Municipality",
                dcc.Dropdown(
                    id=f"{prefix}-municipality",
                    options=municipalities,
                    multi=True,
                    placeholder="All municipalities",
                    className="toolbar-municipalities",
                ),
            ),
        ],
        className="toolbar",
    )


def data_line(node_count: int, loaded_at: pd.Timestamp) -> html.P:
    """
    Data line on top of every page: data source, number of nodes and load time.

    Args:
        node_count (int): Number of reported nodes.
        loaded_at (pd.Timestamp): Load time (UTC, naive).

    Returns:
        html.P: The line.
    """
    return html.P(
        f"Data: {settings.DATA_SOURCE} · {node_count} nodes · "
        f"loaded {when(loaded_at)} UTC",
        className="data-info",
    )


def map_view(nodes: pd.DataFrame, without_location: int) -> html.Div:
    """
    Map half of the Overview: status filter, the number of nodes without location, the zoomable
    map; a click on a dot opens the Node page.

    Args:
        nodes (pd.DataFrame): Nodes of the map, every status (pages.map_nodes).
        without_location (int): Number of nodes without location.

    Returns:
        html.Div: Toolbar, map and the map rows of the status filter (ids map-status, node-map,
            map-nodes).
    """
    statuses = [name.capitalize() for name in orders.STATUS_ORDER]
    return html.Div(
        [
            html.Div(
                [
                    item(
                        "Status",
                        dcc.Checklist(
                            id="map-status",
                            options=statuses,
                            value=statuses,
                            inline=True,
                        ),
                    ),
                    html.Span(f"{without_location} nodes without location"),
                ],
                className="toolbar",
            ),
            dcc.Graph(
                id="node-map",
                figure=node_map(nodes),
                config={"scrollZoom": True},
                responsive=True,
                style={"flex": 1, "minHeight": "400px"},
            ),
            dcc.Store(id="map-nodes", data=nodes.to_dict("records")),
        ],
        className="map-view",
    )


def node_view(data: NodeData) -> html.Div:
    """
    Node: node selector and the detail of the selected node: header, timeline, detail
    of the clicked segment.

    Args:
        data (NodeData): Page data.

    Returns:
        html.Div: Selector (id node-select) and detail.
    """
    selector = item(
        "Node",
        dcc.Dropdown(
            id="node-select",
            options=data.options,
            value=data.node_id,
            placeholder="Select a node",
            className="toolbar-nodes",
        ),
    )
    if data.node_id is None:
        return html.Div(
            [
                html.Div(selector, className="toolbar"),
                html.P("Select a node.", className="data-info"),
            ]
        )
    ranges = item(
        "Range",
        dcc.RadioItems(
            id="node-range",
            options=[
                {"label": "All" if value == "all" else f"{value} d", "value": value}
                for value in RANGES
            ],
            value=DEFAULT_RANGE,
            inline=True,
        ),
    )
    dates = [str(t.date()) for t in data.shown]
    pickers = [
        item(
            label,
            dcc.DatePickerSingle(
                id=f"node-{label.lower()}",
                date=date,
                min_date_allowed=str(data.first.date()),
                max_date_allowed=str(data.now.date()),
                display_format="YYYY-MM-DD",
            ),
        )
        for label, date in zip(("From", "To"), dates)
    ]
    return html.Div(
        [
            html.Div([selector, ranges, *pickers], className="toolbar"),
            node_header(data.node_id, data.node, data.networks),
            timeline(data.rows, data.segments, data.shown, data.container),
            dcc.Store(id="node-span", data=[str(data.first), str(data.now)]),
            html.Div(
                html.P("Click a bar for its detail.", className="data-info"),
                id="node-run",
            ),
            html.H3("Threads"),
            threads_table(data.threads),
            html.H3("Experiments"),
            experiments_table(data.experiments),
            html.Div(
                html.P(
                    "Click an experiment for its parameters.", className="data-info"
                ),
                id="node-parameters",
            ),
        ]
    )


def overview(data: OverviewData) -> html.Div:
    """
    Overview page (/).

    Args:
        data (OverviewData): Page data.

    Returns:
        html.Div: Data line, map and count tables.
    """
    return html.Div(
        [
            data_line(data.node_count, data.loaded_at),
            html.Div(
                [
                    map_view(data.map_nodes, data.without_location),
                    grid.overview(data.counts, data.running),
                ],
                className="overview-split",
            ),
        ],
        className="fill",
    )


def grid_page(data: GridData) -> html.Div:
    """
    Grid page (/grid); all rows kept in a store for filter_grid.

    Args:
        data (GridData): Page data.

    Returns:
        html.Div: Data line, toolbar, legend and grid.
    """
    table = grid.status_grid(data.nodes, data.cells, data.states)
    # pylint: disable-next=no-member
    rows = table.rowData
    return html.Div(
        [
            data_line(data.node_count, data.loaded_at),
            toolbar(
                "grid",
                rows,
                item(
                    "State",
                    dcc.Dropdown(
                        id="grid-state",
                        options=[
                            {
                                "label": status.state_text(name).capitalize(),
                                "value": name,
                            }
                            for name in grid.STATES
                        ],
                        multi=True,
                        placeholder="All states",
                        className="toolbar-states",
                    ),
                ),
            ),
            grid.legend(),
            table,
            dcc.Store(id="grid-rows", data=rows),
        ],
        className="fill",
    )


def problems_page(data: ProblemsData) -> html.Div:
    """
    Problems page (/problems); all rows kept in a store for filter_problems.

    Args:
        data (ProblemsData): Page data.

    Returns:
        html.Div: Data line, toolbar and problem list.
    """
    problems = grid.problems_grid(data.problems)
    # pylint: disable-next=no-member
    rows = problems.rowData
    return html.Div(
        [
            data_line(data.node_count, data.loaded_at),
            toolbar(
                "problems",
                rows,
                item(
                    "Issues",
                    dcc.Input(
                        id="problems-text",
                        type="text",
                        # One filter request after typing, not one per keystroke
                        debounce=0.5,
                        placeholder="Text in the issues",
                        className="toolbar-text",
                    ),
                ),
            ),
            problems,
            dcc.Store(id="problems-rows", data=rows),
        ],
        className="fill",
    )


def node_page(data: NodeData) -> html.Div:
    """
    Node page (/node).

    Args:
        data (NodeData): Page data.

    Returns:
        html.Div: Data line and the node view.
    """
    return html.Div([data_line(data.node_count, data.loaded_at), node_view(data)])
