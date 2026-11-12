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
# Checks of the node map
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
Checks of the node map (components/nodemap.py) on the synthetic data: one dot per located node,
the status filter, worst grades drawn last, the click target.

Sample code:
```bash
pytest tests/test_nodemap.py
```
"""

import json

import pandas as pd

from container_status_webpage.components import nodemap
from container_status_webpage.data import status
from container_status_webpage.data.cache import load

SNAPSHOT = load("synthetic", pd.Timestamp("2026-11-06 12:00"))


def node_ids(figure) -> list:
    """Node ids of all dots of a map."""
    return [int(i) for trace in figure.data for i in trace.customdata]


def test_dots_filter_and_click():
    """Every node with a location is one dot, the nodes without municipality none; the status
    filter keeps its nodes; grades from best to worst, so the worst lie on top; a click opens the
    Node page of the dot."""
    nodes = SNAPSHOT.nodes.set_index("node_id")
    figure = nodemap.node_map(SNAPSHOT, ["Deployed", "Testing"])
    assert sorted(node_ids(figure)) == sorted(nodes.index[nodes.loc_lat.notna()])
    assert nodes.municipality[nodes.loc_lat.isna()].isna().all()
    testing = nodemap.node_map(SNAPSHOT, ["Testing"])
    assert set(nodes.status[node_ids(testing)]) == {"TESTING"}
    grades = [trace.name.split(" (")[0].lower() for trace in figure.data]
    assert grades == sorted(grades, key=status.GRADE_ORDER.index)
    node_id = node_ids(figure)[0]
    click = {"points": [{"customdata": node_id}]}
    assert nodemap.click_query(click) == f"/node?node={node_id}"
    # customdata as plain JSON lists, so that dcc.Graph passes it with the click
    traces = json.loads(figure.to_json())["data"]
    assert all(isinstance(trace["customdata"], list) for trace in traces)
