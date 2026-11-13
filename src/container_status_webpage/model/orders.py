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
# Orders of the statuses and classes
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
Orders of the statuses and classes (documentation/DESIGN.md sections 3, 5 and 6): the reported
node_status groups in display order, the last seen classes and the colour classes (grades) from
best to worst. The rules (model/status.py) and the views read them from here.

Sample code:
```python
from container_status_webpage.model import orders

orders.GRADE_ORDER   # ("long-run", "stable", "young", "fresh", "late", ...)
```
"""

from typing import Tuple

from container_status_webpage.model.limits import UPTIME

# Reported node_status groups in display order
STATUS_ORDER: Tuple[str, ...] = ("DEPLOYED", "TESTING")

# Last seen classes from best to worst
SEVERITY: Tuple[str, ...] = ("running", "late", "stale", "down", "long down", "never")

# Colour classes from best to worst, the grade of a node on the map: uptime shades of running
# cells, longest first, then the last seen classes
GRADE_ORDER: Tuple[str, ...] = (
    tuple(name for _, name in reversed(UPTIME)) + SEVERITY[1:]
)
