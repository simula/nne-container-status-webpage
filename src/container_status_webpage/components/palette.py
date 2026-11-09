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
# Colours and symbols of the container status rules
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
Colours and symbols of the container status rules (documentation/DESIGN.md section 6), the single
source for the grid and the timeline; the colours of the page frame stay in assets/style.css.
Aligned with nne-viz web/src/constants/colors.tsx (Status, UpRate); the network colours come from
the nnedbtools enum_mapper.

Sample code:
```python
from container_status_webpage.components import palette

palette.cell_style(cell, testing=False)
```
"""

from typing import Dict, List, Tuple

from container_status_webpage.data.status import Cell

# Background and text colour per class: uptime classes of running cells, then the last seen classes
COLOUR: Dict[str, Tuple[str, str]] = {
    "fresh": ("#bfddd3", "#000000"),
    "young": ("#80bca8", "#000000"),
    "stable": ("#409a7c", "#ffffff"),
    "long-run": ("#007850", "#ffffff"),
    "late": ("#efc94d", "#000000"),
    "stale": ("#e16437", "#ffffff"),
    "down": ("#e13737", "#ffffff"),
    "long down": ("#a50f15", "#ffffff"),
    "never": ("#dddddd", "#000000"),
    "none": ("#ffffff", "#000000"),
}

# Symbol per state, so that no state depends on colour alone
SYMBOL: Dict[str, str] = {
    "running": "✓",
    "late": "!",
    "stale": "!",
    "down": "×",
    "long down": "×",
    "never": "–",
    "none": "",
}

# Inner border of a partial cell (amber) and of a cell with orphan threads or an orphan container
# (dark red)
PARTIAL: str = "#d39e00"
ORPHAN: str = "#a50f15"

# Hatching of a configured container never seen
HATCH: str = (
    "repeating-linear-gradient(45deg, transparent 0 4px, rgba(0, 0, 0, 0.15) 4px 6px)"
)

# White dot with a black ring in the top right corner of a flapping cell
FLAP_DOT: str = (
    "radial-gradient(circle at calc(100% - 7px) 7px, "
    "#ffffff 0 3px, #000000 3px 4px, transparent 4px)"
)

# Amber dot with a black ring in the top left corner of a cell with a receiver restart warning
RESTART_DOT: str = (
    "radial-gradient(circle at 7px 7px, #d39e00 0 3px, #000000 3px 4px, transparent 4px)"
)

# Cell border of TESTING nodes and of containers that are not configured
TESTING_BORDER: str = "1px dashed #444444"
NONE_BORDER: str = "1px solid #e6e6e6"

# Status chips
STATUS_COLOUR: Dict[str, str] = {"DEPLOYED": "#1f3a93", "TESTING": "#7b3fb5"}


def colour_class(cell: Cell) -> str:
    """
    Colour class of a cell: the uptime shade when running, the state otherwise.

    Args:
        cell (Cell): The cell.

    Returns:
        str: Key of COLOUR.
    """
    return cell.shade if cell.state == "running" else cell.state


def cell_text(cell: Cell) -> str:
    """
    Text of a cell: symbol and label.

    Args:
        cell (Cell): The cell.

    Returns:
        str: E.g. "✓ S 2/2 R 2/2".
    """
    return " ".join(part for part in (SYMBOL[cell.state], cell.label) if part)


def cell_style(cell: Cell, testing: bool) -> Dict[str, str]:
    """
    Complete CSS style of a grid cell: colours, hatching, flapping dot, inner borders, TESTING
        border.

    Args:
        cell (Cell): The cell.
        testing (bool): The node is TESTING.

    Returns:
        Dict[str, str]: CSS properties in camel case (React style).
    """
    # 1. Colours of the class
    background, text = COLOUR[colour_class(cell)]
    style = {"backgroundColor": background, "color": text, "textAlign": "center"}
    # 2. Flapping dot and hatching
    images: List[str] = (
        ([FLAP_DOT] if cell.flapping else [])
        + ([RESTART_DOT] if cell.restart_warnings else [])
        + ([HATCH] if cell.state == "never" else [])
    )
    if images:
        style["backgroundImage"] = ", ".join(images)
    # 3. Inner borders: partial amber, orphans dark red (outside the amber one when both)
    shadows: List[str] = [f"inset 0 0 0 3px {PARTIAL}"] if cell.partial else []
    if cell.orphans or cell.orphan_container:
        shadows.append(f"inset 0 0 0 {6 if cell.partial else 3}px {ORPHAN}")
    if shadows:
        style["boxShadow"] = ", ".join(shadows)
    # 4. Cell border
    if testing:
        style["border"] = TESTING_BORDER
    elif cell.state == "none":
        style["border"] = NONE_BORDER
    return style
