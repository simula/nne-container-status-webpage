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
# Sub-tabs in the nne-viz TabButton style
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
Sub-tabs of a page in the nne-viz TabButton style (web/src/components/buttons/TabButton.tsx),
built on dcc.Tabs; the CSS is in assets/style.css (classes sub-tabs, tab-button,
tab-button--selected).

Sample code:
```python
from dash import html

from container_status_webpage.components.tabs import sub_tabs

sub_tabs("containers-tabs", [("overview", "Overview", html.P("Nodes per status"))])
```
"""

from typing import List, Optional, Tuple

from dash import dcc
from dash.development.base_component import Component


def sub_tabs(
    tabs_id: str, tabs: List[Tuple[str, str, Component]], value: Optional[str] = None
) -> dcc.Tabs:
    """
    Tabs in the nne-viz TabButton look.

    Args:
        tabs_id (str): Component id of the tabs.
        tabs (List[Tuple[str, str, Component]]): Value, label and content of each tab.
        value (Optional[str], optional): Selected tab. Defaults to None (the first tab).

    Returns:
        dcc.Tabs: Tabs component.
    """
    return dcc.Tabs(
        id=tabs_id,
        value=value or tabs[0][0],
        className="sub-tabs",
        children=[
            dcc.Tab(
                label=label,
                value=value,
                className="tab-button",
                selected_className="tab-button--selected",
                children=content,
            )
            for value, label, content in tabs
        ],
    )
