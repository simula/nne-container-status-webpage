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
# Page data: what each page shows, prepared from a snapshot
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
What each page shows, prepared from a snapshot: the controllers build the page data with these
functions and hand it to the views (view/layouts.py), which only build the Dash and Plotly objects
from it (documentation/DESIGN.md section 9).

Integrations:
    1. model.snapshot.Snapshot - frames and summary.
    2. model.status - rules of the cells, grades, problems and counts; model.timeline - rows,
       segments and ranges of the timeline.

Sample code:
```python
import pandas as pd
from container_status_webpage.model import pages
from container_status_webpage.model.snapshot import load

snapshot = load("synthetic", pd.Timestamp("2026-11-06 12:00"))
pages.node(snapshot, 90001, None).threads
```
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from container_status_webpage.model import status, timeline
from container_status_webpage.model.snapshot import Snapshot

# Columns of the map rows (map_nodes), also when there are none
MAP_COLUMNS: Tuple[str, ...] = (
    "node_id",
    "loc_lat",
    "loc_lon",
    "status",
    "municipality",
    "grade",
    "issues",
)


@dataclass(frozen=True)
class OverviewData:
    """Overview: data line, map and count tables."""

    # Number of reported nodes and load time (UTC, naive) of the data line
    node_count: int
    loaded_at: pd.Timestamp
    # Map rows: every node with a location (map_nodes); the number of nodes without location
    map_nodes: pd.DataFrame
    without_location: int
    # Node counts per status group (status.overview), running containers (status.container_counts)
    counts: pd.DataFrame
    running: pd.DataFrame


@dataclass(frozen=True)
class GridData:
    """Grid: data line and colour grid."""

    # Number of reported nodes and load time (UTC, naive) of the data line
    node_count: int
    loaded_at: pd.Timestamp
    # Nodes in the order of the grid (status.ordered)
    nodes: pd.DataFrame
    # Cell per (node_id, container); thread states for the tooltips
    cells: Dict[Tuple[int, str], status.Cell]
    states: Dict[Tuple[int, str, str], status.ThreadState]


@dataclass(frozen=True)
class ProblemsData:
    """Problems: data line and problem list."""

    # Number of reported nodes and load time (UTC, naive) of the data line
    node_count: int
    loaded_at: pd.Timestamp
    # Nodes that are not fully OK (status.problems)
    problems: pd.DataFrame


@dataclass(frozen=True)
class NodeData:  # pylint: disable=too-many-instance-attributes
    """Node: node selector and, for a selected node, header, timeline, threads and experiments;
    the fields after container are None without a selected node."""

    # Number of reported nodes and load time (UTC, naive) of the data line
    node_count: int
    loaded_at: pd.Timestamp
    # Node ids of the selector in the order of the grid
    options: List[int]
    # Selected node and the container highlighted in the timeline, None for none
    node_id: Optional[int]
    container: Optional[str]
    # Row of the node in the nodes frame
    node: Optional[pd.Series] = None
    # Networks of its active experiments, one per display name, sorted by name
    networks: Optional[pd.DataFrame] = None
    # Timeline rows (container, thread, kind) and segments (model.timeline)
    rows: Optional[List[Tuple[str, str, str]]] = None
    segments: Optional[pd.DataFrame] = None
    # First start and load time of the timeline; the x range shown first (DEFAULT_RANGE)
    first: Optional[pd.Timestamp] = None
    now: Optional[pd.Timestamp] = None
    shown: Optional[List[pd.Timestamp]] = None
    # Threads in the order of the timeline with their state, None when never seen
    threads: Optional[List[Tuple[str, str, str, Optional[status.ThreadState]]]] = None
    # Measurement instances of the node with their network names, active first
    experiments: Optional[pd.DataFrame] = None


def map_nodes(snapshot: Snapshot) -> pd.DataFrame:
    """
    Reported nodes with a location, with what their map dot shows; the page keeps them as its map
    rows for the status filter (checked_map_nodes).

    Args:
        snapshot (Snapshot): Loaded data.

    Returns:
        pd.DataFrame: Columns of MAP_COLUMNS; issues as a list.
    """
    nodes = snapshot.nodes
    nodes = nodes[nodes.loc_lat.notna() & nodes.loc_lon.notna()]
    return nodes[["node_id", "loc_lat", "loc_lon", "status", "municipality"]].assign(
        grade=[status.grade(snapshot.summary, n) for n in nodes.node_id],
        issues=[status.issues(snapshot.summary, n) for n in nodes.node_id],
    )


def checked_map_nodes(rows: List[Dict[str, Any]], statuses: List[str]) -> pd.DataFrame:
    """
    Map rows of the open page (map_nodes as records) with a checked status: the map filter draws
    the data of the page, also after the cache has loaded newer data.

    Args:
        rows (List[Dict[str, Any]]): Map rows of the page.
        statuses (List[str]): Checked statuses ("Deployed", "Testing").

    Returns:
        pd.DataFrame: Columns of MAP_COLUMNS.
    """
    nodes = pd.DataFrame(rows, columns=list(MAP_COLUMNS))
    return nodes[nodes.status.str.capitalize().isin(statuses)]


def overview(snapshot: Snapshot) -> OverviewData:
    """
    Overview page data; the map shows every status at first.

    Args:
        snapshot (Snapshot): Loaded data.

    Returns:
        OverviewData: The page data.
    """
    nodes = snapshot.nodes
    return OverviewData(
        node_count=len(nodes),
        loaded_at=snapshot.loaded_at,
        map_nodes=map_nodes(snapshot),
        without_location=int((nodes.loc_lat.isna() | nodes.loc_lon.isna()).sum()),
        counts=status.overview(nodes, snapshot.summary),
        running=status.container_counts(nodes, snapshot.summary),
    )


def grid(snapshot: Snapshot) -> GridData:
    """
    Grid page data.

    Args:
        snapshot (Snapshot): Loaded data.

    Returns:
        GridData: The page data.
    """
    return GridData(
        node_count=len(snapshot.nodes),
        loaded_at=snapshot.loaded_at,
        nodes=status.ordered(snapshot.nodes),
        cells=snapshot.summary.cells,
        states=snapshot.summary.states,
    )


def problems(snapshot: Snapshot) -> ProblemsData:
    """
    Problems page data.

    Args:
        snapshot (Snapshot): Loaded data.

    Returns:
        ProblemsData: The page data.
    """
    return ProblemsData(
        node_count=len(snapshot.nodes),
        loaded_at=snapshot.loaded_at,
        problems=status.problems(snapshot.nodes, snapshot.summary, snapshot.raw),
    )


def node(
    snapshot: Snapshot, node_id: Optional[int], container: Optional[str]
) -> NodeData:
    """
    Node page data.

    Args:
        snapshot (Snapshot): Loaded data.
        node_id (Optional[int]): Selected reported node, None for none.
        container (Optional[str]): Container highlighted in the timeline, None for none.

    Returns:
        NodeData: The page data; only the selector without a selected node.
    """
    # 1. Selector; nothing more without a selected node
    common = {
        "node_count": len(snapshot.nodes),
        "loaded_at": snapshot.loaded_at,
        "options": status.ordered(snapshot.nodes).node_id.tolist(),
        "node_id": node_id,
        "container": container,
    }
    if node_id is None:
        return NodeData(**common)
    # 2. Header: the networks of the active experiments, one chip per display name
    experiments = snapshot.experiments
    active = status.networks(
        experiments[(experiments.node_id == node_id) & experiments.stop_time.isna()]
    )
    shown = active[active.network_id != 0].drop_duplicates("display_name")
    # 3. Timeline and threads
    rows = timeline.thread_rows(snapshot, node_id)
    first, now = timeline.span(snapshot, node_id)
    states = snapshot.summary.states
    # 4. Experiments, active first
    frame = status.networks(experiments[experiments.node_id == node_id])
    frame = frame.assign(active=frame.stop_time.isna()).sort_values(
        ["active", "id"], ascending=[False, True]
    )
    return NodeData(
        **common,
        node=snapshot.nodes.set_index("node_id").loc[node_id],
        networks=shown.sort_values("display_name"),
        rows=rows,
        segments=timeline.segments(snapshot, node_id),
        first=first,
        now=now,
        shown=timeline.x_range(first, now, timeline.DEFAULT_RANGE),
        threads=[(c, t, kind, states.get((node_id, c, t))) for c, t, kind in rows],
        experiments=frame,
    )
