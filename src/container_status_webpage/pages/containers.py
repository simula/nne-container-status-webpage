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
# Registration of the pages Overview, Grid, Problems, Node
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
Pages of the container status of the reported nodes, registered with dash.register_page: Overview,
Grid, Problems and Node (documentation/DESIGN.md section 7). Each page is built by the page function
of its controller.

Integrations:
    1. controller.overview, controller.grid, controller.problems, controller.node - page functions.

Sample code:
    Served on /, /grid, /problems and /node by the app (container_status_webpage.app).
"""

import dash

from container_status_webpage.controller import grid, node, overview, problems

# The four views as pages, one header button each (view/frame.py)
dash.register_page(
    "overview",
    path="/",
    name="Overview",
    title="NorNet edge – Overview",
    order=0,
    layout=overview.page,
)


dash.register_page(
    "grid",
    path="/grid",
    name="Grid",
    title="NorNet edge – Grid",
    order=1,
    layout=grid.page,
)


dash.register_page(
    "problems",
    path="/problems",
    name="Problems",
    title="NorNet edge – Problems",
    order=2,
    layout=problems.page,
)


dash.register_page(
    "node",
    path="/node",
    name="Node",
    title="NorNet edge – Node",
    order=3,
    layout=node.page,
)
