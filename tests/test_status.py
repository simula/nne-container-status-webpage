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
# Checks of the container status rules
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
Checks of the container status rules (data/status.py): class boundaries, flapping, worst thread /
partial / orphan,
coverage of the synthetic data, problem list and overview.

Sample code:
```bash
pytest tests/test_status.py
```
"""

import pandas as pd

from container_status_webpage.data import status
from container_status_webpage.data.synthetic import SCENARIOS, synthetic

NOW = pd.Timestamp("2026-11-06 12:00")


def raw(*rows) -> pd.DataFrame:
    """container_rawdata of node 1 from (container, process, start hours ago, last seen hours
    ago)."""
    return pd.DataFrame(
        [
            {
                "node_id": 1,
                "container": c,
                "process": p,
                "version": "v",
                "start_ts": NOW - pd.Timedelta(hours=s),
                "seen_ts": NOW - pd.Timedelta(hours=e),
                "uptime": (s - e) * 3600,
                "extra": None,
            }
            for c, p, s, e in rows
        ]
    )


def test_class_boundaries():
    """Last seen limits inclusive, uptime limits exclusive."""
    assert [
        status.seen_class(h) for h in (2, 2.01, 6, 6.01, 24, 24.01, 168, 168.01)
    ] == [
        "running",
        "late",
        "late",
        "stale",
        "stale",
        "down",
        "down",
        "long down",
    ]
    assert [status.uptime_class(h) for h in (0.99, 1, 23.99, 24, 167.99, 168)] == [
        "fresh",
        "young",
        "young",
        "stable",
        "stable",
        "long-run",
    ]


def test_flapping():
    """Three starts within 24 h flap, two do not."""
    three = status.thread_states(
        raw(*[("speedtest", "container", s, s - 0.1) for s in (20, 10, 1)]), NOW
    )
    two = status.thread_states(
        raw(*[("speedtest", "container", s, s - 0.1) for s in (30, 10, 1)]), NOW
    )
    assert status.cell(1, "speedtest", three, []).flapping
    assert not status.cell(1, "speedtest", two, []).flapping


def test_worst_thread_partial_and_orphans():
    """Worst seen thread sets the state; never seen threads make a cell partial; running threads of
    inactive
    experiments are orphans, stopped ones are history."""
    states = status.thread_states(
        raw(
            ("udpping", "container", 100, 0.5),
            ("udpping", "sender-10", 100, 0.5),
            ("udpping", "receiver-10", 100, 0.5),
            ("udpping", "receiver-12", 100, 0.5),
            ("udpping", "sender-14", 100, 0.5),
            ("udpping", "receiver-16", 100, 48),
            ("mqtt", "container", 100, 0.5),
            ("mqtt", "mqtt", 100, 48),
            ("speedtest", "container", 100, 48),
        ),
        NOW,
    )
    # active experiments 10, 12: sender-12 never seen, sender-14 orphan, receiver-16 down (not an
    # orphan)
    udpping = status.cell(1, "udpping", states, [10, 12])
    assert (udpping.state, udpping.partial, udpping.label) == (
        "running",
        True,
        "S 1/2 R 2/2 ⚠+1",
    )
    assert udpping.orphans == ["sender-14"]
    mqtt = status.cell(1, "mqtt", states, [])
    assert (mqtt.state, mqtt.partial) == ("down", True)
    speedtest = status.cell(1, "speedtest", states, [])
    assert (speedtest.state, speedtest.partial) == ("down", False)
    assert status.cell(1, "metadata", states, []).state == "never"
    assert status.cell(1, "traceroute", states, []).state == "none"


def test_synthetic_covers_every_class():
    """The synthetic data show every state, shade and marker for both status groups."""
    nodes, experiments, rawdata = synthetic(NOW)
    cells = list(status.summarise(nodes, experiments, rawdata, NOW).cells.values())
    assert set(status.SEVERITY) | {"none"} <= {c.state for c in cells}
    assert {name for _, name in status.UPTIME} <= {c.shade for c in cells}
    assert any(c.partial and c.state == "running" for c in cells)
    assert any(c.partial and c.state != "running" for c in cells)
    assert any(c.flapping for c in cells)
    assert any(c.orphans for c in cells)
    assert tuple(nodes.status.unique()) == status.STATUS_ORDER


def test_problems_and_overview():
    """Problems: every scenario with an issue, none of the healthy ones; DEPLOYED first, the silent
    ones first.
    Overview: the counts of each group add up."""
    nodes, experiments, rawdata = synthetic(NOW)
    summary = status.summarise(nodes, experiments, rawdata, NOW)
    found = status.problems(nodes, summary, rawdata)
    scenario = nodes.set_index("node_id").scenario
    healthy = {"all long-run", "fresh restart", "young", "stable", "version change"}
    assert set(found.node_id.map(scenario)) == set(SCENARIOS) - healthy
    assert found.status.tolist() == ["DEPLOYED"] * 13 + ["TESTING"] * 13
    assert found.node_id.map(scenario).iloc[0] == "no data"
    counts = status.overview(nodes, summary)
    assert (
        counts.all_main_ok + counts.some_issue + counts.nothing_running == counts.nodes
    ).all()
    assert counts.set_index("status").loc["all", "nodes"] == len(nodes)
