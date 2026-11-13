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
# Snapshot of the loaded data: input frames with their summary
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
Loaded data of a source (settings.DATA_SOURCE): the three input frames with their summary at the
load time. The cache (model/cache.py) keeps one snapshot per process; the views and the timeline
take a snapshot as their data.

Integrations:
    1. model.synthetic - synthetic frames; model.loader - frames of the databases (imported only
       for the source database, settings.DB_ENV_FILE).
    2. model.status - thread states and cells of the frames.

Sample code:
```python
import pandas as pd
from container_status_webpage.model.snapshot import load

snapshot = load("synthetic", pd.Timestamp("2026-11-06 12:00"))
snapshot.summary.cells
```
"""

from dataclasses import dataclass

import pandas as pd

from container_status_webpage import settings
from container_status_webpage.model import status
from container_status_webpage.model.synthetic import synthetic


@dataclass(frozen=True)
class Snapshot:
    """Input frames with their summary at the load time."""

    # Nodes frame
    nodes: pd.DataFrame
    # Experiments frame
    experiments: pd.DataFrame
    # report.container_rawdata rows
    raw: pd.DataFrame
    # Thread states and cells
    summary: status.Summary
    # Load time (UTC, naive)
    loaded_at: pd.Timestamp


def load(source: str, now: pd.Timestamp) -> Snapshot:
    """
    Frames of a source with their summary.

    Args:
        source (str): Data source of settings.DATA_SOURCE.
        now (pd.Timestamp): Load time (UTC, naive).

    Returns:
        Snapshot: Frames, summary and load time.

    Raises:
        ValueError: Unknown source.
    """
    # 1. Frames of the source; the loader only for the database, so synthetic data need no
    #    credentials
    if source == "synthetic":
        nodes, experiments, raw = synthetic(now)
    elif source == "database":
        # pylint: disable-next=import-outside-toplevel
        from container_status_webpage.model.loader import load_database

        nodes, experiments, raw = load_database(settings.DB_ENV_FILE, now)
    else:
        raise ValueError(f"Data source {source} is not available")
    # 2. Summary at the load time
    return Snapshot(
        nodes, experiments, raw, status.summarise(nodes, experiments, raw, now), now
    )
