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
# Dash application: pages, page frame, development server
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
Dash application of the NNE container status webpage: pages from the folder pages/, assets from
the folder assets/ (both next to this module), the nne-viz page frame and the development server.

Integrations:
    1. Dash Pages - one module per page in pages/.
    2. settings - DEBUG for the development server.

Sample code:
```bash
DEBUG=true container-status-webpage              # development server, http://localhost:8050
gunicorn container_status_webpage.app:server     # production server (Dockerfile)
```
"""

from dash import Dash
from flask import Flask

from container_status_webpage import settings
from container_status_webpage.controller import frame

# Dash app with the pages of pages/ and the assets of assets/
app: Dash = Dash(
    __name__, use_pages=True, title="NorNet edge – container status", update_title=None
)

# WSGI server for gunicorn
server: Flask = app.server

# Page frame, built on every page load
app.layout = frame.page


def main() -> None:
    """
    Runs the development server (console script container-status-webpage).
    """
    app.run(debug=settings.DEBUG)
