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
# Containers page: container status of the reported nodes
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
Containers page: container status of the reported nodes in sub-tabs Overview, Grid, Problems and
Node detail (documentation/DESIGN.md section 7). No page title: the header button and the sub-tabs
name the view.

Integrations:
    1. data.cache.CONTAINERS_CACHE - loaded data of settings.DATA_SOURCE.

Sample code:
    Served on / by the app (container_status_webpage.app).
"""

from typing import Any, Dict, List, Optional

import dash
from dash import Input, Output, State, callback, dcc, html

from container_status_webpage import settings
from container_status_webpage.components import grid
from container_status_webpage.components.formatting import when
from container_status_webpage.components.tabs import sub_tabs
from container_status_webpage.data import status
from container_status_webpage.data.cache import CONTAINERS_CACHE

dash.register_page(
    __name__, path="/", name="Containers", title="NorNet edge – containers", order=0
)


def grid_toolbar(rows: List[Dict[str, Any]]) -> html.Div:
    """
    Filter toolbar of the colour grid: status, state, node, municipality; the dropdowns search
    their options while typing.

    Args:
        rows (List[Dict[str, Any]]): Rows of the grid, source of the node and municipality options.

    Returns:
        html.Div: The controls (ids grid-status, grid-state, grid-node, grid-municipality).
    """
    statuses = [name.capitalize() for name in status.STATUS_ORDER]
    municipalities = sorted({row["municipality"] for row in rows} - {""})
    return html.Div(
        [
            html.Div(
                [
                    html.Span("Status"),
                    dcc.Checklist(
                        id="grid-status", options=statuses, value=statuses, inline=True
                    ),
                ],
                className="toolbar-item",
            ),
            html.Div(
                [
                    html.Span("State"),
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
                ],
                className="toolbar-item",
            ),
            html.Div(
                [
                    html.Span("Node"),
                    dcc.Dropdown(
                        id="grid-node",
                        options=[row["node_id"] for row in rows],
                        multi=True,
                        placeholder="All nodes",
                        className="toolbar-nodes",
                    ),
                ],
                className="toolbar-item",
            ),
            html.Div(
                [
                    html.Span("Municipality"),
                    dcc.Dropdown(
                        id="grid-municipality",
                        options=municipalities,
                        multi=True,
                        placeholder="All municipalities",
                        className="toolbar-municipalities",
                    ),
                ],
                className="toolbar-item",
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


def layout(**_query: str) -> html.Div:
    """
    Page content, built on every page load from the cached data.

    Args:
        **_query (str): Query string values (not used yet).

    Returns:
        html.Div: Data line and the sub-tabs.
    """
    # 1. Loaded data
    snapshot = CONTAINERS_CACHE.get()
    info = (
        f"Data: {settings.DATA_SOURCE} · {len(snapshot.nodes)} nodes · "
        f"loaded {when(snapshot.loaded_at)} UTC"
    )
    table = grid.status_grid(snapshot)
    rows = table.rowData  # pylint: disable=no-member
    # 2. Sub-tabs; the grid tab keeps all rows in a store for filter_grid
    return html.Div(
        [
            html.P(info, className="data-info"),
            sub_tabs(
                "containers-tabs",
                [
                    ("overview", "Overview", grid.overview(snapshot)),
                    (
                        "grid",
                        "Grid",
                        html.Div(
                            [
                                grid_toolbar(rows),
                                grid.legend(),
                                table,
                                dcc.Store(id="grid-rows", data=rows),
                            ]
                        ),
                    ),
                    ("problems", "Problems", grid.problems_grid(snapshot)),
                    (
                        "node",
                        "Node detail",
                        html.P(
                            "Placeholder: timeline, threads and experiments of one node."
                        ),
                    ),
                ],
            ),
        ]
    )
