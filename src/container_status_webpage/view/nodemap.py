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
# Map of the Overview page: reported nodes coloured by their grade
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
Map of the reported nodes: one dot per node with a location, coloured by its grade (status.grade,
the worst colour class of its containers), on OpenStreetMap tiles; zoomable. The click on a dot is
handled by controller/overview.py.

Integrations:
    1. model.status - grades and issues of the nodes.
    2. view.palette - colours of the classes.

Sample code:
```python
from container_status_webpage.view.nodemap import node_map

figure = node_map(snapshot, ["Deployed", "Testing"])
```
"""

from typing import Dict, List

import pandas as pd
import plotly.graph_objects as go

from container_status_webpage.model import status
from container_status_webpage.model.snapshot import Snapshot
from container_status_webpage.view import palette
from container_status_webpage.view.formatting import blank

# Initial view: the whole of Norway
CENTRE: Dict[str, float] = {"lat": 65.0, "lon": 14.0}
ZOOM: float = 3.6


def details(snapshot: Snapshot, node_id: int) -> List[str]:
    """
    Lines about a node for the hover: status and municipality, grade, issues.

    Args:
        snapshot (Snapshot): Loaded data.
        node_id (int): Node identifier.

    Returns:
        List[str]: The lines.
    """
    node = snapshot.nodes.set_index("node_id").loc[node_id]
    return [
        " · ".join(filter(None, [node.status.capitalize(), blank(node.municipality)])),
        f"Grade: {status.grade(snapshot.summary, node_id).capitalize()}",
        *status.issues(snapshot.summary, node_id),
    ]


def located(snapshot: Snapshot, statuses: List[str]) -> pd.DataFrame:
    """
    Nodes with a location and a checked status, with their grade and hover text.

    Args:
        snapshot (Snapshot): Loaded data.
        statuses (List[str]): Checked statuses ("Deployed", "Testing").

    Returns:
        pd.DataFrame: node_id, loc_lat, loc_lon, grade, text.
    """
    nodes = snapshot.nodes
    nodes = nodes[
        nodes.status.str.capitalize().isin(statuses)
        & nodes.loc_lat.notna()
        & nodes.loc_lon.notna()
    ]
    return nodes[["node_id", "loc_lat", "loc_lon"]].assign(
        grade=[status.grade(snapshot.summary, n) for n in nodes.node_id],
        text=[
            "<br>".join([f"<b>Node {n}</b>", *details(snapshot, n)])
            for n in nodes.node_id
        ],
    )


def node_map(snapshot: Snapshot, statuses: List[str]) -> go.Figure:
    """
    Map of the nodes: one trace per grade from best to worst, so the worst dots lie on top and the
    legend counts and hides the grades; the zoom stays when the filter changes (uirevision).

    Args:
        snapshot (Snapshot): Loaded data.
        statuses (List[str]): Checked statuses ("Deployed", "Testing").

    Returns:
        go.Figure: The map; customdata of a dot is its node id.
    """
    frame = located(snapshot, statuses)
    figure = go.Figure(
        [
            go.Scattermap(
                lat=rows.loc_lat,
                lon=rows.loc_lon,
                mode="markers",
                marker={"size": 12, "color": palette.COLOUR[grade][0]},
                name=f"{grade.capitalize()} ({len(rows)})",
                text=rows.text,
                # A plain list: dcc.Graph reads the clicked point from the raw trace data, a numpy
                # column would reach the browser base64-encoded and the click without customdata
                customdata=rows.node_id.tolist(),
                hovertemplate="%{text}<extra></extra>",
            )
            for grade, rows in (
                (g, frame[frame.grade == g]) for g in ("none",) + status.GRADE_ORDER
            )
            if len(rows)
        ]
    )
    figure.update_layout(
        map={"style": "open-street-map", "center": CENTRE, "zoom": ZOOM},
        margin={"l": 0, "r": 0, "t": 0, "b": 0},
        uirevision="node-map",
        legend={
            "title": {"text": "Grade"},
            "x": 0.01,
            "y": 0.99,
            "bgcolor": "rgba(255,255,255,0.85)",
        },
        hoverlabel={"bgcolor": "white"},
    )
    return figure
