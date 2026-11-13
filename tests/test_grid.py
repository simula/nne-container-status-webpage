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
# Checks of the tables of the pages Overview, Grid and Problems
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
Checks of the tables of Overview, Grid and Problems (view/grid.py) on the synthetic data:
every cell of the colour grid has a style condition, every colour class is used, the tooltip rows,
the toolbar filter, the problem list and the overview rows.

Sample code:
```bash
pytest tests/test_grid.py
```
"""

import pandas as pd

from container_status_webpage.model import pages, status
from container_status_webpage.model.snapshot import load
from container_status_webpage.view import grid, palette
from container_status_webpage.view.formatting import hours_span

# Properties of dash-ag-grid components (rowData, columnDefs) are created at run time
# pylint: disable=no-member

SNAPSHOT = load("synthetic", pd.Timestamp("2026-11-06 12:00"))


def test_status_grid_styles_every_cell():
    """One row per node; every container cell has the condition of its style id; every colour
    class appears."""
    data = pages.grid(SNAPSHOT)
    table = grid.status_grid(data.nodes, data.cells, data.states)
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


def test_tooltip_table_rows():
    """Tooltip of a UDP Ping cell with orphans: one row per expected thread, then the orphans
    flagged with their inactive experiment; every row has all table columns."""
    nodes = SNAPSHOT.nodes
    node_id = nodes.node_id[nodes.scenario == "inactive experiment"].iloc[0]
    cell = SNAPSHOT.summary.cells[node_id, "udpping"]
    tip = grid.hover(node_id, "DEPLOYED", "udpping", cell, SNAPSHOT.summary.states)
    assert tip["title"].startswith(f"Node {node_id} · Deployed · UDP Ping: ")
    assert [row["thread"] for row in tip["rows"]] == [
        name for name, _ in cell.threads
    ] + cell.orphans
    orphans = [row for row in tip["rows"] if row.get("orphan")]
    assert len(orphans) == len(cell.orphans) == 2
    assert all(row["state"].startswith("inactive experiment ") for row in orphans)
    columns = {
        "thread",
        "state",
        "colour",
        "version",
        "up",
        "seen",
        "ago",
        "starts",
        "restarts",
    }
    assert all(columns <= set(row) for row in tip["rows"])


def test_filter_rows():
    """Grid toolbar: status, any cell in a chosen state, node ids, municipalities; an empty control
    does not filter."""
    data = pages.grid(SNAPSHOT)
    rows = grid.status_grid(data.nodes, data.cells, data.states).rowData
    assert grid.filter_rows(rows, [], [], [], []) == rows
    testing = grid.filter_rows(rows, ["Testing"], [], [], [])
    assert testing and {row["status"] for row in testing} == {"Testing"}
    never = grid.filter_rows(rows, [], ["never", "orphan"], [], [])
    assert never and all({"never", "orphan"} & set(row["states"]) for row in never)
    assert len(never) < len(rows)
    nodes = [rows[0]["node_id"], rows[-1]["node_id"]]
    assert [
        row["node_id"] for row in grid.filter_rows(rows, [], [], nodes, [])
    ] == nodes
    place = next(row["municipality"] for row in rows if row["municipality"])
    found = grid.filter_rows(rows, [], [], [], [place])
    assert found and all(row["municipality"] == place for row in found)


def test_problems_grid_rows():
    """The problem list shows every node that is not fully OK; a node without heartbeat first, with
    no sort key (sorts first); the issues text filter is case-insensitive."""
    table = grid.problems_grid(pages.problems(SNAPSHOT).problems)
    assert len(table.rowData) == 32
    assert table.rowData[0]["last_heartbeat"] == "Not seen in 365 days"
    assert table.rowData[0]["last_seen"] is None
    found = grid.filter_rows(table.rowData, [], [], [], [], text="udp ping")
    assert found and all("UDP Ping" in row["issues"] for row in found)
    assert len(found) < len(table.rowData)


def test_overview_rows():
    """Overview: Deployed, Testing and All; one row per container with its display name."""
    data = pages.overview(SNAPSHOT)
    _, by_status, _, by_container = grid.overview(data.counts, data.running).children
    assert [row["status"] for row in by_status.rowData] == [
        "Deployed",
        "Testing",
        "All",
    ]
    assert [row["container"] for row in by_container.rowData] == [
        status.NAME[c] for c in status.MAIN + status.EXTRA
    ]


def test_legend_from_limits():
    """The legend writes the class limits of model/limits.py: hours up to 24 h, days from 24 h on,
    one receiver restart rule."""
    texts = [part.children[1] for part in grid.legend().children]
    assert texts[:8] == [
        "✓ Running, uptime < 1 h",
        "✓ Running, uptime 1–24 h",
        "✓ Running, uptime 1–7 d",
        "✓ Running, uptime > 7 d",
        "! Late: last seen 2–6 h",
        "! Stale: last seen 6–24 h",
        "× Down: last seen 1–7 d",
        "× Long down: last seen > 7 d",
    ]
    assert "↻ Receiver restarts: > 60 per hour" in texts
    assert hours_span(12, 48) == "12 h – 2 d"
