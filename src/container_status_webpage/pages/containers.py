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
# Container status pages: Overview, Grid, Problems, Node detail
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
Container status pages of the reported nodes: Overview (map and counts), Grid, Problems and Node
detail (documentation/DESIGN.md section 7), registered here with dash.register_page. No page
title: the header button names the view.

Integrations:
    1. data.cache.CONTAINERS_CACHE - loaded data of settings.DATA_SOURCE.

Sample code:
    Served on /, /grid, /problems and /node by the app (container_status_webpage.app).
"""

from typing import Any, Dict, List, Optional

import dash
import pandas as pd
from dash import Input, Output, Patch, State, callback, dcc, html

from container_status_webpage import settings
from container_status_webpage.components import grid
from container_status_webpage.components.formatting import when
from container_status_webpage.components.node import (
    DEFAULT_RANGE,
    RANGES,
    click_query,
    experiments_table,
)
from container_status_webpage.components.node import header as node_header
from container_status_webpage.components.node import (
    node_query,
    parameters_view,
    run_detail,
    span,
    threads_table,
    timeline,
    x_range,
)
from container_status_webpage.components.nodemap import click_query as map_query
from container_status_webpage.components.nodemap import node_map
from container_status_webpage.data import status
from container_status_webpage.data.cache import CONTAINERS_CACHE, Snapshot


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
    statuses = [name.capitalize() for name in status.STATUS_ORDER]
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


@callback(
    Output("status-grid", "rowData"),
    Input("grid-status", "value"),
    Input("grid-state", "value"),
    Input("grid-node", "value"),
    Input("grid-municipality", "value"),
    State("grid-rows", "data"),
    prevent_initial_call=True,
)
def filter_grid(
    statuses: Optional[List[str]],
    states: Optional[List[str]],
    nodes: Optional[List[int]],
    municipalities: Optional[List[str]],
    rows: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Rows of the colour grid that match the toolbar.

    Args:
        statuses (Optional[List[str]]): Checked statuses.
        states (Optional[List[str]]): Selected states.
        nodes (Optional[List[int]]): Selected node ids.
        municipalities (Optional[List[str]]): Selected municipalities.
        rows (List[Dict[str, Any]]): All rows of the grid.

    Returns:
        List[Dict[str, Any]]: Matching rows.
    """
    return grid.filter_rows(
        rows, statuses or [], states or [], nodes or [], municipalities or []
    )


@callback(
    Output("problems-grid", "rowData"),
    Input("problems-status", "value"),
    Input("problems-text", "value"),
    Input("problems-node", "value"),
    Input("problems-municipality", "value"),
    State("problems-rows", "data"),
    prevent_initial_call=True,
)
def filter_problems(
    statuses: Optional[List[str]],
    text: Optional[str],
    nodes: Optional[List[int]],
    municipalities: Optional[List[str]],
    rows: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Rows of the problem list that match the toolbar.

    Args:
        statuses (Optional[List[str]]): Checked statuses.
        text (Optional[str]): Text in the issues.
        nodes (Optional[List[int]]): Selected node ids.
        municipalities (Optional[List[str]]): Selected municipalities.
        rows (List[Dict[str, Any]]): All rows of the problem list.

    Returns:
        List[Dict[str, Any]]: Matching rows.
    """
    return grid.filter_rows(
        rows, statuses or [], [], nodes or [], municipalities or [], text=text or ""
    )


@callback(
    Output("node-map", "figure"),
    Input("map-status", "value"),
    prevent_initial_call=True,
)
def filter_map(statuses: Optional[List[str]]) -> Any:
    """
    Map of the nodes with a checked status.

    Args:
        statuses (Optional[List[str]]): Checked statuses.

    Returns:
        Any: The figure.
    """
    return node_map(CONTAINERS_CACHE.get(), statuses or [])


# Each page opens the node detail from its own component: a callback on the components of several
# pages would miss those of the pages not shown. The empty values the selector, the tables and the
# map report when they appear change nothing.


@callback(
    Output("_pages_location", "href", allow_duplicate=True),
    Input("node-select", "value"),
    prevent_initial_call=True,
)
def open_selected(node_id: Optional[int]) -> str:
    """
    Opens the node detail of the selected node.

    Args:
        node_id (Optional[int]): Selected node.

    Returns:
        str: URL of the node detail.
    """
    return dash.no_update if node_id is None else node_query(node_id)


@callback(
    Output("_pages_location", "href", allow_duplicate=True),
    Input("status-grid", "cellClicked"),
    prevent_initial_call=True,
)
def open_from_grid(cell: Optional[Dict[str, Any]]) -> str:
    """
    Opens the node detail of a clicked grid row, on a container cell also of that container.

    Args:
        cell (Optional[Dict[str, Any]]): Clicked cell of the grid.

    Returns:
        str: URL of the node detail.
    """
    return click_query(cell) if cell else dash.no_update


@callback(
    Output("_pages_location", "href", allow_duplicate=True),
    Input("problems-grid", "cellClicked"),
    prevent_initial_call=True,
)
def open_from_problems(cell: Optional[Dict[str, Any]]) -> str:
    """
    Opens the node detail of a clicked problem list row.

    Args:
        cell (Optional[Dict[str, Any]]): Clicked cell of the problem list.

    Returns:
        str: URL of the node detail.
    """
    return click_query(cell) if cell else dash.no_update


@callback(
    Output("_pages_location", "href", allow_duplicate=True),
    Input("node-map", "clickData"),
    prevent_initial_call=True,
)
def open_from_map(click: Optional[Dict[str, Any]]) -> str:
    """
    Opens the node detail of a clicked map dot.

    Args:
        click (Optional[Dict[str, Any]]): Clicked dot of the map.

    Returns:
        str: URL of the node detail.
    """
    return map_query(click) if click else dash.no_update


@callback(
    Output("node-run", "children"),
    Input("node-timeline", "clickData"),
    prevent_initial_call=True,
)
def show_run(click: Dict[str, Any]) -> html.Table:
    """
    Detail of the clicked timeline segment.

    Args:
        click (Dict[str, Any]): clickData of the timeline.

    Returns:
        html.Table: The detail (run_detail).
    """
    return run_detail(click["points"][0]["customdata"])


@callback(
    Output("node-parameters", "children"),
    Input("node-experiments", "cellClicked"),
    State("node-experiments", "rowData"),
    prevent_initial_call=True,
)
def show_parameters(cell: Dict[str, Any], rows: List[Dict[str, Any]]) -> html.Div:
    """
    Parameters of the clicked experiment.

    Args:
        cell (Dict[str, Any]): cellClicked of the experiments table (rowId is the experiment id).
        rows (List[Dict[str, Any]]): Rows of the experiments table.

    Returns:
        html.Div: The parameters (parameters_view).
    """
    row = next(row for row in rows if str(row["id"]) == cell["rowId"])
    return parameters_view(row["id"], row["parameters"])


@callback(
    Output("node-timeline", "figure"),
    Input("node-range", "value"),
    State("node-span", "data"),
    prevent_initial_call=True,
)
def set_range(choice: str, first_now: List[str]) -> Patch:
    """
    X range of the timeline for the chosen range button.

    Args:
        choice (str): Value of node.RANGES.
        first_now (List[str]): First start and load time of the timeline (node.span).

    Returns:
        Patch: The new x range of the figure.
    """
    first, now = (pd.Timestamp(value) for value in first_now)
    figure = Patch()
    figure["layout"]["xaxis"]["range"] = [str(t) for t in x_range(first, now, choice)]
    figure["layout"]["xaxis"]["autorange"] = False
    return figure


def node_view(
    snapshot: Snapshot, node_id: Optional[int], container: Optional[str]
) -> html.Div:
    """
    Node detail: node selector and the detail of the selected node: header, timeline, detail
    of the clicked segment.

    Args:
        snapshot (Snapshot): Loaded data.
        node_id (Optional[int]): Selected node, None for none.
        container (Optional[str]): Container highlighted in the timeline, None for none.

    Returns:
        html.Div: Selector (id node-select) and detail.
    """
    selector = item(
        "Node",
        dcc.Dropdown(
            id="node-select",
            options=status.ordered(snapshot.nodes).node_id.tolist(),
            value=node_id,
            placeholder="Select a node",
            className="toolbar-nodes",
        ),
    )
    if node_id is None:
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
    return html.Div(
        [
            html.Div([selector, ranges], className="toolbar"),
            node_header(snapshot, node_id),
            timeline(snapshot, node_id, container),
            dcc.Store(id="node-span", data=[str(t) for t in span(snapshot, node_id)]),
            html.Div(
                html.P("Click a bar for its detail.", className="data-info"),
                id="node-run",
            ),
            html.H3("Threads"),
            threads_table(snapshot, node_id),
            html.H3("Experiments"),
            experiments_table(snapshot, node_id),
            html.Div(
                html.P(
                    "Click an experiment for its parameters.", className="data-info"
                ),
                id="node-parameters",
            ),
        ]
    )


def map_view(snapshot: Snapshot) -> html.Div:
    """
    Map half of the Overview: status filter, the number of nodes without location, the zoomable
    map; a click on a dot opens the node detail.

    Args:
        snapshot (Snapshot): Loaded data.

    Returns:
        html.Div: Toolbar and map (ids map-status, node-map).
    """
    statuses = [name.capitalize() for name in status.STATUS_ORDER]
    nodes = snapshot.nodes
    missing = int((nodes.loc_lat.isna() | nodes.loc_lon.isna()).sum())
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
                    html.Span(f"{missing} nodes without location"),
                ],
                className="toolbar",
            ),
            dcc.Graph(
                id="node-map",
                figure=node_map(snapshot, statuses),
                config={"scrollZoom": True},
            ),
        ]
    )


def data_line(snapshot: Snapshot) -> html.P:
    """
    Data line on top of every page: data source, number of nodes and load time.

    Args:
        snapshot (Snapshot): Loaded data.

    Returns:
        html.P: The line.
    """
    return html.P(
        f"Data: {settings.DATA_SOURCE} · {len(snapshot.nodes)} nodes · "
        f"loaded {when(snapshot.loaded_at)} UTC",
        className="data-info",
    )


def overview(**_query: str) -> html.Div:
    """
    Overview page (/), built on every page load from the cached data.

    Args:
        **_query (str): URL query values (ignored).

    Returns:
        html.Div: Data line, map and count tables.
    """
    snapshot = CONTAINERS_CACHE.get()
    return html.Div(
        [
            data_line(snapshot),
            html.Div(
                [map_view(snapshot), grid.overview(snapshot)],
                className="overview-split",
            ),
        ]
    )


def grid_page(**_query: str) -> html.Div:
    """
    Grid page (/grid); all rows kept in a store for filter_grid.

    Args:
        **_query (str): URL query values (ignored).

    Returns:
        html.Div: Data line, toolbar, legend and grid.
    """
    snapshot = CONTAINERS_CACHE.get()
    table = grid.status_grid(snapshot)
    # pylint: disable-next=no-member
    rows = table.rowData
    return html.Div(
        [
            data_line(snapshot),
            toolbar(
                "grid",
                rows,
                item(
                    "State",
                    dcc.Dropdown(
                        id="grid-state",
                        options=[
                            {"label": name.capitalize(), "value": name}
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
        ]
    )


def problems_page(**_query: str) -> html.Div:
    """
    Problems page (/problems); all rows kept in a store for filter_problems.

    Args:
        **_query (str): URL query values (ignored).

    Returns:
        html.Div: Data line, toolbar and problem list.
    """
    snapshot = CONTAINERS_CACHE.get()
    problems = grid.problems_grid(snapshot)
    # pylint: disable-next=no-member
    rows = problems.rowData
    return html.Div(
        [
            data_line(snapshot),
            toolbar(
                "problems",
                rows,
                item(
                    "Issues",
                    dcc.Input(
                        id="problems-text",
                        type="text",
                        placeholder="Text in the issues",
                        className="toolbar-text",
                    ),
                ),
            ),
            problems,
            dcc.Store(id="problems-rows", data=rows),
        ]
    )


def node_page(
    node: Optional[str] = None, container: Optional[str] = None, **_query: str
) -> html.Div:
    """
    Node detail page (/node?node=<id>&container=<name>); unknown values select nothing.

    Args:
        node (Optional[str], optional): Node to show. Defaults to None.
        container (Optional[str], optional): Container highlighted in the timeline. Defaults to
            None.
        **_query (str): Other query values (ignored).

    Returns:
        html.Div: Data line and the node detail.
    """
    snapshot = CONTAINERS_CACHE.get()
    node_id = (
        int(node)
        if node and node.isdigit() and int(node) in set(snapshot.nodes.node_id)
        else None
    )
    return html.Div(
        [
            data_line(snapshot),
            node_view(
                snapshot, node_id, container if container in status.NAME else None
            ),
        ]
    )


# The four views as pages, one header button each (components/frame.py)
dash.register_page(
    "overview",
    path="/",
    name="Overview",
    title="NorNet edge – Overview",
    order=0,
    layout=overview,
)
dash.register_page(
    "grid",
    path="/grid",
    name="Grid",
    title="NorNet edge – Grid",
    order=1,
    layout=grid_page,
)
dash.register_page(
    "problems",
    path="/problems",
    name="Problems",
    title="NorNet edge – Problems",
    order=2,
    layout=problems_page,
)
dash.register_page(
    "node",
    path="/node",
    name="Node detail",
    title="NorNet edge – Node detail",
    order=3,
    layout=node_page,
)
