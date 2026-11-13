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
# Controller of the Overview page: page load, map filter, map click
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
Controller of the Overview page (/): builds the page, draws the map again for the checked statuses
and opens the Node page of a clicked dot.

Integrations:
    1. model.cache.CONTAINERS_CACHE - loaded data of settings.DATA_SOURCE; model.pages - page
       data built from it.
    2. view.layouts, view.nodemap - page layout and map figure.

Sample code:
    Registered as the layout of / in pages/containers.py; the callbacks register on import.
"""

from typing import Any, Dict, List, Optional

import dash
from dash import Input, Output, State, callback, html

from container_status_webpage.controller.node import node_query
from container_status_webpage.model import pages
from container_status_webpage.model.cache import CONTAINERS_CACHE
from container_status_webpage.view import layouts
from container_status_webpage.view.nodemap import node_map


def click_query(click: Dict[str, Any]) -> str:
    """
    URL of the Node page of a clicked dot.

    Args:
        click (Dict[str, Any]): clickData of the map (customdata is the node id).

    Returns:
        str: URL of the Node page.
    """
    return node_query(click["points"][0]["customdata"])


def page(**_query: str) -> html.Div:
    """
    Overview page (/), built on every page load from the cached data.

    Args:
        **_query (str): URL query values (ignored).

    Returns:
        html.Div: The page (view.layouts.overview).
    """
    return layouts.overview(pages.overview(CONTAINERS_CACHE.get()))


@callback(
    Output("node-map", "figure"),
    Input("map-status", "value"),
    State("map-nodes", "data"),
    prevent_initial_call=True,
)
def filter_map(statuses: Optional[List[str]], rows: List[Dict[str, Any]]) -> Any:
    """
    Map of the page's nodes with a checked status: drawn from the map rows of the open page, not
    from the cache, so the map keeps the data of the tables after a refresh.

    Args:
        statuses (Optional[List[str]]): Checked statuses.
        rows (List[Dict[str, Any]]): Map rows of the page (map-nodes).

    Returns:
        Any: The figure.
    """
    return node_map(pages.checked_map_nodes(rows, statuses or []))


@callback(
    Output("_pages_location", "href", allow_duplicate=True),
    Input("node-map", "clickData"),
    prevent_initial_call=True,
)
def open_from_map(click: Optional[Dict[str, Any]]) -> str:
    """
    Opens the Node page of a clicked map dot.

    Args:
        click (Optional[Dict[str, Any]]): Clicked dot of the map.

    Returns:
        str: URL of the Node page.
    """
    return click_query(click) if click else dash.no_update
