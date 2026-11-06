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
# Cache of the loaded data with its time-to-live
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
Loaded data of the selected source (settings.DATA_SOURCE) with their summary and load time, kept per
process for
settings.CACHE_TTL seconds: every page load within that time uses the same snapshot.

Integrations:
    1. settings - DATA_SOURCE, CACHE_TTL.
    2. data.synthetic - synthetic frames; the database loader follows in phase 4.

Sample code:
```python
from container_status_webpage.data.cache import CACHE

snapshot = CACHE.get()
snapshot.summary.cells
```
"""

import threading
from dataclasses import dataclass
from typing import Callable, Optional

import pandas as pd

from container_status_webpage import settings
from container_status_webpage.data import status
from container_status_webpage.data.synthetic import synthetic


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


def utc_now() -> pd.Timestamp:
    """
    Current time as the database stores it.

    Returns:
        pd.Timestamp: UTC, naive, whole seconds.
    """
    return pd.Timestamp.now("UTC").tz_localize(None).floor("s")


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
    # 1. Frames of the source
    if source != "synthetic":
        raise ValueError(f"Data source {source} is not available")
    nodes, experiments, raw = synthetic(now)
    # 2. Summary at the load time
    return Snapshot(
        nodes, experiments, raw, status.summarise(nodes, experiments, raw, now), now
    )


class Cache:
    """Snapshot of the loaded data, loaded again when older than its time-to-live."""

    def __init__(self, ttl_s: int, loader: Callable[[pd.Timestamp], Snapshot]) -> None:
        """
        Args:
            ttl_s (int): Time-to-live in seconds.
            loader (Callable[[pd.Timestamp], Snapshot]): Loads a snapshot at a given time.
        """
        self._ttl: pd.Timedelta = pd.Timedelta(seconds=ttl_s)
        self._loader: Callable[[pd.Timestamp], Snapshot] = loader
        self._snapshot: Optional[Snapshot] = None
        # Callbacks of the development server run in threads: one load at a time
        self._lock: threading.Lock = threading.Lock()

    def get(self, now: Optional[pd.Timestamp] = None) -> Snapshot:
        """
        Current snapshot; loaded on the first call and when the kept one is older than the
        time-to-live.

        Args:
            now (Optional[pd.Timestamp]): Time of the request (UTC, naive). Defaults to utc_now().

        Returns:
            Snapshot: Frames, summary and load time.
        """
        now = utc_now() if now is None else now
        with self._lock:
            if self._snapshot is None or now - self._snapshot.loaded_at >= self._ttl:
                self._snapshot = self._loader(now)
            return self._snapshot


# Cache of the process
CACHE: Cache = Cache(settings.CACHE_TTL, lambda now: load(settings.DATA_SOURCE, now))
