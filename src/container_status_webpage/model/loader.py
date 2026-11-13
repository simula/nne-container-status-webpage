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
    2. model.status - status groups of the reported nodes.

Sample code:
```python
from container_status_webpage.model.loader import load_database

nodes, experiments, raw = load_database(".db_env")
```
"""

from typing import Tuple

import pandas as pd
from nnedbtools import identityprovider
from nnedbtools.connection import engines
from nnedbtools.queries.address import select_from_nne_node_adreess_and_nne_addresss
from nnedbtools.queries.augumentation import select_from_nne_measurement_instance
from nnedbtools.tables import (
    NneAddressType,
    NneMeasurementInstance,
    NneNodeAddress,
    NneNodeInfo,
    NneNodeStatusTable,
    NneStatus,
    ReportContainerRawdata,
)
from sqlalchemy import Select, and_, func, or_, select
from sqlalchemy.orm import aliased

from container_status_webpage.model.status import SATELLITE_NODES, STATUS_ORDER

# Satellite nodes have no address: the map shows them next to the site of this node (SimulaMet)
SATELLITE_SITE_NODE: int = 7056


def select_reported_node_candidates() -> Select:
    """
    Candidate nodes with their status and counts: nodes with an active experiment bound to a network
    and a service and node_id >= 3100, and the satellite nodes; interfaces without service 7 (power
    switch SIM), experiments + 1 for metadata. Nodes without a status record have status NULL.

    Returns:
        Select: Columns node_id, status, interfaces, experiments.
    """
    # 1. Candidate nodes
    instance = NneMeasurementInstance
    candidates = (
        select(instance.node_id)
        .distinct()
        .where(
            or_(
                instance.node_id.in_(SATELLITE_NODES),
                and_(
                    instance.stop_time.is_(None),
                    instance.network_id != 0,
                    instance.service_id != 0,
                    instance.node_id >= 3100,
                ),
            )
        )
        .subquery("candidates")
    )
    # 2. Active interfaces and active experiments of a candidate
    interfaces = (
        select(func.count())
        .select_from(NneNodeInfo)
        .where(
            NneNodeInfo.node_id == candidates.c.node_id,
            NneNodeInfo.valid_to.is_(None),
            NneNodeInfo.service_id != 7,
        )
        .scalar_subquery()
    )
    counted = aliased(NneMeasurementInstance)
    experiments = (
        select(func.count())
        .select_from(counted)
        .where(counted.node_id == candidates.c.node_id, counted.stop_time.is_(None))
        .scalar_subquery()
    )
    # 3. Status of the node (optional)
    return (
        select(
            candidates.c.node_id,
            NneStatus.value.label("status"),
            interfaces.label("interfaces"),
            (experiments + 1).label("experiments"),
        )
        .join(
            NneNodeStatusTable,
            NneNodeStatusTable.node_id == candidates.c.node_id,
            isouter=True,
        )
        .join(NneStatus, NneStatus.id == NneNodeStatusTable.status_id, isouter=True)
    )


def reported(
    candidates: pd.DataFrame, site: pd.DataFrame, experiments: pd.DataFrame
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Reported nodes with their site and their experiments, built from the frames read from the
    databases (no database access).

    Args:
        candidates (pd.DataFrame): Rows of select_reported_node_candidates.
        site (pd.DataFrame): Current site addresses of the candidates and of SATELLITE_SITE_NODE
            (node_id, municipality, loc_lat, loc_lon; coordinates as text).
        experiments (pd.DataFrame): measurement_instance rows of the candidates.

    Returns:
        Tuple[pd.DataFrame, pd.DataFrame]: nodes (node_id, status, interfaces, experiments,
        municipality, loc_lat, loc_lon) and the experiments of these nodes.
    """
    # 1. Reported nodes: status DEPLOYED or TESTING with an active interface, or a satellite node
    nodes = candidates.copy()
    satellite = nodes.node_id.isin(SATELLITE_NODES)
    nodes.loc[satellite, "status"] = "DEPLOYED"
    # Satellite nodes run no metadata container
    nodes.loc[satellite, "experiments"] -= 1
    nodes = nodes[
        satellite | (nodes.status.isin(STATUS_ORDER) & (nodes.interfaces > 0))
    ]
    # 2. Municipality and location of the current site address (optional); coordinates rounded to
    #    2 decimals (about 1 km), the map does not pinpoint the sites
    site = site[["node_id", "municipality", "loc_lat", "loc_lon"]]
    site[["loc_lat", "loc_lon"]] = (
        site[["loc_lat", "loc_lon"]].apply(pd.to_numeric, errors="coerce").round(2)
    )
    simulamet = site[site.node_id == SATELLITE_SITE_NODE]
    # Satellite nodes have no address: shown next to the site of node 7056 (SimulaMet),
    # 0.01° longitude (about 0.5 km) apart so that each dot can be clicked. One site per node: the
    # first row, so a satellite node with an address of its own keeps it
    site = pd.concat(
        [site]
        + [
            simulamet.assign(node_id=n, loc_lon=simulamet.loc_lon + 0.01 * (i + 1))
            for i, n in enumerate(SATELLITE_NODES)
        ]
    ).drop_duplicates("node_id")
    nodes = nodes.merge(site, on="node_id", how="left")
    # 3. Experiments of the reported nodes
    experiments = experiments[experiments.node_id.isin(nodes.node_id)]
    return nodes.reset_index(drop=True), experiments.reset_index(drop=True)


def load_database(env_file: str) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Frames of the reported nodes from the databases: reads the candidate nodes with their site
    addresses and experiments and the container runs; reported builds the frames of the pages.

    Args:
        env_file (str): nnedbtools env file of the nne-reader account; loaded once per process.

    Returns:
        Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]: nodes (node_id, status, interfaces,
        experiments, municipality, loc_lat, loc_lon), experiments (measurement_instance rows of
        the nodes, active and stopped), raw (report.container_rawdata).
    """
    # 1. Credentials and engines, once per process
    if engines.nne_engine is None:
        identityprovider.load_from_enviroment(env_file)
    # 2. Candidate nodes, the site addresses of them and of SATELLITE_SITE_NODE, their experiments
    #    and the container runs
    candidates = pd.read_sql(select_reported_node_candidates(), engines.nne_engine)
    node_ids = candidates.node_id.tolist()
    site = pd.read_sql(
        select_from_nne_node_adreess_and_nne_addresss(
            node_ids + [SATELLITE_SITE_NODE]
        ).where(
            NneNodeAddress.address_type == NneAddressType.site,
            NneNodeAddress.valid_to.is_(None),
        ),
        engines.nne_engine,
    )
    experiments = pd.read_sql(
        select_from_nne_measurement_instance(node_ids), engines.nne_engine
    )
    raw = pd.read_sql(select(ReportContainerRawdata), engines.report_engine)
    # 3. Reported nodes with their site and experiments
    nodes, experiments = reported(candidates, site, experiments)
    return nodes, experiments, raw
