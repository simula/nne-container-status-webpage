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
# Layer rules of the model, view and controller, no SQL as text
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
Checks of the layer rules (documentation/DESIGN.md section 9) and of "no SQL as text" (section 13),
read from the syntax tree of every module of the package without importing it.

Sample code:
```bash
pytest tests/test_layers.py
```
"""

import ast
import importlib.util
import re
from pathlib import Path
from typing import List, Set, Tuple

import pytest

# Source folder of the package
PACKAGE: Path = Path(__file__).resolve().parents[1] / "src" / "container_status_webpage"
# The model imports neither the web libraries nor the view or the controller
MODEL_FORBIDDEN: Tuple[str, ...] = (
    "dash",
    "dash_ag_grid",
    "flask",
    "plotly",
    "container_status_webpage.controller",
    "container_status_webpage.view",
)
# A view never loads data, never takes the snapshot (it builds from model.pages) and never calls
# the controller
VIEW_FORBIDDEN: Tuple[str, ...] = (
    "container_status_webpage.controller",
    "container_status_webpage.model.snapshot",
    "container_status_webpage.model.loader",
    "container_status_webpage.model.synthetic",
)
# Only the controller reads the cache and has callbacks
CACHE: Tuple[str, ...] = ("container_status_webpage.model.cache",)
CALLBACKS: Set[str] = {"callback", "clientside_callback"}
# SQL written as a string
SQL_TEXT: re.Pattern = re.compile(r"\bSELECT\b.*\bFROM\b", re.DOTALL)


def within(imported: Set[str], prefixes: Tuple[str, ...]) -> List[str]:
    """
    Imported modules and names that lie in one of the given modules.

    Args:
        imported (Set[str]): Absolute module and module.name of every import.
        prefixes (Tuple[str, ...]): Forbidden modules.

    Returns:
        List[str]: The imports inside them, sorted.
    """
    return sorted(
        name
        for name in imported
        if any(name == prefix or name.startswith(prefix + ".") for prefix in prefixes)
    )


def violations(path: Path) -> List[str]:
    """
    Broken rules of one module.

    Args:
        path (Path): Module file below PACKAGE.

    Returns:
        List[str]: One line per broken rule; empty when the module keeps all.
    """
    # 1. Imports (relative ones made absolute), attribute names and strings of the module
    package: str = ".".join(path.relative_to(PACKAGE.parent).parts[:-1])
    imported: Set[str] = set()
    attributes: Set[str] = set()
    strings: List[str] = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            module = importlib.util.resolve_name(
                "." * node.level + (node.module or ""), package
            )
            imported.update(f"{module}.{alias.name}" for alias in node.names)
        elif isinstance(node, ast.Attribute):
            attributes.add(node.attr)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            strings.append(node.value)
    used: Set[str] = attributes | {name.rpartition(".")[2] for name in imported}
    # 2. Rules of the layer: the first folder below the package
    layer: str = path.relative_to(PACKAGE).parts[0]
    found: List[str] = []
    if layer == "model":
        found += [f"model imports {name}" for name in within(imported, MODEL_FORBIDDEN)]
    if layer == "view":
        found += [f"view imports {name}" for name in within(imported, VIEW_FORBIDDEN)]
    if layer != "controller":
        found += [
            f"cache read outside the controller: {name}"
            for name in within(imported, CACHE)
        ]
        found += [
            f"callback outside the controller: {name}"
            for name in sorted(used & CALLBACKS)
        ]
    # 3. Rules of every module
    found += [
        f"SQL as text: {name}"
        for name in sorted(imported)
        if name.startswith("sqlalchemy") and name.endswith(".text")
    ]
    found += [
        f"SQL as text: {text[:60]!r}" for text in strings if SQL_TEXT.search(text)
    ]
    return found


@pytest.mark.parametrize(
    "path",
    sorted(PACKAGE.rglob("*.py")),
    ids=lambda path: str(path.relative_to(PACKAGE)),
)
def test_layer_rules(path):
    """Every module keeps the layer rules of its folder and writes no SQL as text."""
    assert not violations(path)
