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
# Settings of the webpage from environment variables
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
Settings of the webpage, read once from environment variables.

Integrations:
    1. Environment variables (Docker compose, systemd unit or shell):
        * DEBUG       - Dash development mode: hot reload, error overlay (default False)
        * DB_ENV_FILE - nnedbtools env file of the nne-reader account (read access to nne and
                        report), used by the data loader from phase 4 (default .db_env)
        * DATA_SOURCE - synthetic (default) or database (data.loader, read-only)
        * CONTAINERS_CACHE_MINUTES - minutes of the hour after which the Containers tab loads its
                                     data again (default 15,45; the importer writes at 10 and 40)

Sample code:
```python
from container_status_webpage import settings

if settings.DEBUG:
    ...
```
"""

from typing import List

from environs import Env
from marshmallow.validate import OneOf

# Reader of the environment variables
_env: Env = Env()

# Dash development mode
DEBUG: bool = _env.bool("DEBUG", False)

# nnedbtools env file of the nne-reader account (read access to nne and report)
DB_ENV_FILE: str = _env.str("DB_ENV_FILE", ".db_env")

# Source of the data
DATA_SOURCE: str = _env.str(
    "DATA_SOURCE", "synthetic", validate=OneOf(["synthetic", "database"])
)

# Minutes of the hour after which the Containers tab loads its data again (the importer writes at
# minute 10 and 40 and gets 5 minutes to finish)
CONTAINERS_CACHE_MINUTES: List[int] = _env.list(
    "CONTAINERS_CACHE_MINUTES", [15, 45], subcast=int
)
