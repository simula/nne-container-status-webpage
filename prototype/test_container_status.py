"""Checks of the colour rules: class boundaries, flapping, worst thread / partial, synthetic coverage.

Run: python test_container_status.py  (or pytest)
"""

import container_status as cs
import pandas as pd

NOW = pd.Timestamp("2026-11-06 12:00")


def raw(*rows):
    """(container, process, start hours ago, last seen hours ago) on node 1."""
    return pd.DataFrame(
        [
            dict(
                node_id=1,
                container=c,
                process=p,
                version="v",
                start_ts=NOW - pd.Timedelta(hours=s),
                seen_ts=NOW - pd.Timedelta(hours=e),
                uptime=(s - e) * 3600,
                extra=None,
            )
            for c, p, s, e in rows
        ]
    )


def test_class_boundaries():
    assert [cs.seen_class(h) for h in (2, 2.01, 6, 6.01, 24, 24.01, 168, 168.01)] == [
        "running",
        "late",
        "late",
        "stale",
        "stale",
        "down",
        "down",
        "long down",
    ]
    assert [cs.uptime_class(h) for h in (0.99, 1, 23.99, 24, 167.99, 168)] == [
        "fresh",
        "young",
        "young",
        "stable",
        "stable",
        "long-run",
    ]


def test_flapping():
    three = cs.thread_states(
        raw(*[("speedtest", "container", s, s - 0.1) for s in (20, 10, 1)]), NOW
    )
    two = cs.thread_states(
        raw(*[("speedtest", "container", s, s - 0.1) for s in (30, 10, 1)]), NOW
    )
    assert cs.cell(1, "speedtest", three, []).flapping
    assert not cs.cell(1, "speedtest", two, []).flapping


def test_worst_thread_and_partial():
    states = cs.thread_states(
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
    # active experiments 10, 12: sender-12 never seen; sender-14 still running for an inactive experiment (orphan),
    # receiver-16 of an inactive experiment is down (history, not an orphan)
    udpping = cs.cell(1, "udpping", states, [10, 12])
    assert (udpping.state, udpping.partial, udpping.label) == (
        "running",
        True,
        "S 1/2 R 2/2 ⚠+1",
    )
    assert udpping.orphans == ["sender-14"]
    mqtt = cs.cell(1, "mqtt", states, [])  # mqtt thread down, container running
    assert (mqtt.state, mqtt.partial) == ("down", True)
    speedtest = cs.cell(1, "speedtest", states, [])  # all threads down: not partial
    assert (speedtest.state, speedtest.partial) == ("down", False)
    assert cs.cell(1, "metadata", states, []).state == "never"
    assert cs.cell(1, "traceroute", states, []).state == "none"


def test_synthetic_covers_every_class():
    nodes, experiments, rawdata = cs.synthetic(NOW)
    _, cells = cs.summarise(nodes, experiments, rawdata, NOW)
    cells = list(cells.values())
    assert set(cs.SEVERITY) | {"none"} <= {c.state for c in cells}
    assert {name for _, name in cs.UPTIME} <= {c.shade for c in cells}
    assert any(c.partial and c.state == "running" for c in cells)
    assert any(c.partial and c.state != "running" for c in cells)
    assert any(c.flapping for c in cells)
    assert any(c.orphans for c in cells)
    assert set(nodes.status) == set(cs.STATUS_ORDER)


if __name__ == "__main__":
    for name, test in list(globals().items()):
        if name.startswith("test_"):
            test()
    print("ok")
