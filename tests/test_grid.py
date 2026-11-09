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
# Checks of the tables of the Containers page
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
Checks of the tables of the Containers page (components/grid.py) on the synthetic data: every cell
of the colour grid has a style condition, every colour class is used, the problem list and the
overview rows.

Sample code:
```bash
pytest tests/test_grid.py
```
"""

import pandas as pd

from container_status_webpage.components import grid, palette
from container_status_webpage.data import status
from container_status_webpage.data.cache import load

# Properties of dash-ag-grid components (rowData, columnDefs) are created at run time
# pylint: disable=no-member

SNAPSHOT = load("synthetic", pd.Timestamp("2026-11-06 12:00"))


def test_status_grid_styles_every_cell():
    """One row per node; every container cell has the condition of its style id; every colour
    class appears."""
    table = grid.status_grid(SNAPSHOT)
    assert len(table.rowData) == len(SNAPSHOT.nodes)
    groups = {
        group["headerName"]: group for group in table.columnDefs if "children" in group
    }
    assert [c["field"] for c in groups["Main containers"]["children"]] == list(
        status.MAIN
    )
    assert [c["field"] for c in groups["Extra containers"]["children"]] == list(
        status.EXTRA
    )
    backgrounds = set()
    for column in (
        groups["Main containers"]["children"] + groups["Extra containers"]["children"]
    ):
        conditions = {
            c["condition"]: c["style"] for c in column["cellStyle"]["styleConditions"]
        }
        for row in table.rowData:
            style = conditions[
                f"params.data.{column['field']}__style === {row[column['field'] + '__style']}"
            ]
            backgrounds.add(style["backgroundColor"])
    assert backgrounds == {background for background, _ in palette.COLOUR.values()}


def test_problems_grid_rows():
    """The problem list shows every node that is not fully OK; a node without heartbeat first."""
    table = grid.problems_grid(SNAPSHOT)
    assert len(table.rowData) == 26
    assert table.rowData[0]["last_heartbeat"] == "Never"


def test_overview_rows():
    """Overview: Deployed, Testing and All; one row per container with its display name."""
    by_status, _, by_container = grid.overview(SNAPSHOT).children
    assert [row["status"] for row in by_status.rowData] == [
        "Deployed",
        "Testing",
        "All",
    ]
    assert [row["container"] for row in by_container.rowData] == [
        status.NAME[c] for c in status.MAIN + status.EXTRA
    ]
