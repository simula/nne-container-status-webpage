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

import dataclasses
from types import SimpleNamespace
from unittest import mock

import dash
import pandas as pd

from container_status_webpage.controller.node import (
    set_range,
    show_parameters,
    show_run,
)
from container_status_webpage.model import limits, pages, status, timeline
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
    data = pages.node(SNAPSHOT, node_id, None)
    shown = node.timeline(
        data.rows, data.segments, data.shown
    ).figure.layout.xaxis.range
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
    data = pages.node(SNAPSHOT, node_id, None)
    threads = node.threads_table(data.threads).rowData
    assert len(threads) == len(timeline.thread_rows(SNAPSHOT, node_id))
    assert sum(row["state"].startswith("inactive experiment ") for row in threads) == 2
    experiments = node.experiments_table(data.experiments).rowData
    assert [row["stop"] == "active" for row in experiments] == [True] * 4 + [False]
    view = node.parameters_view(experiments[0]["id"], experiments[0]["parameters"])
    assert '\n  "synthetic": true' in view.children[1].children


def test_header_and_networks():
    """Header: counts of interfaces and experiments (+ 1 for metadata), one chip per network of the
    active experiments (not the stopped Ice one, not the dummy network 0 of MQTT). Experiments
    table: measurement with its container, network by name of the nnedbtools enum_mapper.
    """
    node_id = node_of("inactive experiment")
    data = pages.node(SNAPSHOT, node_id, None)
    header = node.header(data.node_id, data.node, data.networks)
    texts = [child.children for child in header.children]
    assert texts[3:] == ["2 interfaces · 5 experiments", "Telenor:4G", "Telia:5G"]
    experiments = node.experiments_table(data.experiments).rowData
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
    data = pages.node(SNAPSHOT, node_id, "udpping")
    figure = node.timeline(data.rows, data.segments, data.shown, data.container).figure
    ticks = figure.layout.yaxis.ticktext
    assert len(ticks) == len(rows)
    assert all(
        text.startswith("<b>") == (container == "udpping")
        for (container, _, _), text in zip(rows, ticks)
    )


def test_span_ignores_clock_errors():
    """A start before the first real deployment (node clock error, 2011) does not stretch the
    timeline: its first start is FIRST_DEPLOYMENT."""
    node_id = node_of("release history")
    raw = SNAPSHOT.raw.copy()
    raw.loc[raw.index[raw.node_id == node_id][0], "start_ts"] = pd.Timestamp(
        "2011-11-11"
    )
    first, _ = timeline.span(dataclasses.replace(SNAPSHOT, raw=raw), node_id)
    assert first == limits.FIRST_DEPLOYMENT


def patched(figure) -> dict:
    """Assigned values of a dash.Patch by their location."""
    operations = figure.to_plotly_json()["operations"]
    return {tuple(op["location"]): op["params"]["value"] for op in operations}


def test_click_callbacks():
    """A click on a timeline bar shows its detail; a click on an experiment its parameters."""
    custom = [
        "UDP Ping · receiver-1",
        "Run (stable)",
        "2026-11-01 10:00",
        "2026-11-02 10:00",
    ]
    custom += ["1d 0h", "v1", "–", "–"]
    detail = show_run({"points": [{"customdata": custom}]})
    assert [row.children[1].children for row in detail.children] == custom
    rows = [{"id": 12, "parameters": '{"a": 1}'}, {"id": 13, "parameters": '{"b": 2}'}]
    view = show_parameters({"rowId": "13"}, rows)
    assert view.children[0].children == "Parameters of experiment 13"
    assert '"b": 2' in view.children[1].children


def test_range_callback():
    """A range button sets its exact range and fills the pickers with its days; a picker sets whole
    days and clears the button; a reversed picker range changes nothing."""
    first_now = ["2026-10-01 08:00:00", "2026-11-06 12:00:00"]
    with mock.patch("dash.ctx", SimpleNamespace(triggered_id="node-range")):
        button, start, end, figure = set_range("3", None, None, first_now)
    assert (button, start, end) == (dash.no_update, "2026-11-03", "2026-11-06")
    assert patched(figure)[("layout", "xaxis", "range")] == [
        "2026-11-03 12:00:00",
        "2026-11-06 12:00:00",
    ]
    with mock.patch("dash.ctx", SimpleNamespace(triggered_id="node-from")):
        button, start, end, figure = set_range(
            "3", "2026-11-01", "2026-11-02", first_now
        )
    assert (button, start, end) == (None, dash.no_update, dash.no_update)
    assert patched(figure)[("layout", "xaxis", "range")] == [
        "2026-11-01 00:00:00",
        "2026-11-03 00:00:00",
    ]
    with mock.patch("dash.ctx", SimpleNamespace(triggered_id="node-to")):
        assert (
            set_range("3", "2026-11-05", "2026-11-01", first_now)
            == (dash.no_update,) * 4
        )


def test_span_one_year_back():
    """A year after the first runs, the timeline starts HISTORY before the load time: "All" and the
    From picker reach back one year at most, also for a run that started earlier."""
    node_id = node_of("release history")
    later = pd.Timestamp("2027-06-01 12:00")
    raw = SNAPSHOT.raw.copy()
    raw.loc[raw.index[raw.node_id == node_id][0], "start_ts"] = pd.Timestamp(
        "2026-02-01"
    )
    summary = dataclasses.replace(SNAPSHOT.summary, now=later)
    snapshot = dataclasses.replace(SNAPSHOT, raw=raw, summary=summary)
    assert timeline.span(snapshot, node_id) == (later - limits.HISTORY, later)


def test_run_cut_at_the_window():
    """A run older than HISTORY and still alive starts at the window on the timeline (bar and
    hover); its class stays that of the whole run."""
    node_id = node_of("release history")
    later = pd.Timestamp("2027-06-01 12:00")
    raw = SNAPSHOT.raw.copy()
    row = raw.index[raw.node_id == node_id][0]
    raw.loc[row, "start_ts"] = pd.Timestamp("2026-02-01")
    raw.loc[row, "seen_ts"] = later - pd.Timedelta(hours=1)
    summary = dataclasses.replace(SNAPSHOT.summary, now=later)
    frame = timeline.segments(
        dataclasses.replace(SNAPSHOT, raw=raw, summary=summary), node_id
    )
    run = frame[
        (frame.container == raw.container[row])
        & (frame.thread == raw.process[row])
        & (frame.kind == "run")
        & (frame.end == later - pd.Timedelta(hours=1))
    ]
    assert run.start.tolist() == [later - limits.HISTORY]
    assert run.cls.tolist() == ["long-run"]
