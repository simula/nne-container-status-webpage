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
    1. data.cache.CACHE - loaded data of settings.DATA_SOURCE.

Sample code:
    Served on / by the app (container_status_webpage.app).
"""

import dash
from dash import html

from container_status_webpage import settings
from container_status_webpage.components import grid
from container_status_webpage.components.formatting import when
from container_status_webpage.components.tabs import sub_tabs
from container_status_webpage.data.cache import CACHE

dash.register_page(
    __name__, path="/", name="Containers", title="NorNet edge – containers", order=0
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
    snapshot = CACHE.get()
    info = (
        f"Data: {settings.DATA_SOURCE} · {len(snapshot.nodes)} nodes · "
        f"loaded {when(snapshot.loaded_at)} UTC"
    )
    # 2. Sub-tabs
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
                        html.Div([grid.legend(), grid.status_grid(snapshot)]),
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
