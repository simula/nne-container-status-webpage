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
# Controller of the Grid page: page load, toolbar filter, row click
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
Controller of the Grid page (/grid): builds the page, filters the rows by the toolbar and opens the
Node page of a clicked row.

Integrations:
    1. model.cache.CONTAINERS_CACHE - loaded data of settings.DATA_SOURCE.
    2. view.layouts, view.grid - page layout and the row filter.

Sample code:
    Registered as the layout of /grid in pages/containers.py; the callbacks register on import.
"""

from typing import Any, Dict, List, Optional

import dash
from dash import Input, Output, State, callback, html

from container_status_webpage.controller.node import click_query
from container_status_webpage.model.cache import CONTAINERS_CACHE
from container_status_webpage.view import layouts
from container_status_webpage.view.grid import filter_rows


def page(**_query: str) -> html.Div:
    """
    Grid page (/grid), built on every page load from the cached data.

    Args:
        **_query (str): URL query values (ignored).

    Returns:
        html.Div: The page (view.layouts.grid_page).
    """
    return layouts.grid_page(CONTAINERS_CACHE.get())


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
    return filter_rows(
        rows, statuses or [], states or [], nodes or [], municipalities or []
    )


@callback(
    Output("_pages_location", "href", allow_duplicate=True),
    Input("status-grid", "cellClicked"),
    prevent_initial_call=True,
)
def open_from_grid(cell: Optional[Dict[str, Any]]) -> str:
    """
    Opens the Node page of a clicked grid row, on a container cell also of that container.

    Args:
        cell (Optional[Dict[str, Any]]): Clicked cell of the grid.

    Returns:
        str: URL of the Node page.
    """
    return click_query(cell) if cell else dash.no_update
