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
# Checks of the data cache
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
Checks of the data cache (data/cache.py): one load per time-to-live, the synthetic snapshot.

Sample code:
```bash
pytest tests/test_cache.py
```
"""

from types import SimpleNamespace

import pandas as pd

from container_status_webpage.data.cache import Cache, load

NOW = pd.Timestamp("2026-11-06 12:00")


def test_one_load_per_time_to_live():
    """The snapshot is kept for 300 s and loaded again at 300 s."""
    loads = []

    def loader(now):
        loads.append(now)
        return SimpleNamespace(loaded_at=now)

    cache = Cache(300, loader)
    first = cache.get(NOW)
    assert cache.get(NOW + pd.Timedelta(seconds=299)) is first
    assert cache.get(NOW + pd.Timedelta(seconds=300)) is not first
    assert loads == [NOW, NOW + pd.Timedelta(seconds=300)]


def test_synthetic_snapshot():
    """The synthetic source gives 36 nodes summarised at the load time."""
    snapshot = load("synthetic", NOW)
    assert len(snapshot.nodes) == 36
    assert snapshot.loaded_at == snapshot.summary.now == NOW
