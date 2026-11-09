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
# Read-only loader of the nne and report databases
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
Read-only loader of the frames nodes, experiments and raw from the nne and report databases
(documentation/DESIGN.md sections 2, 3 and 10); SELECT statements only.

Integrations:
    1. nnedbtools - credentials (identityprovider), engines (connection), queries, tables.
    2. data.status - status groups of the reported nodes.

Sample code:
```python
from container_status_webpage.data.loader import load_database

nodes, experiments, raw = load_database(".db_env")
```
"""

from typing import Tuple

import pandas as pd
from nnedbtools import identityprovider
from nnedbtools.connection import engines
from nnedbtools.queries.address import select_from_nne_node_adreess_and_nne_addresss
from nnedbtools.queries.augumentation import select_from_nne_measurement_instance
from nnedbtools.tables import NneAddressType, NneNodeAddress, ReportContainerRawdata
from sqlalchemy import select, text

from container_status_webpage.data.status import SATELLITE_NODES, STATUS_ORDER

# Candidate nodes with their status and counts: an active experiment bound to a network and a
# service, node_id >= 3100, or a satellite node; interfaces without service 7 (power switch SIM),
# experiments + 1 for metadata
NODES_SQL: str = f"""
SELECT n.node_id,
       s.value AS status,
       (SELECT COUNT(*) FROM node_info i
         WHERE i.node_id = n.node_id AND i.valid_to IS NULL AND i.service_id <> 7) AS interfaces,
       (SELECT COUNT(*) FROM measurement_instance m
         WHERE m.node_id = n.node_id AND m.stop_time IS NULL) + 1 AS experiments
  FROM (SELECT DISTINCT node_id FROM measurement_instance
         WHERE node_id IN ({", ".join(map(str, SATELLITE_NODES))})
            OR (stop_time IS NULL AND network_id <> 0 AND service_id <> 0 AND node_id >= 3100)) n
  LEFT JOIN node_status ns ON ns.node_id = n.node_id
  LEFT JOIN status s ON s.id = ns.status_id
"""


def load_database(env_file: str) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Frames of the reported nodes from the databases.

    Args:
        env_file (str): nnedbtools env file of the nne-reader account; loaded once per process.

    Returns:
        Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]: nodes (node_id, status, interfaces,
        experiments, municipality), experiments (measurement_instance rows of the nodes, active
        and stopped), raw (report.container_rawdata).
    """
    # 1. Credentials and engines, once per process
    if engines.nne_engine is None:
        identityprovider.load_from_enviroment(env_file)
    # 2. Reported nodes: status DEPLOYED or TESTING with an active interface, or a satellite node
    nodes = pd.read_sql(text(NODES_SQL), engines.nne_engine)
    satellite = nodes.node_id.isin(SATELLITE_NODES)
    nodes.loc[satellite, "status"] = "DEPLOYED"
    # Satellite nodes run no metadata container
    nodes.loc[satellite, "experiments"] -= 1
    nodes = nodes[
        satellite | (nodes.status.isin(STATUS_ORDER) & (nodes.interfaces > 0))
    ]
    node_ids = nodes.node_id.tolist()
    # 3. Municipality of the current site address (optional)
    site = pd.read_sql(
        select_from_nne_node_adreess_and_nne_addresss(node_ids).where(
            NneNodeAddress.address_type == NneAddressType.site,
            NneNodeAddress.valid_to.is_(None),
        ),
        engines.nne_engine,
    ).drop_duplicates("node_id")
    nodes = nodes.merge(site[["node_id", "municipality"]], on="node_id", how="left")
    # 4. Experiments of the reported nodes and the container runs
    experiments = pd.read_sql(
        select_from_nne_measurement_instance(node_ids), engines.nne_engine
    )
    raw = pd.read_sql(select(ReportContainerRawdata), engines.report_engine)
    return nodes.reset_index(drop=True), experiments, raw
