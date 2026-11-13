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
# Development tool: page layouts and callbacks as JSON, compared before and after a refactoring
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
Development tool: the page frame, every page layout and the registered callbacks of the app, built
on the synthetic data at a fixed time, as one JSON file. A refactoring changes no behaviour when the
file is the same before and after it (documentation/DESIGN.md section 14).

Integrations:
    1. container_status_webpage.app - Dash Pages registry, /_dash-dependencies; view.frame - page
       frame.
    2. model.cache - utc_now fixed, so every run loads the same synthetic snapshot.

Sample code:
```bash
git switch main && python tools/layout_snapshot.py /tmp/before.json
git switch feat/<step> && python tools/layout_snapshot.py /tmp/after.json
cmp /tmp/before.json /tmp/after.json      # no output: identical
```
"""

import json
import sys
from typing import Any, Dict, List
from unittest import mock

import dash
import pandas as pd
from plotly.io.json import to_json_plotly

from container_status_webpage import settings
from container_status_webpage.app import server
from container_status_webpage.model import cache
from container_status_webpage.view.frame import layout as frame_layout

# Load time of the synthetic data (UTC, naive)
NOW: pd.Timestamp = pd.Timestamp("2026-11-06 12:00")


def snapshot_layouts(path: str) -> None:
    """
    Writes the page frame, the page layouts and the sorted callback dependencies as JSON.

    Args:
        path (str): Output file.
    """
    # 1. Synthetic data only: the database changes between runs
    if settings.DATA_SOURCE != "synthetic":
        sys.exit("DATA_SOURCE must be unset or synthetic")
    with mock.patch.object(cache, "utc_now", return_value=NOW):
        # 2. Page frame, the four pages, an unknown node and every node with a container
        pages: Dict[str, Any] = {
            page["path"]: page["layout"] for page in dash.page_registry.values()
        }
        built: Dict[str, Any] = {"frame": frame_layout()}
        built.update({page_path: layout() for page_path, layout in pages.items()})
        built["/node?node=1"] = pages["/node"](node="1")
        for node_id in cache.CONTAINERS_CACHE.get().nodes["node_id"]:
            built[f"/node?node={node_id}&container=udpping"] = pages["/node"](
                node=str(node_id), container="udpping"
            )
    # 3. Callbacks in a stable order
    dependencies: List[Any] = server.test_client().get("/_dash-dependencies").get_json()
    dependencies.sort(key=lambda dependency: json.dumps(dependency, sort_keys=True))
    # 4. One JSON file, indented so a diff shows where a layout changed
    layouts: Dict[str, Any] = {
        key: json.loads(to_json_plotly(value)) for key, value in built.items()
    }
    with open(path, "w", encoding="utf-8") as file:
        json.dump(
            {"layouts": layouts, "dependencies": dependencies},
            file,
            indent=1,
            sort_keys=True,
        )


if __name__ == "__main__":
    snapshot_layouts(sys.argv[1])
