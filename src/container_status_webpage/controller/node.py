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
# Controller of the Node page: URL, page load, selector, range, clicks
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
Controller of the Node page (/node?node=<id>&container=<name>): the URL of the page, the page built
from its query, the node selector, the range buttons and date pickers of the timeline, the detail of
a clicked segment and the parameters of a clicked experiment.

Integrations:
    1. model.cache.CONTAINERS_CACHE - loaded data of settings.DATA_SOURCE.
    2. model.timeline - x ranges of the timeline.
    3. view.layouts, view.node - page layout, segment detail and parameters.

Sample code:
    Registered as the layout of /node in pages/containers.py; the callbacks register on import.
"""

from typing import Any, Dict, List, Optional, Tuple

import dash
import pandas as pd
from dash import Input, Output, Patch, State, callback, html

from container_status_webpage.model import status
from container_status_webpage.model.cache import CONTAINERS_CACHE
from container_status_webpage.model.timeline import picker_range, x_range
from container_status_webpage.view import layouts
from container_status_webpage.view.node import parameters_view, run_detail


def node_query(node_id: Any, container: Optional[str] = None) -> str:
    """
    URL of the Node page (page builds the page from its query).

    Args:
        node_id (Any): Node id.
        container (Optional[str], optional): Container to highlight. Defaults to None.

    Returns:
        str: URL, e.g. "/node?node=90001&container=udpping".
    """
    return f"/node?node={node_id}" + (f"&container={container}" if container else "")


def click_query(cell: Dict[str, Any]) -> str:
    """
    URL of a clicked grid or problem list cell: its node, and its container for a container
    cell.

    Args:
        cell (Dict[str, Any]): cellClicked of the AG Grid (rowId is the node id).

    Returns:
        str: URL of the Node page.
    """
    column = cell["colId"]
    return node_query(cell["rowId"], column if column in status.NAME else None)


def page(
    node: Optional[str] = None, container: Optional[str] = None, **_query: str
) -> html.Div:
    """
    Node page (/node?node=<id>&container=<name>), built on every page load from the cached data;
    unknown values select nothing.

    Args:
        node (Optional[str], optional): Node to show. Defaults to None.
        container (Optional[str], optional): Container highlighted in the timeline. Defaults to
            None.
        **_query (str): Other query values (ignored).

    Returns:
        html.Div: The page (view.layouts.node_page).
    """
    snapshot = CONTAINERS_CACHE.get()
    node_id = (
        int(node)
        if node and node.isdigit() and int(node) in set(snapshot.nodes.node_id)
        else None
    )
    return layouts.node_page(
        snapshot, node_id, container if container in status.NAME else None
    )


@callback(
    Output("_pages_location", "href", allow_duplicate=True),
    Input("node-select", "value"),
    prevent_initial_call=True,
)
def open_selected(node_id: Optional[int]) -> str:
    """
    Opens the Node page of the selected node.

    Args:
        node_id (Optional[int]): Selected node.

    Returns:
        str: URL of the Node page.
    """
    return dash.no_update if node_id is None else node_query(node_id)


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
    Output("node-range", "value"),
    Output("node-from", "date"),
    Output("node-to", "date"),
    Output("node-timeline", "figure"),
    Input("node-range", "value"),
    Input("node-from", "date"),
    Input("node-to", "date"),
    State("node-span", "data"),
    prevent_initial_call=True,
)
def set_range(
    choice: str,
    from_date: Optional[str],
    to_date: Optional[str],
    first_now: List[str],
) -> Tuple[Any, Any, Any, Any]:
    """
    X range of the timeline: a range button sets its exact range (x_range) and fills the From / To
    pickers with its days; a picker sets whole days, To at most the load time (picker_range), and
    clears the range button (a click on it sets its range again). One callback for both, so its
    own outputs do not trigger it again.

    Args:
        choice (str): Value of model.timeline.RANGES.
        from_date (Optional[str]): From date.
        to_date (Optional[str]): To date.
        first_now (List[str]): First start and load time of the timeline (model.timeline.span).

    Returns:
        Tuple[Any, Any, Any, Any]: Range button, from date, to date and the Patch of the figure
            x range; no_update for an invalid picker range.
    """
    first, now = (pd.Timestamp(value) for value in first_now)
    if dash.ctx.triggered_id in ("node-from", "node-to"):
        shown = picker_range(from_date, to_date, now)
        button, dates = None, [dash.no_update, dash.no_update]
    else:  # a range button, or the page load
        shown = x_range(first, now, choice)
        button, dates = dash.no_update, [str(t.date()) for t in shown]
    if shown is None:
        return dash.no_update, dash.no_update, dash.no_update, dash.no_update
    figure = Patch()
    figure["layout"]["xaxis"]["range"] = [str(t) for t in shown]
    figure["layout"]["xaxis"]["autorange"] = False
    return button, dates[0], dates[1], figure
