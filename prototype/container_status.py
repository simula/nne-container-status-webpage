"""Container status page: one static HTML file with tabs, a colour grid with hover detail and node detail timelines.

Phase 1 renders synthetic data that covers every colour combination:
    python container_status.py --synthetic out.html

The input frames have the columns of the real tables, so a database loader can replace `synthetic()` later:
    nodes        node_id, status (nne.node_status / nne.status), valid_from, interfaces, experiments,
                 name, address, zip, municipality (optional), country_code (site address: nne.node_address / nne.address)
    experiments  nne.measurement_instance rows of the nodes (id, node_id, network_id, measurement_desc_id, iccid,
                 start_time, stop_time, parameters) plus provider (network name)
    raw          report.container_rawdata columns
"""

import argparse
import html
import json
import math
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

MAIN = ("metadata", "mqtt", "speedtest", "udpping")
EXTRA = ("traceroute", "netperfmeter", "hipercontracer")
# Fixed threads per container; udpping adds sender-<id> / receiver-<id> per active udpping experiment
THREADS = {
    "metadata": ("homekeeping", "metadata"),
    "mqtt": ("container", "mqtt"),
} | dict.fromkeys(("speedtest", "udpping") + EXTRA, ("container",))

STATUS_ORDER = ("DEPLOYED", "TESTING")  # the only reported node_status groups
STATUS_COLOUR = {"DEPLOYED": "#1f3a93", "TESTING": "#7b3fb5"}

# Last seen classes: hours since the last heartbeat (upper limit inclusive); heartbeats arrive hourly
SEEN = (
    (2, "running"),
    (6, "late"),
    (24, "stale"),
    (168, "down"),
    (math.inf, "long down"),
)
SEVERITY = ("running", "late", "stale", "down", "long down", "never")
# Uptime classes of running threads: hours (upper limit exclusive)
UPTIME = ((1, "fresh"), (24, "young"), (168, "stable"), (math.inf, "long-run"))
FLAPPING = 3  # starts within 24 h
WINDOW = pd.Timedelta(days=14)  # node detail timeline

# (background, text) per class; aligned with nne-viz web/src/constants/colors.tsx (Status, UpRate)
COLOUR = {
    "fresh": ("#bfddd3", "#000"),
    "young": ("#80bca8", "#000"),
    "stable": ("#409a7c", "#fff"),
    "long-run": ("#007850", "#fff"),
    "late": ("#efc94d", "#000"),
    "stale": ("#e16437", "#fff"),
    "down": ("#e13737", "#fff"),
    "long down": ("#a50f15", "#fff"),
    "never": ("#dddddd", "#000"),
    "none": ("#ffffff", "#000"),
}
SYMBOL = {
    "running": "✓",
    "late": "!",
    "stale": "!",
    "down": "×",
    "long down": "×",
    "never": "–",
    "none": "",
}
PARTIAL = "#d39e00"
ORPHAN = (
    "#a50f15"  # udpping thread running for an experiment that is not active on the node
)
UDPPING = 1  # measurement_desc_id of udpping
# nne-viz provider colours
PROVIDER = {
    "Telenor": "#19aaf8",
    "Telia": "#9308db",
    "ICE": "#ffb900",
    "ICE-R": "#ff8800",
    "LAN": "#00cc5c",
}


# ---- classification ----------------------------------------------------------------------------


def seen_class(age_h: float) -> str:
    return next(name for limit, name in SEEN if age_h <= limit)


def uptime_class(uptime_h: float) -> str:
    return next(name for limit, name in UPTIME if uptime_h < limit)


def expected_threads(container: str, experiment_ids) -> tuple:
    udpping = tuple(
        f"{kind}-{e}" for e in experiment_ids for kind in ("sender", "receiver")
    )
    return THREADS[container] + (udpping if container == "udpping" else ())


def thread_states(raw: pd.DataFrame, now: pd.Timestamp) -> dict:
    """Latest run per (node_id, container, process) with its classes and start counts."""
    key = ["node_id", "container", "process"]
    latest = raw.sort_values("seen_ts").groupby(key).tail(1).set_index(key)
    starts = raw.groupby(key).start_ts
    states = latest[["start_ts", "seen_ts", "uptime", "version"]].assign(
        age_h=(now - latest.seen_ts).dt.total_seconds() / 3600,
        restarts_24h=starts.apply(
            lambda s: s[s > now - pd.Timedelta(hours=24)].nunique()
        ),
        restarts_7d=starts.apply(lambda s: s[s > now - pd.Timedelta(days=7)].nunique()),
    )
    states["seen"] = states.age_h.map(seen_class)
    states["up"] = (states.uptime / 3600).map(uptime_class)
    return states.to_dict("index")


@dataclass
class Cell:
    state: str  # SEVERITY class, or "none" (extra container not deployed)
    shade: str = ""  # uptime class of the freshest running thread
    partial: bool = False  # some threads running, not all
    flapping: bool = False
    label: str = ""
    threads: list = field(default_factory=list)  # (name, state dict or None)
    orphans: list = field(
        default_factory=list
    )  # running udpping threads of experiments not active on the node


def cell(node_id, container: str, states: dict, experiment_ids) -> Cell:
    """Cell takes the class of its worst seen thread; a never seen thread only makes it partial. udpping threads
    still running for an experiment that is not active on the node are orphans (bad)."""
    threads = [
        (name, states.get((node_id, container, name)))
        for name in expected_threads(container, experiment_ids)
    ]
    orphans = sorted(
        p
        for (n, c, p), s in states.items()
        if n == node_id
        and c == container
        and s["seen"] == "running"
        and experiment(p) is not None
        and experiment(p) not in experiment_ids
    )
    present = [s for _, s in threads if s]
    if not present:
        return Cell(
            "never" if container in MAIN else "none", threads=threads, orphans=orphans
        )
    running = [s for s in present if s["seen"] == "running"]
    partial = 0 < len(running) < len(threads)
    if container == "udpping":

        def count(kind):
            return sum(
                1
                for name, s in threads
                if name.startswith(kind) and s and s["seen"] == "running"
            )

        label = f"S {count('sender-')}/{len(experiment_ids)} R {count('receiver-')}/{len(experiment_ids)}"
    else:
        label = f"{len(running)}/{len(threads)}" if partial else ""
    if orphans:
        label += f" ⚠+{len(orphans)}"
    return Cell(
        state=max((s["seen"] for s in present), key=SEVERITY.index),
        shade=uptime_class(min(s["uptime"] for s in running) / 3600) if running else "",
        partial=partial,
        flapping=any(s["restarts_24h"] >= FLAPPING for s in present),
        label=label,
        threads=threads,
        orphans=orphans,
    )


def summarise(nodes, experiments, raw, now):
    states = thread_states(raw, now)
    active = experiments[
        (experiments.measurement_desc_id == UDPPING) & experiments.stop_time.isna()
    ]
    experiment_ids = active.groupby("node_id").id.apply(sorted).to_dict()
    cells = {
        (n, c): cell(n, c, states, experiment_ids.get(n, []))
        for n in nodes.node_id
        for c in MAIN + EXTRA
    }
    return states, cells


def running(c: Cell) -> bool:
    return c.state == "running" or c.partial


def issue(container: str, c: Cell) -> str:
    bad = c.state not in ("running", "none")
    if not (bad or c.partial or c.flapping or c.orphans):
        return ""
    return " ".join(
        filter(
            None,
            (
                f"{container}:",
                c.state if bad else "",
                f"partial {c.label}" if c.partial else "",
                "flapping" if c.flapping else "",
                (
                    f"running for inactive experiment {', '.join(c.orphans)}"
                    if c.orphans
                    else ""
                ),
            ),
        )
    )


# ---- synthetic data ----------------------------------------------------------------------------

SCENARIOS = (
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
)
VERSION = {
    "metadata": "geo",
    "mqtt": "locum",
    "speedtest": "dendro",
    "udpping": "electro",
    "traceroute": "chrono",
    "netperfmeter": "cryo",
    "hipercontracer": "hipercontracer",
}


def synthetic_threads(
    scenario: str, target: str, container: str, experiment_ids
) -> list:
    """(process, [(start hours ago, last seen hours ago, version)]) of one container in one scenario."""
    names = expected_threads(container, experiment_ids)
    new, old = f"{VERSION[container]}-2-2-5", f"{VERSION[container]}-2-1-8-1"
    base = [(720, 0.5, new)]  # running for 30 days, last heartbeat 30 min ago
    if container in EXTRA:
        runs = {
            "netperfmeter": base,
            "traceroute": [(720, 48, new)],
            "hipercontracer": [(720, 3, new)],
        }[container]
        return [(n, runs) for n in names] if scenario == "extra containers" else []
    if scenario == "no data":
        return []
    if scenario == "nothing running":
        return [(n, [(720, 216, new)]) for n in names]
    special = {
        "udpping partial": (
            "udpping",
            f"sender-{experiment_ids[1]}",
            None,
        ),  # never seen
        "thread missing": ("metadata", "homekeeping", None),
        "thread down": ("mqtt", "mqtt", [(720, 48, new)]),
    }
    if scenario in special:
        where, name, runs = special[scenario]
        return [
            (n, runs if (container, n) == (where, name) else base)
            for n in names
            if not ((container, n) == (where, name) and runs is None)
        ]
    if (
        scenario == "inactive experiment"
    ):  # udpping also runs the threads of the stopped experiment node_id*10+4
        stopped = (
            [(f"{k}-{experiment_ids[0] + 4}", base) for k in ("sender", "receiver")]
            if container == "udpping"
            else []
        )
        return [(n, base) for n in names] + stopped
    if container != target:
        return [(n, base) for n in names]
    runs = {
        "all long-run": base,
        "extra containers": base,
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
    return [(n, runs) for n in names] if runs else []


def synthetic_experiments(node_id, ids, scenario, now) -> list:
    """Active udpping instances `ids`, three other active instances, a stopped udpping one for "inactive experiment";
    the parameters JSON is made up."""
    providers = (("Telenor", 1), ("Telia", 2), ("ICE", 3))

    def instance(e, desc, k, stop=pd.NaT, **parameters):
        provider, network_id = providers[(node_id + k) % 3]
        return dict(
            id=e,
            node_id=node_id,
            network_id=network_id,
            provider=provider,
            measurement_desc_id=desc,
            iccid=f"8947{node_id:07d}{k:02d}",
            start_time=now - pd.Timedelta(days=60),
            stop_time=stop,
            parameters=json.dumps(dict(synthetic=True, **parameters)),
        )

    udpping = dict(interval_ms=1000, packet_size=64, target="udpping.example.net")
    out = [instance(e, UDPPING, k, **udpping) for k, e in enumerate(ids)]
    out += [
        instance(node_id * 10 + 5 + k, 2 + k, k, schedule="hourly") for k in range(3)
    ]
    if scenario == "inactive experiment":
        out.append(
            instance(
                node_id * 10 + 4, UDPPING, 2, stop=now - pd.Timedelta(days=5), **udpping
            )
        )
    return out


def synthetic(now: pd.Timestamp):
    """Every scenario for every status on fake node ids from 90001; the scenario target container rotates."""
    nodes, experiments, raw = [], [], []
    node_id = 90000
    municipalities = (
        "Oslo",
        "Bergen",
        "Trondheim",
        "Tromsø",
        "Stavanger",
        None,
    )  # municipality is optional
    for s, (status, valid_from) in enumerate(
        (("DEPLOYED", "2025-03-01"), ("TESTING", "2026-09-01"))
    ):
        for i, scenario in enumerate(SCENARIOS):
            node_id += 1
            ids = [
                node_id * 10,
                node_id * 10 + 2,
            ]  # like the real pairs of even measurement_instance ids
            nodes.append(
                dict(
                    node_id=node_id,
                    status=status,
                    valid_from=pd.Timestamp(valid_from),
                    interfaces=3,
                    experiments=5,
                    scenario=scenario,
                    name=f"Synthetic site {node_id}",
                    address=f"Testveien {node_id % 100}",
                    zip=f"{node_id % 9000 + 1000}",
                    municipality=municipalities[node_id % len(municipalities)],
                    country_code="NO",
                )
            )
            experiments += synthetic_experiments(node_id, ids, scenario, now)
            for container in MAIN + EXTRA:
                for process, runs in synthetic_threads(
                    scenario, MAIN[(i + s) % len(MAIN)], container, ids
                ):
                    for start_h, seen_h, version in runs:
                        start, seen = now - pd.Timedelta(
                            hours=start_h
                        ), now - pd.Timedelta(hours=seen_h)
                        raw.append(
                            dict(
                                node_id=node_id,
                                start_ts=start,
                                container=container,
                                version=version,
                                process=process,
                                seen_ts=seen,
                                uptime=(seen - start).total_seconds(),
                                extra=None,
                            )
                        )
    return pd.DataFrame(nodes), pd.DataFrame(experiments), pd.DataFrame(raw)


# ---- rendering ---------------------------------------------------------------------------------


def esc(text) -> str:
    return html.escape(str(text))


def blank(value) -> str:
    return "" if pd.isna(value) else str(value)


def epoch(ts) -> int:
    return int(ts.timestamp())  # naive timestamps are UTC


def when(ts) -> str:
    return "–" if pd.isna(ts) else f"{ts:%Y-%m-%d %H:%M}"


def duration(seconds: float) -> str:
    minutes = int(seconds // 60)
    days, hours, minutes = minutes // 1440, minutes // 60 % 24, minutes % 60
    return (
        f"{days}d {hours}h"
        if days
        else f"{hours}h {minutes}m" if hours else f"{minutes}m"
    )


def chip(status: str) -> str:
    return f'<span class="chip" style="background:{STATUS_COLOUR.get(status, "#444")}">{esc(status)}</span>'


def colour(c: Cell) -> tuple:
    return COLOUR[c.shade if c.state == "running" else c.state]


def experiment(name: str):
    kind, _, number = name.partition("-")
    return int(number) if kind in ("sender", "receiver") and number.isdigit() else None


def experiment_label(e, info: dict) -> str:
    row = info.get(e)
    if row is None:
        return f"{e} (not on this node)"
    return f"{e} ({row.provider}{', stopped' if pd.notna(row.stop_time) else ''})"


def parameters(value) -> str:
    if pd.isna(value):
        return ""
    try:
        text = json.dumps(json.loads(value), indent=2, ensure_ascii=False)
    except TypeError, ValueError:
        text = str(value)
    return f"<details><summary>parameters</summary><pre>{esc(text)}</pre></details>"


def hover(node, container: str, c: Cell) -> str:
    lines = [
        f"node {node.node_id} · {node.status} · {container}: {c.state}"
        + (" · partial" if c.partial else "")
        + (" · flapping" if c.flapping else "")
    ]
    for name, s in c.threads:
        lines.append(
            f"{name}: never seen"
            if s is None
            else f"{name}: {s['seen']}, {s['version']}, up {duration(s['uptime'])}, last seen {when(s['seen_ts'])} "
            f"({duration(s['age_h'] * 3600)} ago), starts 24 h / 7 d: {s['restarts_24h']} / {s['restarts_7d']}"
        )
    lines += [
        f"{p}: running for inactive experiment {experiment(p)}" for p in c.orphans
    ]
    return "\n".join(lines)


def legend() -> str:
    def item(style, text, cls=""):
        return f'<span><i class="{cls}" style="{style}"></i>{esc(text)}</span>'

    items = [
        item(f"background-color:{COLOUR[k][0]}", f"✓ running, uptime {t}")
        for k, t in (
            ("fresh", "< 1 h"),
            ("young", "1 h – 1 d"),
            ("stable", "1–7 d"),
            ("long-run", "> 7 d"),
        )
    ]
    items += [
        item(f"background-color:{COLOUR[k][0]}", f"{SYMBOL[k]} {k}: last seen {t}")
        for k, t in (
            ("late", "2–6 h"),
            ("stale", "6–24 h"),
            ("down", "1–7 d"),
            ("long down", "> 7 d"),
        )
    ]
    items += [
        item(
            f"background-color:{COLOUR['never'][0]}",
            "– never seen (main container)",
            "never",
        ),
        item("", "not deployed (extra container)"),
        item(
            f"box-shadow:inset 0 0 0 3px {PARTIAL}",
            "partial: some threads not running (count shown)",
        ),
        item(
            f"box-shadow:inset 0 0 0 3px {ORPHAN}",
            "⚠ udpping thread running for an inactive experiment",
        ),
        item("", f"flapping: ≥ {FLAPPING} starts in 24 h", "flap"),
        item("border:1px dashed #444", "TESTING node"),
    ]
    return f'<div class="legend">{"".join(items)}</div>'


def grid(nodes, cells) -> str:
    """Main and extra containers in one grid; a click on a cell opens the side panel (script)."""
    gap = '<td class="gap"></td>'
    rows = []
    for node in nodes.itertuples():
        tds = []
        for container in MAIN + EXTRA:
            c = cells[node.node_id, container]
            bg, fg = colour(c)
            classes = " ".join(
                ["c", c.state.replace(" ", "-")]
                + ["partial"] * c.partial
                + ["flap"] * c.flapping
                + ["orphan"] * bool(c.orphans)
            )
            text = " ".join(filter(None, (SYMBOL[c.state], c.label)))
            tds.append(
                f'<td class="{classes}" data-node="{node.node_id}" data-container="{container}" '
                f'style="background-color:{bg};color:{fg}" '
                f'title="{esc(hover(node, container, c))}">{esc(text)}</td>'
            )
        tds.insert(len(MAIN), gap)
        rows.append(
            f'<tr class="{esc(node.status)}"><th><a href="#node-{node.node_id}">{node.node_id}</a></th>'
            f'<td>{chip(node.status)}</td><td>{esc(blank(node.municipality))}</td>{"".join(tds)}</tr>'
        )
    groups = (
        f'<tr><th colspan="3"></th><th colspan="{len(MAIN)}">main containers</th>{gap}'
        f'<th colspan="{len(EXTRA)}">extra containers</th></tr>'
    )
    head = (
        "".join(f"<th>{c}</th>" for c in MAIN)
        + gap
        + "".join(f"<th>{c}</th>" for c in EXTRA)
    )
    return (
        f'{legend()}<div class="scroll"><table class="grid"><thead>{groups}<tr><th>node</th><th>status</th>'
        f'<th>municipality</th>{head}</tr></thead><tbody>{"".join(rows)}</tbody></table></div>'
    )


def statuses(nodes) -> list:
    present = set(nodes.status)
    return [s for s in STATUS_ORDER if s in present] + sorted(
        present - set(STATUS_ORDER)
    )


def overview(nodes, cells) -> str:
    groups = [
        (chip(s), nodes.node_id[nodes.status == s].tolist()) for s in statuses(nodes)
    ]
    groups.append(("all", nodes.node_id.tolist()))

    def counts(ids):
        ok = sum(
            all(
                cells[n, c].state == "running"
                and not cells[n, c].partial
                and not cells[n, c].orphans
                for c in MAIN
            )
            for n in ids
        )
        idle = sum(not any(running(cells[n, c]) for c in MAIN + EXTRA) for n in ids)
        return len(ids), ok, len(ids) - ok - idle, idle

    by_status = "".join(
        f"<tr><th>{label}</th>{''.join(f'<td>{v}</td>' for v in counts(ids))}</tr>"
        for label, ids in groups
    )
    by_container = "".join(
        f"<tr><th>{c}</th>{''.join(f'<td>{sum(running(cells[n, c]) for n in ids)} / {len(ids)}</td>' for _, ids in groups)}</tr>"
        for c in MAIN + EXTRA
    )
    return (
        f'<div class="scroll"><table><thead><tr><th>status</th><th>nodes</th><th>all main containers OK</th>'
        f"<th>some issue</th><th>nothing running</th></tr></thead><tbody>{by_status}</tbody></table></div>"
        f'<h3>Nodes running each container</h3><div class="scroll"><table><thead><tr><th>container</th>'
        f"{''.join(f'<th>{label}</th>' for label, _ in groups)}</tr></thead><tbody>{by_container}</tbody></table></div>"
    )


def problems(nodes, cells, raw, now) -> str:
    order = {s: i for i, s in enumerate(statuses(nodes))}
    last = raw.groupby("node_id").seen_ts.max()
    found = []
    for node in nodes.itertuples():
        node_issues = [
            i for i in (issue(c, cells[node.node_id, c]) for c in MAIN + EXTRA) if i
        ]
        if node_issues:
            seen = last.get(node.node_id, pd.NaT)
            age = math.inf if pd.isna(seen) else (now - seen).total_seconds()
            found.append(
                (order[node.status], -age, node.node_id, node, node_issues, seen, age)
            )
    found.sort(key=lambda f: f[:3])
    rows = "".join(
        f'<tr><th><a href="#node-{node.node_id}">{node.node_id}</a></th><td>{chip(node.status)}</td>'
        f'<td>{esc("; ".join(node_issues))}</td>'
        f'<td>{"never" if math.isinf(age) else f"{when(seen)} ({duration(age)} ago)"}</td></tr>'
        for *_, node, node_issues, seen, age in found
    )
    return (
        f"<p>{len(found)} of {len(nodes)} nodes not fully OK; DEPLOYED first, then the longest silent.</p>"
        f'<div class="scroll"><table><thead><tr><th>node</th><th>status</th><th>issues</th>'
        f"<th>last heartbeat (UTC)</th></tr></thead><tbody>{rows}</tbody></table></div>"
    )


def timeline(runs, rows, info, orphans, now) -> str:
    """SVG: one row per thread, one bar per run (start_ts → seen_ts), a thin bar from the last heartbeat to now."""
    width, left, row_h, top = 1000, 210, 18, 20
    start, span, bottom = now - WINDOW, WINDOW.total_seconds(), top + row_h * len(rows)

    def x(t):
        return left + min(max((t - start).total_seconds(), 0), span) / span * (
            width - left - 10
        )

    svg = ['<g class="axis-g">']  # redrawn by the script on zoom
    day = start.normalize() + pd.Timedelta(days=1)
    while day <= now:
        svg.append(
            f'<line x1="{x(day):.1f}" x2="{x(day):.1f}" y1="{top - 4}" y2="{bottom}"/>'
            f'<text class="axis" x="{x(day):.1f}" y="{top - 8}" text-anchor="middle">{day:%m-%d}</text>'
        )
        day += pd.Timedelta(days=1)
    svg.append("</g>")
    for i, name in enumerate(rows):
        y, e = top + i * row_h, experiment(name)
        label = f"{name.partition('-')[0]} {experiment_label(e, info)}" if e else name
        cls = ' class="bad"' if name in orphans else ""
        svg.append(
            f'<text{cls} x="{left - 6}" y="{y + 13}" text-anchor="end">{esc(label)}</text>'
        )
        own = runs[runs.process == name].sort_values("start_ts")
        if own.empty:
            svg.append(
                f'<text class="axis" x="{left + 4}" y="{y + 13}">never seen</text>'
            )
            continue
        version = None
        for r in own.itertuples():
            if r.seen_ts >= start:
                x0, x1 = x(r.start_ts), x(r.seen_ts)
                fill = (
                    PROVIDER.get(getattr(info.get(e), "provider", None), "#757575")
                    if e
                    else COLOUR[uptime_class(r.uptime / 3600)][0]
                )
                tip = f"{name}: {when(r.start_ts)} → {when(r.seen_ts)} UTC, up {duration(r.uptime)}, {r.version}"
                exp = f' data-exp="{e}"' if e else ""
                svg.append(
                    f'<rect data-s="{epoch(r.start_ts)}" data-e="{epoch(r.seen_ts)}"{exp} x="{x0:.1f}" '
                    f'y="{y + 3}" width="{max(x1 - x0, 2):.1f}" height="{row_h - 6}" fill="{fill}">'
                    f"<title>{esc(tip)}</title></rect>"
                )
                if version is not None and r.version != version and r.start_ts >= start:
                    svg.append(
                        f'<path data-s="{epoch(r.start_ts)}" transform="translate({x0:.1f},0)" '
                        f'd="M-4,{y} h8 l-4,5 z"><title>{esc(f"version {version} → {r.version}")}</title></path>'
                    )
            version = r.version
        last = own.seen_ts.max()
        age = (now - last).total_seconds()
        state = seen_class(age / 3600)
        if state != "running":
            x0 = x(max(last, start))
            svg.append(
                f'<rect data-s="{epoch(last)}" data-e="{epoch(now)}" x="{x0:.1f}" y="{y + 7}" '
                f'width="{max(x(now) - x0, 2):.1f}" height="4" '
                f'fill="{COLOUR[state][0]}"><title>{esc(f"{name}: {state}, not seen for {duration(age)}")}'
                f"</title></rect>"
            )
    buttons = "".join(
        f'<button data-days="{d}">{d} d</button>' for d in (1, 3, 7, WINDOW.days)
    )
    return (
        f'<div class="zoom">{buttons}<span>drag on the chart to zoom, double-click to reset, click a bar for '
        f'detail</span></div><svg class="tl" viewBox="0 0 {width} {bottom + 4}" width="100%" role="img" '
        f'aria-label="container runs, last {WINDOW.days} days" data-left="{left}" data-right="{width - 10}" '
        f'data-top="{top}" data-bottom="{bottom}" data-now="{epoch(now)}" data-days="{WINDOW.days}">'
        f'{"".join(svg)}</svg><div class="run"></div>'
    )


def thread_table(node_id, container, rows, states, info, orphans) -> str:
    out = []
    for name in rows:
        s, e = states.get((node_id, container, name)), experiment(name)
        exp = experiment_label(e, info) if e else ""
        cls = ' class="bad"' if name in orphans else ""
        if s is None:
            out.append(
                f'<tr><td>{esc(name)}</td><td>{esc(exp)}</td><td colspan="6">never seen</td></tr>'
            )
            continue
        bg, fg = COLOUR[s["up"] if s["seen"] == "running" else s["seen"]]
        state = s["seen"] + (f", {s['up']}" if s["seen"] == "running" else "")
        values = (
            name,
            exp,
            s["version"],
            when(s["start_ts"]),
            duration(s["uptime"]),
            f"{when(s['seen_ts'])} ({duration(s['age_h'] * 3600)} ago)",
        )
        out.append(
            f"<tr{cls}>{''.join(f'<td>{esc(v)}</td>' for v in values)}"
            f'<td style="background-color:{bg};color:{fg}">{esc(state)}</td>'
            f"<td>{s['restarts_24h']} / {s['restarts_7d']}</td></tr>"
        )
    head = "".join(
        f"<th>{h}</th>"
        for h in (
            "thread",
            "experiment",
            "version",
            "started (UTC)",
            "uptime",
            "last seen (UTC)",
            "state",
            "starts 24 h / 7 d",
        )
    )
    return f'<div class="scroll"><table><thead><tr>{head}</tr></thead><tbody>{"".join(out)}</tbody></table></div>'


def experiments_table(node_id, exps, own, states, orphans, now) -> str:
    """Active measurement instances, plus stopped ones that container threads seen in the timeline window refer to."""
    referenced = {experiment(p) for p in own.process[own.seen_ts >= now - WINDOW]} - {
        None
    }
    shown = exps[exps.stop_time.isna() | exps.id.isin(referenced)].sort_values("id")
    if shown.empty:
        return "<p>No active measurement instance.</p>"
    bad = {experiment(p) for p in orphans}
    rows = []
    for e in shown.itertuples():
        threads = ""
        if e.measurement_desc_id == UDPPING:
            seen = [
                (kind, states.get((node_id, "udpping", f"{kind}-{e.id}")))
                for kind in ("sender", "receiver")
            ]
            threads = ", ".join(
                f"{kind} {s['seen'] if s else 'never seen'}" for kind, s in seen
            )
        values = (
            e.id,
            e.measurement_desc_id,
            f"{e.provider} ({e.network_id})",
            "" if pd.isna(e.iccid) else e.iccid,
            when(e.start_time),
            when(e.stop_time) if pd.notna(e.stop_time) else "active",
            threads,
        )
        cls = ' class="bad"' if e.id in bad else ""
        rows.append(
            f'<tr data-exp="{e.id}"{cls}>'
            + "".join(f"<td>{esc(v)}</td>" for v in values)
            + f"<td>{parameters(e.parameters)}</td></tr>"
        )
    head = "".join(
        f"<th>{h}</th>"
        for h in (
            "measurement_instance",
            "measurement_desc",
            "network",
            "iccid",
            "start (UTC)",
            "stop (UTC)",
            "udpping threads",
            "parameters",
        )
    )
    return f'<div class="scroll"><table><thead><tr>{head}</tr></thead><tbody>{"".join(rows)}</tbody></table></div>'


TIMELINE_LEGEND = (
    f'<p class="note">Last {WINDOW.days} days, UTC. Bar = one container run (start → last heartbeat), '
    "green shade = uptime class of the run, udpping sender / receiver in the provider colour; "
    "thin bar after the last heartbeat = last seen class; ▼ = version change. Hover or click a bar for detail.</p>"
)


def node_detail(node, raw, states, cells, experiments, now) -> str:
    node_id = node.node_id
    own = raw[raw.node_id == node_id]
    exps = experiments[experiments.node_id == node_id]
    info = {row.id: row for row in exps.itertuples()}
    active_udpping = sorted(
        exps.id[(exps.measurement_desc_id == UDPPING) & exps.stop_time.isna()]
    )
    containers = [c for c in MAIN + EXTRA if (own.container == c).any()]
    never = [c for c in MAIN if cells[node_id, c].state == "never"]
    place = " ".join(filter(None, (blank(node.zip), blank(node.municipality))))
    address = ", ".join(
        filter(
            None,
            (blank(node.name), blank(node.address), place, blank(node.country_code)),
        )
    )
    facts = [
        address or "no site address",
        f"status since {when(node.valid_from)[:10]}",
        f"{node.interfaces} active interfaces",
        f"{node.experiments} active experiments",
    ]
    if never:
        facts.append("never seen: " + ", ".join(never))
    if "scenario" in node._fields:
        facts.append(f"synthetic scenario: {node.scenario}")
    if containers:
        inputs = "".join(
            f'<input type="radio" name="n{node_id}" id="n{node_id}-{c}"{" checked" * (i == 0)}>'
            for i, c in enumerate(containers)
        )
        labels = "".join(
            f'<label for="n{node_id}-{c}"><i style="background-color:{colour(cells[node_id, c])[0]}">'
            f"</i>{c}</label>"
            for c in containers
        )
        panels = []
        for c in containers:
            runs = own[own.container == c]
            names = list(expected_threads(c, active_udpping))
            rows = names + sorted(
                set(runs.loc[runs.seen_ts >= now - WINDOW, "process"]) - set(names)
            )
            orphans = set(cells[node_id, c].orphans)
            panels.append(
                f'<div data-container="{c}">{timeline(runs, rows, info, orphans, now)}'
                f"{thread_table(node_id, c, rows, states, info, orphans)}</div>"
            )
        body = (
            f'{TIMELINE_LEGEND}<div class="sub">{inputs}{labels}{"".join(panels)}</div>'
        )
    else:
        body = "<p>No container heartbeat for this node.</p>"
    return (
        f'<section class="tab" id="node-{node_id}"><h2>Node {node_id} {chip(node.status)}</h2>'
        f'<p>{esc(" · ".join(facts))} · <a href="#containers">back to grid</a></p>{body}<h3>Experiments</h3>'
        f'{experiments_table(node_id, exps, own, states, cells[node_id, "udpping"].orphans, now)}</section>'
    )


TABS = (
    ("overview", "Overview"),
    ("containers", "Containers"),
    ("problems", "Problems"),
)
DRAWER = (
    '<aside id="drawer" hidden><button class="close" aria-label="close">×</button><h3></h3>'
    '<p class="summary"></p><div class="body scroll"></div><p><button class="open">open node detail</button></p>'
    "</aside>"
)
# Grid cell click → side panel; node detail timelines: range buttons, drag to zoom, double-click reset, bar click detail
SCRIPT = r"""
"use strict";
const NS = "http://www.w3.org/2000/svg", DAY = 86400;
const drawer = document.getElementById("drawer");

document.addEventListener("click", (ev) => {
  const cell = ev.target.closest("td.c");
  if (cell) return openDrawer(cell);
  if (ev.target.closest("#drawer .close")) drawer.hidden = true;
  const open = ev.target.closest("#drawer .open");
  if (open) {
    drawer.hidden = true;
    const radio = document.getElementById(`n${open.dataset.node}-${open.dataset.container}`);
    if (radio) radio.checked = true;
    location.hash = `node-${open.dataset.node}`;
  }
});
document.addEventListener("keydown", (ev) => { if (ev.key === "Escape") drawer.hidden = true; });

function openDrawer(cell) {
  const { node, container } = cell.dataset;
  const table = document.querySelector(`#node-${node} .sub > div[data-container="${container}"] table`);
  drawer.querySelector("h3").textContent = `Node ${node} · ${container}`;
  drawer.querySelector(".summary").textContent = cell.title.split("\n")[0];
  drawer.querySelector(".body").replaceChildren(table ? table.cloneNode(true) : "No heartbeat of this container.");
  Object.assign(drawer.querySelector(".open").dataset, { node, container });
  drawer.hidden = false;
}

function element(name, attributes, text) {
  const el = document.createElementNS(NS, name);
  for (const [key, value] of Object.entries(attributes)) el.setAttribute(key, value);
  if (text) el.textContent = text;
  return el;
}

document.querySelectorAll("svg.tl").forEach((svg) => {
  const d = svg.dataset, left = +d.left, right = +d.right, top = +d.top, bottom = +d.bottom;
  const now = +d.now, full = +d.days * DAY, panel = svg.parentElement, detail = panel.querySelector(".run");
  let from = now - full, to = now, anchor = null;
  const x = (t) => left + (Math.min(Math.max(t, from), to) - from) / (to - from) * (right - left);
  const time = (sx) => from + (sx - left) / (right - left) * (to - from);
  const svgX = (ev) => {
    const r = svg.getBoundingClientRect();
    return (ev.clientX - r.left) * svg.viewBox.baseVal.width / r.width;
  };
  const span = (ev) => [Math.max(Math.min(anchor, svgX(ev)), left), Math.min(Math.max(anchor, svgX(ev)), right)];
  const brush = svg.appendChild(element("rect", { class: "brush", y: top, height: bottom - top, display: "none" }));

  function zoom(a, b) {
    [from, to] = [a, b];
    for (const el of svg.querySelectorAll("[data-s]")) {
      const s = +el.dataset.s, e = "e" in el.dataset ? +el.dataset.e : s;
      const visible = e >= from && s <= to;
      el.setAttribute("display", visible ? "inline" : "none");
      if (!visible) continue;
      if ("e" in el.dataset) {
        el.setAttribute("x", x(s));
        el.setAttribute("width", Math.max(x(e) - x(s), 2));
      } else el.setAttribute("transform", `translate(${x(s)},0)`);
    }
    const axis = svg.querySelector(".axis-g");
    const step = to - from <= 1.5 * DAY ? 3 * 3600 : to - from <= 4 * DAY ? 12 * 3600 : DAY;
    axis.replaceChildren();
    for (let tick = Math.ceil(from / step) * step; tick <= to; tick += step) {
      const iso = new Date(tick * 1000).toISOString();
      axis.append(element("line", { x1: x(tick), x2: x(tick), y1: top - 4, y2: bottom }),
                  element("text", { class: "axis", x: x(tick), y: top - 8, "text-anchor": "middle" },
                          tick % DAY ? iso.slice(11, 16) : iso.slice(5, 10)));
    }
  }

  panel.querySelectorAll(".zoom button").forEach((b) => b.addEventListener("click", () => zoom(now - b.dataset.days * DAY, now)));
  svg.addEventListener("dblclick", () => zoom(now - full, now));
  svg.addEventListener("mousedown", (ev) => {
    if (svgX(ev) >= left) { anchor = svgX(ev); ev.preventDefault(); }
  });
  svg.addEventListener("mousemove", (ev) => {
    if (anchor === null) return;
    const [a, b] = span(ev);
    brush.setAttribute("x", a);
    brush.setAttribute("width", Math.max(b - a, 0));
    brush.setAttribute("display", "inline");
  });
  window.addEventListener("mouseup", (ev) => {
    if (anchor === null) return;
    const [a, b] = span(ev);
    anchor = null;
    brush.setAttribute("display", "none");
    if (b - a > 5) zoom(time(a), time(b));
  });
  svg.addEventListener("click", (ev) => {
    const bar = ev.target.closest("[data-s]");
    if (!bar) return;
    detail.replaceChildren(bar.querySelector("title")?.textContent ?? "");
    const parameters = bar.dataset.exp && panel.closest("section").querySelector(`tr[data-exp="${bar.dataset.exp}"] pre`);
    if (parameters) detail.append(parameters.cloneNode(true));
  });
});
"""
CSS = """
:root{--theme:#f15d22;--sub:#ebecee;--border:#e6e6e6;--muted:#808080}
*{box-sizing:border-box}
body{margin:0;font:14px/1.4 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;color:#000;background:#fff}
header{display:flex;flex-wrap:wrap;gap:.25em 1em;align-items:baseline;padding:12px 16px;border-bottom:3px solid var(--theme)}
header h1{margin:0;font-size:20px}
header span,.note{color:var(--muted)}
nav{display:flex;flex-wrap:wrap;gap:4px;padding:8px 16px;background:var(--sub)}
nav a,.sub>label{padding:6px 12px;border-radius:5px;background:#fff;color:#000;text-decoration:none;border:1px solid var(--border);cursor:pointer}
main{padding:12px 16px}
h2{font-size:18px}h3{font-size:15px;margin-top:1.5em}
.tab{display:none}
.tab:target,body:not(:has(.tab:target)) #overview{display:block}
body:not(:has(.tab:target)) nav a[href="#overview"]{background:var(--theme);color:#fff}
.scroll{overflow-x:auto}
table{border-collapse:separate;border-spacing:2px}
th,td{padding:3px 8px;text-align:left;white-space:nowrap}
thead th{background:var(--sub)}
.grid td.c{min-width:7.5em;text-align:center;border:1px solid transparent;font-variant-numeric:tabular-nums;cursor:pointer}
.grid td.c.none{border-color:var(--border)}
.grid tr.TESTING td.c{border:1px dashed #444}
.never{background-image:repeating-linear-gradient(45deg,transparent 0 4px,rgba(0,0,0,.15) 4px 6px)}
.partial{box-shadow:inset 0 0 0 3px #d39e00}
.orphan{box-shadow:inset 0 0 0 3px #a50f15}
.partial.orphan{box-shadow:inset 0 0 0 3px #d39e00,inset 0 0 0 6px #a50f15}
.bad{color:#a50f15;fill:#a50f15;font-weight:600}
details summary{cursor:pointer;color:var(--muted)}
pre{margin:4px 0;font-size:12px;white-space:pre-wrap}
.grid .gap{width:10px;padding:0;background:none}
button{font:inherit;padding:3px 10px;border:1px solid var(--border);border-radius:5px;background:#fff;cursor:pointer}
.zoom{display:flex;flex-wrap:wrap;gap:4px;align-items:center;margin:6px 0}
.zoom span{color:var(--muted);font-size:12px}
.run{white-space:pre-wrap;font-size:12px;margin:4px 0 8px}
.tl{user-select:none}
.tl .brush{fill:rgba(241,93,34,.15);stroke:#f15d22}
#drawer{position:fixed;top:0;right:0;bottom:0;width:min(680px,100vw);overflow:auto;background:#fff;border-left:3px solid var(--theme);box-shadow:-4px 0 12px rgba(0,0,0,.15);padding:12px 16px;z-index:10}
#drawer[hidden]{display:none}
#drawer .close{float:right;font-size:18px}
.flap{position:relative}
.flap::after{content:"";position:absolute;top:3px;right:3px;width:7px;height:7px;border-radius:50%;background:#fff;border:1px solid #000}
.chip{display:inline-block;padding:1px 8px;border-radius:9px;color:#fff;font-size:12px}
.legend{display:flex;flex-wrap:wrap;gap:6px 14px;margin:8px 0 12px;font-size:12px}
.legend i{display:inline-block;width:16px;height:16px;vertical-align:-4px;margin-right:5px;border:1px solid var(--border)}
.sub>input,.sub>div{display:none}
.sub>label{display:inline-block;margin:0 4px 4px 0}
.sub>label i{display:inline-block;width:10px;height:10px;margin-right:6px;border:1px solid var(--border)}
.sub>div{margin-top:8px}
.tl{display:block;max-width:1100px}
.tl text{font-size:11px}
.tl .axis{fill:var(--muted)}
.tl line{stroke:#ccc;stroke-dasharray:3 3}
"""


def render(nodes, experiments, raw, now, source: str) -> str:
    order = {s: i for i, s in enumerate(STATUS_ORDER)}
    nodes = nodes.assign(rank=nodes.status.map(order).fillna(len(order))).sort_values(
        ["rank", "node_id"]
    )
    states, cells = summarise(nodes, experiments, raw, now)
    bodies = {
        "overview": overview(nodes, cells),
        "containers": grid(nodes, cells),
        "problems": problems(nodes, cells, raw, now),
    }
    nav = "".join(f'<a href="#{tab}">{title}</a>' for tab, title in TABS)
    sections = "".join(
        f'<section class="tab" id="{tab}"><h2>{title}</h2>{bodies[tab]}</section>'
        for tab, title in TABS
    )
    details = "".join(
        node_detail(node, raw, states, cells, experiments, now)
        for node in nodes.itertuples()
    )
    css = CSS + "".join(
        f'body:has(#{tab}:target) nav a[href="#{tab}"]{{background:var(--theme);color:#fff}}\n'
        for tab, _ in TABS
    )
    css += "".join(
        f".sub>input:nth-of-type({k}):checked~div:nth-of-type({k}){{display:block}}\n"
        f".sub>input:nth-of-type({k}):checked~label:nth-of-type({k}){{background:var(--theme);color:#fff}}\n"
        for k in range(1, len(MAIN + EXTRA) + 1)
    )
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Container status</title>
<style>{css}</style>
</head>
<body>
<header><h1>Container status</h1><span>{esc(source)} · {len(nodes)} nodes · generated {when(now)} UTC</span></header>
<nav>{nav}</nav>
<main>{sections}{details}</main>
{DRAWER}
<script>{SCRIPT}</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Render the container status page as one static HTML file."
    )
    parser.add_argument("output", type=Path, help="HTML file to write")
    parser.add_argument(
        "--synthetic",
        action="store_true",
        help="synthetic data covering every colour combination",
    )
    args = parser.parse_args()
    if not args.synthetic:
        parser.error(
            "only --synthetic is implemented so far (database loader: phase 2)"
        )
    now = pd.Timestamp.now("UTC").tz_localize(None).floor("min")
    args.output.write_text(
        render(*synthetic(now), now, "synthetic data"), encoding="utf-8"
    )
    print(f"written {args.output}")


if __name__ == "__main__":
    main()
