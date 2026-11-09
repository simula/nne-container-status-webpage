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
# Smoke tests of the webpage without a browser
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
Smoke tests of the webpage without a browser: pages registered from the installed package,
Containers sub-tabs, pages, layout and nne-viz assets served.

Sample code:
```bash
pytest
```
"""

import dash
import pytest

from container_status_webpage.app import server
from container_status_webpage.components.node import click_query


def test_pages_registered_in_order():
    """Pages come from pages/ of the package, Containers first."""
    assert [(page["name"], page["path"]) for page in dash.page_registry.values()] == [
        ("Containers", "/"),
        ("Plots", "/plots"),
    ]


def test_containers_page_has_placeholder_sub_tabs():
    """The Containers page has the sub-tabs Overview, Grid, Problems and Node detail."""
    page = next(page for page in dash.page_registry.values() if page["path"] == "/")
    tabs = page["layout"]()["containers-tabs"]
    assert [tab.label for tab in tabs.children] == [
        "Overview",
        "Grid",
        "Problems",
        "Node detail",
    ]


def test_node_detail_from_query():
    """/?tab=node&node=<id> opens Node detail with the node selected and its header; an unknown
    node selects none."""
    page = next(page for page in dash.page_registry.values() if page["path"] == "/")
    built = page["layout"](tab="node", node="90001")
    assert built["containers-tabs"].value == "node"
    assert built["node-select"].value == 90001
    texts = [part.children for part in built["node-header"].children]
    assert {"Node 90001", "Deployed", "Bergen"} <= set(texts)
    assert page["layout"](node="1")["node-select"].value is None


def test_click_opens_node_detail():
    """A click on a grid or problem list row opens its node; a container cell also names the
    container."""
    assert click_query({"colId": "node_id", "rowId": "90001"}) == (
        "?tab=node&node=90001"
    )
    assert click_query({"colId": "udpping", "rowId": "90001"}) == (
        "?tab=node&node=90001&container=udpping"
    )
    assert click_query({"colId": "issues", "rowId": "90003"}) == (
        "?tab=node&node=90003"
    )


@pytest.mark.parametrize(
    "path",
    [
        "/",
        "/plots",
        "/_dash-layout",
        "/assets/style.css",
        "/assets/nornet.png",
        "/assets/simulamet.svg",
    ],
)
def test_server_answers(path):
    """Pages, the page frame (layout) and the nne-viz assets are served."""
    assert server.test_client().get(path).status_code == 200
