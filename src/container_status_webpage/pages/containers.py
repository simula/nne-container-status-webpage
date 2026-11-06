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
Containers page: container status of the reported nodes. Skeleton with placeholder sub-tabs; the
dashboard follows in phase 3 (documentation/DESIGN.md).

Sample code:
    Served on / by the app (container_status_webpage.app).
"""

from typing import List, Tuple

import dash
from dash import html

from container_status_webpage.components.tabs import sub_tabs

dash.register_page(
    __name__, path="/", name="Containers", title="NorNet edge – containers", order=0
)

# Sub-tabs: value, label, placeholder text
TABS: List[Tuple[str, str, str]] = [
    ("overview", "Overview", "nodes per status and how many run each container."),
    ("grid", "Grid", "colour grid of nodes and containers."),
    ("problems", "Problems", "nodes that are not fully OK."),
    ("node", "Node detail", "timeline, threads and experiments of one node."),
]


def layout(**_query: str) -> html.Div:
    """
    Page content, built on every page load.

    Args:
        **_query (str): Query string values (not used yet).

    Returns:
        html.Div: Title and the sub-tabs.
    """
    return html.Div(
        [
            html.H2("Container status"),
            sub_tabs(
                "containers-tabs",
                [
                    (value, label, html.P(f"Placeholder: {text}"))
                    for value, label, text in TABS
                ],
            ),
        ]
    )
