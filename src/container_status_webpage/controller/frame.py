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
# Controller of the page frame: page frame, navigation highlight, clock
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
Controller of the page frame: builds the frame on every page load, marks the navigation button of
the shown page and runs the clock in the browser.

Integrations:
    1. view.frame - layout of the page frame.
    2. dash.page_registry - navigation buttons in page order.

Sample code:
```python
from container_status_webpage.controller import frame

app.layout = frame.page
```
"""

from typing import List

import dash
from dash import ALL, Input, Output, html

from container_status_webpage.view import frame


def page() -> html.Div:
    """
    Page frame, built on every page load.

    Returns:
        html.Div: Header, view with the page and footer (view.frame.layout).
    """
    return frame.layout()


@dash.callback(
    Output({"type": "navigation", "index": ALL}, "className"), Input("url", "pathname")
)
def select_navigation(pathname: str) -> List[str]:
    """
    Marks the navigation button of the shown page as selected.

    Args:
        pathname (str): Path of the shown page.

    Returns:
        List[str]: CSS classes of the navigation buttons, in page order.
    """
    return [
        (
            "header-button selected"
            if page["relative_path"] == pathname
            else "header-button"
        )
        for page in dash.page_registry.values()
    ]


# Clock in the browser as nne-viz Clock.tsx: no request to the server every second
dash.clientside_callback(
    """(tick) => {
        const now = new Date(), zone = {timeZone: "UTC"};
        const date = now.toLocaleDateString("en-GB", zone);
        const time = now.toLocaleTimeString("en-GB", {...zone, hour12: false});
        return [date, time];
    }""",
    Output("clock-date", "children"),
    Output("clock-time", "children"),
    Input("clock-tick", "n_intervals"),
)
