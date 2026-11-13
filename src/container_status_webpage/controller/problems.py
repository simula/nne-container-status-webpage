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
# Controller of the Problems page: page load, toolbar filter, row click
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
Controller of the Problems page (/problems): builds the page, filters the rows by the toolbar and
opens the Node page of a clicked row.

Integrations:
    1. model.cache.CONTAINERS_CACHE - loaded data of settings.DATA_SOURCE.
    2. view.layouts, view.grid - page layout and the row filter.

Sample code:
    Registered as the layout of /problems in pages/containers.py; the callbacks register on import.
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
    Problems page (/problems), built on every page load from the cached data.

    Args:
        **_query (str): URL query values (ignored).

    Returns:
        html.Div: The page (view.layouts.problems_page).
    """
    return layouts.problems_page(CONTAINERS_CACHE.get())


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
    return filter_rows(
        rows, statuses or [], [], nodes or [], municipalities or [], text=text or ""
    )


@callback(
    Output("_pages_location", "href", allow_duplicate=True),
    Input("problems-grid", "cellClicked"),
    prevent_initial_call=True,
)
def open_from_problems(cell: Optional[Dict[str, Any]]) -> str:
    """
    Opens the Node page of a clicked problem list row.

    Args:
        cell (Optional[Dict[str, Any]]): Clicked cell of the problem list.

    Returns:
        str: URL of the Node page.
    """
    return click_query(cell) if cell else dash.no_update
