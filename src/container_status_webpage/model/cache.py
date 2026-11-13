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
process until the next refresh point, a minute of the hour after the importer has written: every
page load in between uses the same snapshot. All pages use CONTAINERS_CACHE
(settings.CONTAINERS_CACHE_MINUTES). A load that fails is logged and the previous snapshot stays.

Integrations:
    1. settings - DATA_SOURCE, CONTAINERS_CACHE_MINUTES.
    2. model.snapshot - frames of the selected source with their summary.

Sample code:
```python
from container_status_webpage.model.cache import CONTAINERS_CACHE

snapshot = CONTAINERS_CACHE.get()
snapshot.summary.cells
```
"""

import logging
import threading
from typing import Callable, List, Optional

import pandas as pd

from container_status_webpage import settings
from container_status_webpage.model.snapshot import Snapshot, load

# Logger of the failed loads
LOGGER: logging.Logger = logging.getLogger(__name__)


def utc_now() -> pd.Timestamp:
    """
    Current time as the database stores it.

    Returns:
        pd.Timestamp: UTC, naive, whole seconds.
    """
    return pd.Timestamp.now("UTC").tz_localize(None).floor("s")


def last_refresh(now: pd.Timestamp, minutes: List[int]) -> pd.Timestamp:
    """
    Latest refresh point not later than a time.

    Args:
        now (pd.Timestamp): Time (UTC, naive).
        minutes (List[int]): Minutes of the hour of the refresh points.

    Returns:
        pd.Timestamp: Full hour plus one of the minutes, at or before now.
    """
    points = [now.floor("h") + pd.Timedelta(minutes=minute) for minute in minutes]
    return max(
        point if point <= now else point - pd.Timedelta(hours=1) for point in points
    )


class Cache:
    """Snapshot of the loaded data, loaded again after each refresh point."""

    def __init__(
        self, minutes: List[int], loader: Callable[[pd.Timestamp], Snapshot]
    ) -> None:
        """
        Args:
            minutes (List[int]): Minutes of the hour of the refresh points.
            loader (Callable[[pd.Timestamp], Snapshot]): Loads a snapshot at a given time.
        """
        self._minutes: List[int] = minutes
        self._loader: Callable[[pd.Timestamp], Snapshot] = loader
        self._snapshot: Optional[Snapshot] = None
        # Callbacks of the development server run in threads: one load at a time
        self._lock: threading.Lock = threading.Lock()

    def get(self, now: Optional[pd.Timestamp] = None) -> Snapshot:
        """
        Current snapshot; loaded on the first call and when a refresh point has passed since the
        last load. A load that fails is logged and the previous snapshot stays (the pages show its
        load time).

        Args:
            now (Optional[pd.Timestamp]): Time of the request (UTC, naive). Defaults to utc_now().

        Returns:
            Snapshot: Frames, summary and load time.

        Raises:
            Exception: The load failed and there is no previous snapshot.
        """
        now = utc_now() if now is None else now
        with self._lock:
            if self._snapshot is None or self._snapshot.loaded_at < last_refresh(
                now, self._minutes
            ):
                try:
                    self._snapshot = self._loader(now)
                # ponytail: every request retries the load while it fails; add a retry delay if
                # an outage makes the pages slow
                except Exception:  # pylint: disable=broad-exception-caught
                    LOGGER.exception("Data load failed")
                    if self._snapshot is None:
                        raise
            return self._snapshot


# Cache of the pages: loaded again after each run of the importer
CONTAINERS_CACHE: Cache = Cache(
    settings.CONTAINERS_CACHE_MINUTES, lambda now: load(settings.DATA_SOURCE, now)
)
