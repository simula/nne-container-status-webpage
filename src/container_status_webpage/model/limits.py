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
# Limits of the classes and warnings
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
Limits of the classes and warnings (documentation/DESIGN.md sections 5 and 6): the numbers a
calibration after real use changes. The rules (model/status.py, model/timeline.py) and the texts of
the legend and the timeline (view/) read them from here.

Sample code:
```python
from container_status_webpage.model import limits

limits.SEEN   # ((2, "running"), (6, "late"), ...)
```
"""

import math
from typing import Tuple

import pandas as pd

# Last seen classes: hours since the last heartbeat, upper limit inclusive (heartbeats arrive
# hourly)
SEEN: Tuple[Tuple[float, str], ...] = (
    (2, "running"),
    (6, "late"),
    (24, "stale"),
    (168, "down"),
    (math.inf, "long down"),
)

# Uptime classes of running threads: hours, upper limit exclusive
UPTIME: Tuple[Tuple[float, str], ...] = (
    (1, "fresh"),
    (24, "young"),
    (168, "stable"),
    (math.inf, "long-run"),
)

# Starts within 24 h from which a thread is flapping
FLAPPING: int = 3

# Receiver restarts per hour of the run (extra of a receiver-<N> row, reset when the container
# restarts) above which a receiver gets a warning
RESTARTS_PER_HOUR: float = 60

# A gap longer than this between the last heartbeat of a run and the next start: the thread was down
DOWN_AFTER: pd.Timedelta = pd.Timedelta(hours=1)

# First real deployment: earlier start_ts values are node clock errors (2011) and do not stretch
# the timeline
FIRST_DEPLOYMENT: pd.Timestamp = pd.Timestamp("2026-01-01")
