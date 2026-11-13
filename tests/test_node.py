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
# Checks of the Node page: timeline segments
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
Checks of the Node page (model/timeline.py, view/node.py) on the synthetic data: timeline segments
of a mobile node and of a node with a release history, the timeline rows.

Sample code:
```bash
pytest tests/test_node.py
```
"""

import pandas as pd

from container_status_webpage.model import status, timeline
from container_status_webpage.model.snapshot import load
from container_status_webpage.view import node

# pylint: disable=no-member

SNAPSHOT = load("synthetic", pd.Timestamp("2026-11-06 12:00"))


def node_of(scenario: str) -> int:
    """First synthetic node of a scenario."""
    nodes = SNAPSHOT.nodes
    return int(nodes.node_id[nodes.scenario == scenario].iloc[0])


def test_mobile_segments():
    """Mobile node: 75 trips, a down segment between every two (5.6 h within a day, 131.6 h while
    parked), silent (late) since the last trip."""
    frame = timeline.segments(SNAPSHOT, node_of("mobile"))
    thread = frame[(frame.container == "mqtt") & (frame.thread == "mqtt")]
    down = thread[thread.kind == "down"]
    assert (thread.kind == "run").sum() == 75 and len(down) == 74
    hours = (down.end - down.start).dt.total_seconds() / 3600
    assert (round(hours.min(), 1), round(hours.max(), 1)) == (5.6, 131.6)
    silent = thread[thread.kind == "silent"]
    assert silent.cls.tolist() == ["late"]
    assert silent.end.iloc[0] == SNAPSHOT.summary.now


def test_release_history_segments():
    """Release history: every thread has three version changes (back to a dev build) and one
    down segment of 50 h; still running, so not silent."""
    frame = timeline.segments(SNAPSHOT, node_of("release history"))
    kinds = (
        frame.groupby(["container", "thread"]).kind.value_counts().unstack(fill_value=0)
    )
    assert (kinds["version"] == 3).all() and (kinds["down"] == 1).all()
    assert "silent" not in kinds
    down = frame[frame.kind == "down"]
    assert ((down.end - down.start) == pd.Timedelta(hours=50)).all()
    homekeeping = frame[(frame.thread == "homekeeping") & (frame.kind == "version")]
    assert homekeeping.previous.tolist() == ["geo-2-1-8", "dev-0-8-77", "geo-2-2-4"]


def test_range_buttons():
    """Range buttons: n days back from the load time, all from the first start of a shown thread
    (the release history starts 720 h before the load time); the timeline opens on 7 days.
    """
    node_id = node_of("release history")
    first, now = timeline.span(SNAPSHOT, node_id)
    assert (first, now) == (now - pd.Timedelta(hours=720), SNAPSHOT.summary.now)
    assert timeline.x_range(first, now, "1") == [now - pd.Timedelta(days=1), now]
    assert timeline.x_range(first, now, "all") == [first, now]
    shown = node.timeline(SNAPSHOT, node_id).figure.layout.xaxis.range
    assert [pd.Timestamp(t) for t in shown] == [now - pd.Timedelta(days=7), now]


def test_range_pickers():
    """From / To date pickers: whole days from 00:00, one day too; To at most the load time (today
    ends at the newest data); a reversed range or an empty date gives None (the timeline stays).
    """
    now, day = pd.Timestamp("2026-11-11 06:00"), pd.Timestamp("2026-06-01")
    assert timeline.picker_range("2026-06-01", "2026-06-01", now) == [
        day,
        day + pd.Timedelta(days=1),
    ]
    assert timeline.picker_range("2026-11-10", "2026-11-11", now) == [
        now.normalize() - pd.Timedelta(days=1),
        now,
    ]
    assert timeline.picker_range("2026-06-02", "2026-06-01", now) is None
    assert timeline.picker_range(None, "2026-06-01", now) is None


def test_threads_and_experiments_tables():
    """Threads table: one row per timeline row, the orphans with their inactive experiment as
    state. Experiments table: the 4 active ones first, the stopped UDP Ping one last; parameters as
    indented JSON."""
    node_id = node_of("inactive experiment")
    threads = node.threads_table(SNAPSHOT, node_id).rowData
    assert len(threads) == len(timeline.thread_rows(SNAPSHOT, node_id))
    assert sum(row["state"].startswith("inactive experiment ") for row in threads) == 2
    experiments = node.experiments_table(SNAPSHOT, node_id).rowData
    assert [row["stop"] == "active" for row in experiments] == [True] * 4 + [False]
    view = node.parameters_view(experiments[0]["id"], experiments[0]["parameters"])
    assert '\n  "synthetic": true' in view.children[1].children


def test_header_and_networks():
    """Header: counts of interfaces and experiments (+ 1 for metadata), one chip per network of the
    active experiments (not the stopped Ice one, not the dummy network 0 of MQTT). Experiments
    table: measurement with its container, network by name of the nnedbtools enum_mapper.
    """
    node_id = node_of("inactive experiment")
    texts = [child.children for child in node.header(SNAPSHOT, node_id).children]
    assert texts[3:] == ["2 interfaces · 5 experiments", "Telenor:4G", "Telia:5G"]
    experiments = node.experiments_table(SNAPSHOT, node_id).rowData
    assert [(row["measurement"], row["network"]) for row in experiments] == [
        ("1 (UDP Ping)", "Telenor:4G"),
        ("1 (UDP Ping)", "Telia:5G"),
        ("26 (MQTT)", ""),
        ("18 (Speedtest)", "Telenor:4G"),
        ("1 (UDP Ping)", "Ice:4G"),
    ]


def test_networks_without_service():
    """A measurement instance without service_id (nullable in nne) counts as service 0 instead of
    breaking the Node page."""
    experiments = SNAPSHOT.experiments.head(1).assign(service_id=float("nan"))
    assert status.networks(experiments).service_id.tolist() == [0]


def test_timeline_rows():
    """One timeline row per thread of the deployed containers, orphans included; the highlighted
    container in bold."""
    node_id = node_of("inactive experiment")
    rows = timeline.thread_rows(SNAPSHOT, node_id)
    assert [kind for _, _, kind in rows].count("orphan") == 2
    ticks = node.timeline(SNAPSHOT, node_id, "udpping").figure.layout.yaxis.ticktext
    assert len(ticks) == len(rows)
    assert all(
        text.startswith("<b>") == (container == "udpping")
        for (container, _, _), text in zip(rows, ticks)
    )
