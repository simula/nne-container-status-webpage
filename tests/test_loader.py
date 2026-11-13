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
# Nodes frame built from the database frames, on hand-made frames
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
Checks of the nodes frame built from the database frames (model/loader.py, reported) on hand-made
frames: status and interface filter, satellite nodes, site addresses, experiments of the reported
nodes. The database reads of load_database are not covered (they need the database).

Sample code:
```bash
pytest tests/test_loader.py
```
"""

import operator

import pandas as pd
import pytest

from container_status_webpage.model import limits
from container_status_webpage.model.loader import reported, select_rawdata

# Candidates as select_reported_node_candidates returns them; 4071 and 4072 are satellite nodes
CANDIDATES: pd.DataFrame = pd.DataFrame(
    {
        "node_id": [4000, 4001, 4002, 4003, 4004, 4071, 4072],
        "status": ["DEPLOYED", "TESTING", "DESTROYED", "DEPLOYED", None, None, None],
        "interfaces": [2, 1, 2, 0, 2, 0, 0],
        "experiments": [3, 2, 2, 2, 2, 3, 3],
    }
)
# Site addresses as the address query returns them: coordinates as text, more columns; 7056 is the
# site the satellite nodes are shown next to, 4072 has an address of its own
SITE: pd.DataFrame = pd.DataFrame(
    {
        "node_id": [4000, 7056, 4072],
        "street": ["Street 1", "Kristian Augusts gate 23", "Street 3"],
        "municipality": ["Bergen", "Oslo", "Lillestrøm"],
        "loc_lat": ["60.3913", "59.9172", "59.9781"],
        "loc_lon": ["5.3221", "10.7358", "11.0496"],
    }
)
# Experiments of the candidates
EXPERIMENTS: pd.DataFrame = pd.DataFrame(
    {"id": [1, 2, 3, 4, 5], "node_id": [4000, 4002, 4071, 4003, 4001]}
)


def test_status_and_interface_filter():
    """DEPLOYED and TESTING nodes with an active interface are reported; another status, no
    status or no interface is not."""
    nodes, _ = reported(CANDIDATES, SITE, EXPERIMENTS)
    assert nodes.node_id.tolist() == [4000, 4001, 4071, 4072]


def test_satellite_nodes():
    """Satellite nodes are DEPLOYED without status record and interface, one experiment fewer
    (no metadata container); the input frame stays unchanged."""
    nodes, _ = reported(CANDIDATES, SITE, EXPERIMENTS)
    satellites = nodes[nodes.node_id.isin([4071, 4072])]
    assert satellites.status.tolist() == ["DEPLOYED", "DEPLOYED"]
    assert satellites.experiments.tolist() == [2, 2]
    assert CANDIDATES.experiments.tolist() == [3, 2, 2, 2, 2, 3, 3]


def test_site():
    """Municipality and coordinates rounded to 2 decimals; a satellite node without address next to
    7056 (0.01° longitude per satellite), one with an address keeps it; no address leaves them
    empty."""
    nodes, _ = reported(CANDIDATES, SITE, EXPERIMENTS)
    assert nodes.columns.tolist() == [
        "node_id",
        "status",
        "interfaces",
        "experiments",
        "municipality",
        "loc_lat",
        "loc_lon",
    ]
    site = nodes.set_index("node_id")
    assert site.loc[4000, ["municipality", "loc_lat", "loc_lon"]].tolist() == [
        "Bergen",
        60.39,
        5.32,
    ]
    assert site.loc[4071, "municipality"] == "Oslo"
    assert site.loc[4071, ["loc_lat", "loc_lon"]].tolist() == pytest.approx(
        [59.92, 10.74 + 0.01]
    )
    assert site.loc[4072, ["municipality", "loc_lat", "loc_lon"]].tolist() == [
        "Lillestrøm",
        59.98,
        11.05,
    ]
    assert site.loc[4001, ["municipality", "loc_lat", "loc_lon"]].isna().all()


def test_experiments_of_reported_nodes():
    """Only the experiments of the reported nodes, numbered from 0."""
    _, experiments = reported(CANDIDATES, SITE, EXPERIMENTS)
    assert experiments.id.tolist() == [1, 3, 5]
    assert experiments.index.tolist() == [0, 1, 2]


def test_rawdata_of_the_last_year():
    """Only container runs with a heartbeat within HISTORY are read: filtered on seen_ts, so a run
    that started earlier and is still alive stays."""
    now = pd.Timestamp("2027-06-01 12:00")
    condition = select_rawdata(now).whereclause
    assert condition.left.name == "seen_ts"
    assert condition.operator is operator.ge
    assert condition.right.value == now - limits.HISTORY
