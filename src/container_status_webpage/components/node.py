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
# Node detail of the Containers page: header, timeline, threads, experiments
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
Node detail of the Containers page (documentation/DESIGN.md section 7): the header of the selected
node; the timeline, the threads and the experiments follow.

Integrations:
    1. data.cache.Snapshot - nodes and experiments frames.

Sample code:
```python
from container_status_webpage.components import node
from container_status_webpage.data.cache import CONTAINERS_CACHE

node.header(CONTAINERS_CACHE.get(), 90001)
```
"""

from typing import Any, Dict, Optional

from dash import html

from container_status_webpage.components import palette
from container_status_webpage.components.formatting import blank
from container_status_webpage.data import status
from container_status_webpage.data.cache import Snapshot


def node_query(node_id: Any, container: Optional[str] = None) -> str:
    """
    URL query of the node detail (pages/containers.py builds the page from it).

    Args:
        node_id (Any): Node id, None for none.
        container (Optional[str], optional): Container to highlight. Defaults to None.

    Returns:
        str: Query string, e.g. "?tab=node&node=90001&container=udpping".
    """
    query = "?tab=node" + ("" if node_id is None else f"&node={node_id}")
    return query + (f"&container={container}" if container else "")


def click_query(cell: Dict[str, Any]) -> str:
    """
    URL query of a clicked grid or problem list cell: its node, and its container for a container
    cell.

    Args:
        cell (Dict[str, Any]): cellClicked of the AG Grid (rowId is the node id).

    Returns:
        str: Query string.
    """
    column = cell["colId"]
    return node_query(cell["rowId"], column if column in status.NAME else None)


def chip(text: str, colour: str) -> html.Span:
    """
    Text on a coloured chip.

    Args:
        text (str): Text.
        colour (str): Background colour.

    Returns:
        html.Span: The chip.
    """
    return html.Span(text, className="chip", style={"backgroundColor": colour})


def header(snapshot: Snapshot, node_id: int) -> html.Div:
    """
    Header of a node: id, status, municipality and the providers of its active experiments.

    Args:
        snapshot (Snapshot): Loaded data.
        node_id (int): Node identifier of a reported node.

    Returns:
        html.Div: The header (id node-header).
    """
    node = snapshot.nodes.set_index("node_id").loc[node_id]
    experiments = snapshot.experiments
    active = experiments[
        (experiments.node_id == node_id) & experiments.stop_time.isna()
    ]
    municipality = blank(node.municipality)
    return html.Div(
        [
            html.Span(f"Node {node_id}", className="node-id"),
            chip(node.status.capitalize(), palette.STATUS_COLOUR[node.status]),
            *([html.Span(municipality)] if municipality else []),
            *[
                chip(provider, palette.PROVIDER.get(provider, palette.PROVIDER_DEFAULT))
                for provider in sorted(set(active.provider))
            ],
        ],
        id="node-header",
        className="node-header",
    )
