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
# Synthetic data covering every state of the container status rules
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
Synthetic input frames (DESIGN.md section 9) covering every class and marker of the container status
rules:
22 scenarios for DEPLOYED and TESTING on fake node ids from 90001. Used for development and tests
until the
database loader exists, and with DATA_SOURCE=synthetic afterwards.

Sample code:
```python
import pandas as pd

from container_status_webpage.data.synthetic import synthetic

nodes, experiments, raw = synthetic(pd.Timestamp("2026-11-06 12:00"))
```
"""

import json
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
from nnedbtools.batch.node_config import SupportedExperiment

from container_status_webpage.data.status import (
    EXTRA,
    MAIN,
    STATUS_ORDER,
    UDPPING,
    expected_threads,
)

# Scenarios, one node each per status; the target container rotates over the main containers
SCENARIOS: Tuple[str, ...] = (
    "all long-run",
    "fresh restart",
    "young",
    "stable",
    "late",
    "stale",
    "down",
    "long down",
    "never",
    "udpping partial",
    "thread missing",
    "thread down",
    "flapping",
    "version change",
    "extra containers",
    "nothing running",
    "no data",
    "inactive experiment",
    "mobile",
    "release history",
    "orphan container",
    "receiver restarts",
)

# Version line per container
VERSION: Dict[str, str] = {
    "metadata": "geo",
    "mqtt": "locum",
    "speedtest": "dendro",
    "udpping": "electro",
    "traceroute": "chrono",
    "netperfmeter": "cryo",
}

# Municipalities of the synthetic sites (municipality is optional)
MUNICIPALITIES: Tuple[Any, ...] = (
    "Oslo",
    "Bergen",
    "Trondheim",
    "Tromsø",
    "Stavanger",
    None,
)

# Providers and network ids of the synthetic experiments
PROVIDERS: Tuple[Tuple[str, int], ...] = (("Telenor", 1), ("Telia", 2), ("ICE", 3))

# Start of the node status per status group
VALID_FROM: Dict[str, str] = {"DEPLOYED": "2025-03-01", "TESTING": "2026-09-01"}

# Runs of a thread: (start hours ago, last seen hours ago, version)
Runs = List[Tuple[float, float, str]]


def mobile_runs(version: str) -> Runs:
    """
    Runs of a mobile node (as nodes 7042 and 7045): three trips of 0.4 h a day for 30 days, parked
    from day 10 to day 15, the last trip ended 3 h ago.

    Args:
        version (str): Version of every run.

    Returns:
        Runs: The runs, newest first.
    """
    return [
        (day * 24 + hour + 0.4, day * 24 + hour, version)
        for day in range(30)
        if not 10 <= day < 15
        for hour in (3, 9, 15)
    ]


def synthetic_threads(  # pylint: disable=too-many-return-statements
    scenario: str, target: str, container: str, experiment_ids: List[int]
) -> List[Tuple[str, Runs]]:
    """
    Threads of one container of one scenario with their runs.

    Args:
        scenario (str): Scenario of SCENARIOS.
        target (str): Main container the scenario applies to.
        container (str): Container to build.
        experiment_ids (List[int]): Active udpping experiments of the node.

    Returns:
        List[Tuple[str, Runs]]: Thread name and runs; an empty list for a container without rows.
    """
    # A. Threads and versions of the container, the base run: 30 days, last heartbeat 30 minutes ago
    names = expected_threads(container, experiment_ids)
    new, old = f"{VERSION[container]}-2-2-5", f"{VERSION[container]}-2-1-8-1"
    base: Runs = [(720, 0.5, new)]
    # B. Extra containers: configured and running / down in the scenario "extra containers";
    #    NetPerfMeter alive without a configured instance in the scenario "orphan container"
    if container in EXTRA:
        if scenario == "extra containers":
            runs = {"netperfmeter": base, "traceroute": [(720, 48, new)]}[container]
            return [(name, runs) for name in names]
        if (scenario, container) == ("orphan container", "netperfmeter"):
            return [(name, base) for name in names]
        return []
    # C. Scenarios of all main containers
    if scenario == "no data":
        return []
    if scenario == "nothing running":
        return [(name, [(720, 216, new)]) for name in names]
    if scenario == "mobile":
        return [(name, mobile_runs(new)) for name in names]
    if scenario == "release history":
        # As node 7056: all containers change together, back to a dev build, 50 h down
        line = VERSION[container]
        history = [
            (720, 400.1, f"{line}-2-1-8"),
            (400, 200, "dev-0-8-77"),
            (150, 100.1, f"{line}-2-2-4"),
            (100, 0.5, new),
        ]
        return [(name, history) for name in names]
    if scenario == "inactive experiment":
        # udpping also runs the threads of the stopped experiment node_id * 10 + 4
        stopped = (
            [
                (f"{kind}-{experiment_ids[0] + 4}", base)
                for kind in ("sender", "receiver")
            ]
            if container == "udpping"
            else []
        )
        return [(name, base) for name in names] + stopped
    # D. Scenarios of one thread: never seen (runs None) or down
    special = {
        "udpping partial": ("udpping", f"sender-{experiment_ids[1]}", None),
        "thread missing": ("metadata", "homekeeping", None),
        "thread down": ("mqtt", "mqtt", [(720, 48, new)]),
    }
    if scenario in special:
        where, thread, runs = special[scenario]
        return [
            (name, runs if (container, name) == (where, thread) else base)
            for name in names
            if not ((container, name) == (where, thread) and runs is None)
        ]
    # E. Scenarios of the target container
    if container != target:
        return [(name, base) for name in names]
    runs = {
        "all long-run": base,
        "extra containers": base,
        "orphan container": base,
        "receiver restarts": base,
        "fresh restart": [(720, 0.6, new), (0.4, 0.1, new)],
        "young": [(720, 10.2, new), (10, 0.5, new)],
        "stable": [(720, 72.2, new), (72, 0.5, new)],
        "late": [(720, 4, new)],
        "stale": [(720, 12, new)],
        "down": [(720, 72, new)],
        "long down": [(720, 240, new)],
        "never": [],
        "flapping": [
            (720, 20, new),
            (19.5, 19.4, new),
            (15, 14.8, new),
            (9, 8.9, new),
            (4, 3.5, new),
            (0.5, 0.1, new),
        ],
        "version change": [(720, 120.1, old), (120, 0.5, new)],
    }[scenario]
    return [(name, runs) for name in names] if runs else []


def synthetic_experiments(
    node_id: int, ids: List[int], scenario: str, now: pd.Timestamp
) -> List[Dict[str, Any]]:
    """
    Measurement instances of a node: the active udpping ones, MQTT and Speedtest instances (every
    main container is configured), Traceroute and NetPerfMeter instances in the scenario "extra
    containers", and a stopped udpping one in the scenario "inactive experiment"; service 1 (4G),
    the parameters JSON is made up.

    Args:
        node_id (int): Node identifier.
        ids (List[int]): Ids of the active udpping instances.
        scenario (str): Scenario of the node.
        now (pd.Timestamp): Reference time.

    Returns:
        List[Dict[str, Any]]: Rows of the experiments frame.
    """

    def instance(
        e: int, desc: int, k: int, stop: Any = pd.NaT, **parameters: Any
    ) -> Dict[str, Any]:
        provider, network_id = PROVIDERS[(node_id + k) % len(PROVIDERS)]
        return {
            "id": e,
            "node_id": node_id,
            "network_id": network_id,
            "service_id": 1,
            "provider": provider,
            "measurement_desc_id": desc,
            "iccid": f"8947{node_id:07d}{k:02d}",
            "start_time": now - pd.Timedelta(days=60),
            "stop_time": stop,
            "parameters": json.dumps({"synthetic": True, **parameters}),
        }

    udpping = {"interval_ms": 1000, "packet_size": 64, "target": "udpping.example.net"}
    rows = [instance(e, UDPPING, k, **udpping) for k, e in enumerate(ids)]
    # Measurement descriptor and interface index of the other configured containers
    others = [
        (SupportedExperiment.MQTT_COLLECTOR.value, 2),
        (SupportedExperiment.SPEEDTEST_EVERY_1_HOURS.value, 0),
    ]
    if scenario == "extra containers":
        others += [
            (SupportedExperiment.TRACEROUTE_ANYCAST.value, 1),
            (SupportedExperiment.NETPERFMETER_6_HOURS_EXPERIMENT.value, 2),
        ]
    rows += [
        instance(node_id * 10 + 5 + i, desc, k, schedule="hourly")
        for i, (desc, k) in enumerate(others)
    ]
    if scenario == "inactive experiment":
        rows.append(
            instance(
                node_id * 10 + 4, UDPPING, 2, stop=now - pd.Timedelta(days=5), **udpping
            )
        )
    return rows


def receiver_restarts(scenario: str, process: str, run_h: float) -> Optional[str]:
    """
    extra of a container_rawdata row (text, as in the table): the restart counter of a receiver;
    480 per hour of the run in the scenario "receiver restarts" (as node 7056), 1 otherwise (below
    the warning limits).

    Args:
        scenario (str): Scenario of the node.
        process (str): Thread name.
        run_h (float): Hours from the start to the last heartbeat of the run.

    Returns:
        Optional[str]: The counter, None for other threads.
    """
    if not process.startswith("receiver-"):
        return None
    return str(round(480 * run_h)) if scenario == "receiver restarts" else "1"


def synthetic(now: pd.Timestamp) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Synthetic nodes, experiments and container_rawdata rows: every scenario for every status group.

    Args:
        now (pd.Timestamp): Reference time (UTC, naive); runs are placed relative to it.

    Returns:
        Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]: nodes, experiments, raw.
    """
    nodes, experiments, raw = [], [], []
    node_id = 90000
    for s, status in enumerate(STATUS_ORDER):
        for i, scenario in enumerate(SCENARIOS):
            # 1. Node with its site
            node_id += 1
            ids = [
                node_id * 10,
                node_id * 10 + 2,
            ]  # pairs of even ids as the real measurement_instance ids
            nodes.append(
                {
                    "node_id": node_id,
                    "status": status,
                    "valid_from": pd.Timestamp(VALID_FROM[status]),
                    "interfaces": 3,
                    "experiments": 5,
                    "scenario": scenario,
                    "name": f"Synthetic site {node_id}",
                    "address": f"Testveien {node_id % 100}",
                    "zip": f"{node_id % 9000 + 1000}",
                    "municipality": MUNICIPALITIES[node_id % len(MUNICIPALITIES)],
                    "country_code": "NO",
                }
            )
            # 2. Experiments
            experiments += synthetic_experiments(node_id, ids, scenario, now)
            # 3. Runs of every thread
            target = MAIN[(i + s) % len(MAIN)]
            for container in MAIN + EXTRA:
                for process, runs in synthetic_threads(
                    scenario, target, container, ids
                ):
                    for start_h, seen_h, version in runs:
                        start, seen = now - pd.Timedelta(
                            hours=start_h
                        ), now - pd.Timedelta(hours=seen_h)
                        raw.append(
                            {
                                "node_id": node_id,
                                "start_ts": start,
                                "container": container,
                                "version": version,
                                "process": process,
                                "seen_ts": seen,
                                "uptime": (seen - start).total_seconds(),
                                "extra": receiver_restarts(
                                    scenario, process, start_h - seen_h
                                ),
                            }
                        )
    return pd.DataFrame(nodes), pd.DataFrame(experiments), pd.DataFrame(raw)
