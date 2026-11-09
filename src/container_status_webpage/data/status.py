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
# Container status rules: thread states, cells, crosscheck, overview, problems
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
Rules of the container status (documentation/DESIGN.md sections 3-6): latest run and classes of
every thread, the cell
of a node and container (worst thread, partial, flapping, orphans), the overview counts and the
problem list.
Pandas only, no Dash.

Integrations:
    1. Input frames of DESIGN.md section 9: nodes, experiments, raw (report.container_rawdata).

Sample code:
```python
import pandas as pd

from container_status_webpage.data import status
from container_status_webpage.data.synthetic import synthetic

now = pd.Timestamp("2026-11-06 12:00")
nodes, experiments, raw = synthetic(now)
summary = status.summarise(nodes, experiments, raw, now)
status.problems(nodes, summary, raw)
```
"""

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

# Main and extra containers (DESIGN.md section 4)
MAIN: Tuple[str, ...] = ("metadata", "mqtt", "speedtest", "udpping")
EXTRA: Tuple[str, ...] = ("traceroute", "netperfmeter")

# Display names of the containers
NAME: Dict[str, str] = {
    "metadata": "Metadata",
    "mqtt": "MQTT",
    "speedtest": "Speedtest",
    "udpping": "UDP Ping",
    "traceroute": "Traceroute",
    "netperfmeter": "NetPerfMeter",
}

# Fixed threads per container; udpping adds sender-<id> / receiver-<id> per active udpping
# experiment
THREADS: Dict[str, Tuple[str, ...]] = {
    "metadata": ("homekeeping", "metadata"),
    "mqtt": ("container", "mqtt"),
    **{container: ("container",) for container in ("speedtest", "udpping") + EXTRA},
}

# Reported node_status groups in display order
STATUS_ORDER: Tuple[str, ...] = ("DEPLOYED", "TESTING")

# measurement_desc_id of udpping
UDPPING: int = 1

# Last seen classes: hours since the last heartbeat, upper limit inclusive (heartbeats arrive
# hourly)
SEEN: Tuple[Tuple[float, str], ...] = (
    (2, "running"),
    (6, "late"),
    (24, "stale"),
    (168, "down"),
    (math.inf, "long down"),
)

# Last seen classes from best to worst
SEVERITY: Tuple[str, ...] = ("running", "late", "stale", "down", "long down", "never")

# Uptime classes of running threads: hours, upper limit exclusive
UPTIME: Tuple[Tuple[float, str], ...] = (
    (1, "fresh"),
    (24, "young"),
    (168, "stable"),
    (math.inf, "long-run"),
)

# Starts within 24 h from which a thread is flapping
FLAPPING: int = 3


def seen_class(age_h: float) -> str:
    """
    Last seen class of a thread.

    Args:
        age_h (float): Hours since the last heartbeat.

    Returns:
        str: Class name of SEEN.
    """
    return next(name for limit, name in SEEN if age_h <= limit)


def uptime_class(uptime_h: float) -> str:
    """
    Uptime class of a running thread.

    Args:
        uptime_h (float): Uptime in hours.

    Returns:
        str: Class name of UPTIME.
    """
    return next(name for limit, name in UPTIME if uptime_h < limit)


def experiment_id(process: str) -> Optional[int]:
    """
    measurement_instance.id in the name of an udpping sender / receiver thread.

    Args:
        process (str): Thread name, e.g. "sender-10628".

    Returns:
        Optional[int]: The id, None for other threads.
    """
    kind, _, number = process.partition("-")
    return int(number) if kind in ("sender", "receiver") and number.isdigit() else None


def expected_threads(container: str, experiment_ids: List[int]) -> Tuple[str, ...]:
    """
    Threads a container must run on a node.

    Args:
        container (str): Container name.
        experiment_ids (List[int]): Active udpping experiments of the node.

    Returns:
        Tuple[str, ...]: Thread names; for udpping also sender-<id> and receiver-<id> per
            experiment.
    """
    udpping = tuple(
        f"{kind}-{e}" for e in experiment_ids for kind in ("sender", "receiver")
    )
    return THREADS[container] + (udpping if container == "udpping" else ())


def active_udpping(experiments: pd.DataFrame) -> Dict[int, List[int]]:
    """
    Active udpping experiments per node.

    Args:
        experiments (pd.DataFrame): Experiments frame (measurement_instance rows).

    Returns:
        Dict[int, List[int]]: Sorted measurement_instance ids per node_id.
    """
    active = experiments[
        (experiments.measurement_desc_id == UDPPING) & experiments.stop_time.isna()
    ]
    return active.groupby("node_id").id.apply(sorted).to_dict()


def thread_states(
    raw: pd.DataFrame, now: pd.Timestamp
) -> Dict[Tuple[int, str, str], Dict[str, Any]]:
    """
    Latest run of every thread with its classes and starts.

    Args:
        raw (pd.DataFrame): report.container_rawdata rows.
        now (pd.Timestamp): Reference time (UTC, naive).

    Returns:
        Dict[Tuple[int, str, str], Dict[str, Any]]: Per (node_id, container, process): start_ts,
            seen_ts, uptime,
            version of the latest run, age_h, seen and up classes, starts_24h, starts_7d.
    """
    # 1. Latest run per thread
    key = ["node_id", "container", "process"]
    latest = raw.sort_values("seen_ts").groupby(key).tail(1).set_index(key)
    # 2. Starts per thread within 24 h and 7 days
    starts = raw.groupby(key).start_ts
    states = latest[["start_ts", "seen_ts", "uptime", "version"]].assign(
        age_h=(now - latest.seen_ts).dt.total_seconds() / 3600,
        starts_24h=starts.apply(
            lambda s: s[s > now - pd.Timedelta(hours=24)].nunique()
        ),
        starts_7d=starts.apply(lambda s: s[s > now - pd.Timedelta(days=7)].nunique()),
    )
    # 3. Classes
    states["seen"] = states.age_h.map(seen_class)
    states["up"] = (states.uptime / 3600).map(uptime_class)
    return states.to_dict("index")


@dataclass
class Cell:
    """State of one node and container (DESIGN.md section 5)."""

    # Worst last seen class of the expected threads with rows, "never", or "none" (extra container
    # not deployed)
    state: str
    # Uptime class of the freshest running thread
    shade: str = ""
    # Some, but not all, expected threads running
    partial: bool = False
    # A thread with FLAPPING or more starts within 24 h
    flapping: bool = False
    # k/n of a partial cell, udpping "S a/n R b/n", "⚠+k" for orphans
    label: str = ""
    # Expected threads: name and state (None when never seen)
    threads: List[Tuple[str, Optional[Dict[str, Any]]]] = field(default_factory=list)
    # Running udpping threads of experiments that are not active on the node
    orphans: List[str] = field(default_factory=list)

    @property
    def running(self) -> bool:
        """At least one expected thread is running."""
        return self.state == "running" or self.partial


def cell(
    node_id: int,
    container: str,
    states: Dict[Tuple[int, str, str], Dict[str, Any]],
    experiment_ids: List[int],
) -> Cell:
    """
    Cell of a node and container: the class of its worst thread with rows; a never seen thread only
    makes it partial;
    udpping threads still running for an experiment that is not active on the node are orphans.

    Args:
        node_id (int): Node identifier.
        container (str): Container name.
        states (Dict[Tuple[int, str, str], Dict[str, Any]]): Thread states of thread_states.
        experiment_ids (List[int]): Active udpping experiments of the node.

    Returns:
        Cell: State of the cell.
    """
    # 1. Expected threads with their states, orphans of udpping
    threads = [
        (name, states.get((node_id, container, name)))
        for name in expected_threads(container, experiment_ids)
    ]
    orphans = []
    if container == "udpping":
        orphans = sorted(
            process
            for (n, c, process), state in states.items()
            if n == node_id
            and c == container
            and state["seen"] == "running"
            and experiment_id(process) is not None
            and experiment_id(process) not in experiment_ids
        )
    # 2. No expected thread seen: never (main) or not deployed (extra)
    present = [state for _, state in threads if state]
    if not present:
        return Cell(
            "never" if container in MAIN else "none", threads=threads, orphans=orphans
        )
    # 3. Partial and label
    running = [state for state in present if state["seen"] == "running"]
    partial = 0 < len(running) < len(threads)
    if container == "udpping":

        def count(kind: str) -> int:
            return sum(
                1
                for name, state in threads
                if name.startswith(kind) and state and state["seen"] == "running"
            )

        n = len(experiment_ids)
        label = f"S {count('sender-')}/{n} R {count('receiver-')}/{n}"
    else:
        label = f"{len(running)}/{len(threads)}" if partial else ""
    if orphans:
        label += f" ⚠+{len(orphans)}"
    # 4. Worst class, shade of the freshest running thread, flapping
    return Cell(
        state=max((state["seen"] for state in present), key=SEVERITY.index),
        shade=(
            uptime_class(min(state["uptime"] for state in running) / 3600)
            if running
            else ""
        ),
        partial=partial,
        flapping=any(state["starts_24h"] >= FLAPPING for state in present),
        label=label,
        threads=threads,
        orphans=orphans,
    )


@dataclass
class Summary:
    """Thread states and cells of the nodes at one time."""

    # Reference time (UTC, naive)
    now: pd.Timestamp
    # Thread states of thread_states
    states: Dict[Tuple[int, str, str], Dict[str, Any]]
    # Cell per (node_id, container)
    cells: Dict[Tuple[int, str], Cell]


def summarise(
    nodes: pd.DataFrame, experiments: pd.DataFrame, raw: pd.DataFrame, now: pd.Timestamp
) -> Summary:
    """
    Thread states and the cell of every node and container.

    Args:
        nodes (pd.DataFrame): Nodes frame.
        experiments (pd.DataFrame): Experiments frame.
        raw (pd.DataFrame): report.container_rawdata rows.
        now (pd.Timestamp): Reference time (UTC, naive).

    Returns:
        Summary: States and cells.
    """
    # 1. Thread states and active udpping experiments
    states = thread_states(raw, now)
    experiment_ids = active_udpping(experiments)
    # 2. One cell per node and container
    cells = {
        (node_id, container): cell(
            node_id, container, states, experiment_ids.get(node_id, [])
        )
        for node_id in nodes.node_id
        for container in MAIN + EXTRA
    }
    return Summary(now=now, states=states, cells=cells)


def ordered(nodes: pd.DataFrame) -> pd.DataFrame:
    """
    Nodes in display order: STATUS_ORDER, then node_id.

    Args:
        nodes (pd.DataFrame): Nodes frame.

    Returns:
        pd.DataFrame: Sorted nodes.
    """
    rank = nodes.status.map({status: i for i, status in enumerate(STATUS_ORDER)})
    return nodes.assign(rank=rank).sort_values(["rank", "node_id"]).drop(columns="rank")


def status_groups(nodes: pd.DataFrame) -> List[Tuple[str, List[int]]]:
    """
    Node ids per reported status in STATUS_ORDER, then all nodes.

    Args:
        nodes (pd.DataFrame): Nodes frame.

    Returns:
        List[Tuple[str, List[int]]]: Group name ("all" for all nodes) and node ids.
    """
    groups = [
        (status, nodes.node_id[nodes.status == status].tolist())
        for status in STATUS_ORDER
    ]
    return [(status, ids) for status, ids in groups if ids] + [
        ("all", nodes.node_id.tolist())
    ]


def overview(nodes: pd.DataFrame, summary: Summary) -> pd.DataFrame:
    """
    Node counts per status group: all main OK (every main cell running, not partial, without
    orphans), nothing
    running (no cell with a running thread), some issue (the rest).

    Args:
        nodes (pd.DataFrame): Nodes frame.
        summary (Summary): Cells of the nodes.

    Returns:
        pd.DataFrame: Columns status, nodes, all_main_ok, some_issue, nothing_running.
    """
    rows = []
    for group, ids in status_groups(nodes):
        ok = sum(
            all(
                summary.cells[n, c].state == "running"
                and not summary.cells[n, c].partial
                and not summary.cells[n, c].orphans
                for c in MAIN
            )
            for n in ids
        )
        idle = sum(
            not any(summary.cells[n, c].running for c in MAIN + EXTRA) for n in ids
        )
        rows.append(
            {
                "status": group,
                "nodes": len(ids),
                "all_main_ok": ok,
                "some_issue": len(ids) - ok - idle,
                "nothing_running": idle,
            }
        )
    return pd.DataFrame(rows)


def container_counts(nodes: pd.DataFrame, summary: Summary) -> pd.DataFrame:
    """
    Nodes running each container (a cell with a running thread) per status group.

    Args:
        nodes (pd.DataFrame): Nodes frame.
        summary (Summary): Cells of the nodes.

    Returns:
        pd.DataFrame: Column container, then one column per status group with the count.
    """
    groups = status_groups(nodes)
    return pd.DataFrame(
        [
            {
                "container": c,
                **{
                    group: sum(summary.cells[n, c].running for n in ids)
                    for group, ids in groups
                },
            }
            for c in MAIN + EXTRA
        ]
    )


def issue(container: str, c: Cell) -> str:
    """
    Issue text of a cell for the problem list.

    Args:
        container (str): Container name.
        c (Cell): The cell.

    Returns:
        str: E.g. "UDP Ping: partial S 1/2 R 2/2", empty when the cell is fine.
    """
    bad = c.state not in ("running", "none")
    if not (bad or c.partial or c.flapping or c.orphans):
        return ""
    parts = (
        f"{NAME[container]}:",
        c.state if bad else "",
        f"partial {c.label}" if c.partial else "",
        "flapping" if c.flapping else "",
        f"running for inactive experiment {', '.join(c.orphans)}" if c.orphans else "",
    )
    return " ".join(part for part in parts if part)


def problems(nodes: pd.DataFrame, summary: Summary, raw: pd.DataFrame) -> pd.DataFrame:
    """
    Nodes that are not fully OK, DEPLOYED first, then the longest silent.

    Args:
        nodes (pd.DataFrame): Nodes frame.
        summary (Summary): Cells of the nodes.
        raw (pd.DataFrame): report.container_rawdata rows (last heartbeat per node).

    Returns:
        pd.DataFrame: Columns node_id, status, municipality, issues, last_seen, silent_h (inf
            without heartbeat).
    """
    # 1. Last heartbeat per node
    last_seen = raw.groupby("node_id").seen_ts.max()
    # 2. Issues per node
    rows = []
    for node in nodes.itertuples():
        issues = [
            text
            for text in (issue(c, summary.cells[node.node_id, c]) for c in MAIN + EXTRA)
            if text
        ]
        if issues:
            seen = last_seen.get(node.node_id, pd.NaT)
            silent_h = (
                math.inf
                if pd.isna(seen)
                else (summary.now - seen).total_seconds() / 3600
            )
            rows.append(
                {
                    "node_id": node.node_id,
                    "status": node.status,
                    "municipality": node.municipality,
                    "issues": "; ".join(issues),
                    "last_seen": seen,
                    "silent_h": silent_h,
                }
            )
    # 3. DEPLOYED first, then the longest silent
    frame = pd.DataFrame(
        rows,
        columns=[
            "node_id",
            "status",
            "municipality",
            "issues",
            "last_seen",
            "silent_h",
        ],
    )
    rank = frame.status.map({status: i for i, status in enumerate(STATUS_ORDER)})
    return (
        frame.assign(rank=rank)
        .sort_values(["rank", "silent_h", "node_id"], ascending=[True, False, True])
        .drop(columns="rank")
        .reset_index(drop=True)
    )
