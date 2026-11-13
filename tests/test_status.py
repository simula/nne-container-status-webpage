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
Checks of the container status rules (model/status.py): class boundaries, flapping, receiver
restarts, worst thread / partial / orphan, satellite nodes, grade, coverage of the synthetic data,
problem list and overview.

Sample code:
```bash
pytest tests/test_status.py
```
"""

import pandas as pd

from container_status_webpage.model import status
from container_status_webpage.model.synthetic import SCENARIOS, synthetic

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


def test_receiver_restart_warning():
    """Receiver restarts: warning above 60 per hour, or above 1440 per day once the run lasted 7
    days (the same rate); the run counts as at least 1 h; no counter, no warning."""

    def warned(restarts, run_h):
        return status.restart_warning({"restarts": restarts, "run_h": run_h})

    assert not warned(float("nan"), 10)
    assert (warned(600, 10), warned(601, 10)) == (False, True)
    assert (warned(60, 0), warned(61, 0)) == (False, True)
    assert (warned(10080, 168), warned(10081, 168)) == (False, True)
    assert status.rate_text(480) == "480/h" and status.rate_text(8 / 24) == "8.0/d"


def test_worst_thread_partial_and_orphans():
    """Worst seen thread sets the state; never seen threads make a cell partial; running threads of
    inactive experiments are orphans, stopped ones are history."""
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
    # Not configured: no rows is "none", an alive container is an orphan container
    assert status.cell(1, "traceroute", states, [], expected=False).state == "none"
    assert status.cell(1, "traceroute", states, []).state == "never"
    alive = status.cell(1, "mqtt", states, [], expected=False)
    assert (alive.orphan_container, alive.label) == (True, "1/2 ⚠")
    stopped = status.cell(1, "speedtest", states, [], expected=False)
    assert (stopped.state, stopped.orphan_container) == ("none", False)


def test_satellite_without_metadata_and_mqtt():
    """A satellite node expects neither metadata nor mqtt, even with an active MQTT instance: no
    runs is "none", not a problem. With no main container configured and nothing running the
    Overview counts it once, as nothing running."""
    nodes = pd.DataFrame(
        [{"node_id": 4071, "status": "DEPLOYED", "municipality": None}]
    )
    experiments = pd.DataFrame(
        [{"id": 1, "node_id": 4071, "measurement_desc_id": 26, "stop_time": pd.NaT}]
    )
    rawdata = raw(("speedtest", "container", 100, 0.5))  # node 1 only
    summary = status.summarise(nodes, experiments, rawdata, NOW)
    assert [summary.cells[4071, c].state for c in ("metadata", "mqtt")] == ["none"] * 2
    assert status.problems(nodes, summary, rawdata).empty
    counts = status.overview(nodes, summary).set_index("status").loc["all"]
    assert (counts.all_main_ok, counts.some_issue, counts.nothing_running) == (0, 0, 1)


def test_grade():
    """Grade of a node: long-run only when every configured container runs 7 days or more (the
    containers that are not configured left out), else the worst class of its cells."""
    nodes, experiments, rawdata = synthetic(NOW)
    summary = status.summarise(nodes, experiments, rawdata, NOW)
    scenario = nodes.set_index("node_id").scenario
    grade = {s: status.grade(summary, n) for n, s in scenario.items()}
    assert (grade["all long-run"], grade["young"], grade["late"]) == (
        "long-run",
        "young",
        "late",
    )
    assert grade["no data"] == "never"


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
    assert any(c.orphan_container for c in cells)
    assert any(c.restart_warnings for c in cells)
    assert tuple(nodes.status.unique()) == status.STATUS_ORDER


def test_problems_and_overview():
    """Problems: every scenario with an issue, none of the healthy ones; DEPLOYED first, the silent
    ones first. Overview: the counts of each group add up."""
    nodes, experiments, rawdata = synthetic(NOW)
    summary = status.summarise(nodes, experiments, rawdata, NOW)
    found = status.problems(nodes, summary, rawdata)
    scenario = nodes.set_index("node_id").scenario
    healthy = {
        "all long-run",
        "fresh restart",
        "young",
        "stable",
        "version change",
        "release history",
    }
    assert set(found.node_id.map(scenario)) == set(SCENARIOS) - healthy
    assert found.status.tolist() == ["DEPLOYED"] * 16 + ["TESTING"] * 16
    assert found.node_id.map(scenario).iloc[0] == "no data"
    counts = status.overview(nodes, summary)
    assert (
        counts.all_main_ok + counts.some_issue + counts.nothing_running == counts.nodes
    ).all()
    assert counts.set_index("status").loc["all", "nodes"] == len(nodes)
