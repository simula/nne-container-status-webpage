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
# Page frame in the nne-viz look: header, navigation, clock, footer
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
Page frame in the nne-viz look (web/src/components/Base.tsx, header/Header.tsx, header/Clock.tsx,
Footer.tsx): header with the NorNet logo, one navigation button per registered page and the UTC
clock, the page view, the footer with the SimulaMet logo.

Integrations:
    1. dash.page_registry - navigation buttons in page order.
    2. assets/ - style.css, nornet.png, simulamet.svg.

Sample code:
```python
from dash import Dash

from container_status_webpage.components import frame

app = Dash(__name__, use_pages=True)
app.layout = frame.layout
```
"""

from typing import List

import dash
from dash import ALL, Input, Output, dcc, html

# Link of the NorNet logo
NNTB_URL: str = "https://www.nntb.no/"


def layout() -> html.Div:
    """
    Page frame around dash.page_container, built on every page load.

    Returns:
        html.Div: Header, view with the page and footer.
    """
    # 1. Navigation buttons, one per registered page
    navigation: List[dcc.Link] = [
        dcc.Link(
            page["name"],
            href=page["relative_path"],
            id={"type": "navigation", "index": page["relative_path"]},
            className="header-button",
        )
        for page in dash.page_registry.values()
    ]
    # 2. UTC date and time, updated in the browser every second
    clock: html.Div = html.Div(
        [
            html.Span("UTC:"),
            html.Span(id="clock-date"),
            html.Span(id="clock-time"),
        ],
        className="clock",
    )
    # 3. Header, view and footer
    return html.Div(
        className="base",
        children=[
            dcc.Location(id="url"),
            dcc.Interval(id="clock-tick", interval=1000),
            html.Header(
                className="header",
                children=[
                    html.Div(
                        className="header-start",
                        children=[
                            html.A(
                                html.Img(
                                    src=dash.get_asset_url("nornet.png"),
                                    alt="Nornet logo",
                                    className="logo",
                                ),
                                href=NNTB_URL,
                                target="_blank",
                            ),
                            html.H1("Container Status", className="header-text"),
                        ],
                    ),
                    html.Div(navigation + [clock], className="header-end"),
                ],
            ),
            html.Main(dash.page_container, className="view"),
            html.Footer(
                className="footer",
                children=[
                    html.Span("© Simula Research Laboratory"),
                    html.Div(
                        html.Img(
                            src=dash.get_asset_url("simulamet.svg"), alt="SimulaMet"
                        ),
                        className="footer-end",
                    ),
                ],
            ),
        ],
    )


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
