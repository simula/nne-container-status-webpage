# NNE container status webpage – design

A web application (Dash) that shows, for every reported NNE node, whether its docker containers and their threads are
running. The data are the container heartbeats that
[nne-container-status-importer](https://github.com/simula/nne-container-status-importer) imports into
`report.container_rawdata`, checked against the experiment setup in the `nne` database.

| Phase | Content | State |
|---|---|---|
| 1 | Prototype: static HTML generator, interaction, colour rules on synthetic data (local) | done |
| 2 | Skeleton webpage resembling nne-viz: header navigation (Containers, Plots), placeholder sub-tabs on the Containers page (Overview, Grid, Problems, Node detail) in the nne-viz TabButton style, code conventions (section 13), Docker for development | done |
| 3 | Container dashboard in Dash (AG Grid, Plotly) on synthetic data | next |
| 4 | Database loader through nnedbtools (read-only), cache | |
| 5 | nginx / TLS, set up from scratch | before deployment |
| 6 | Deployment on oculus: venv and systemd service, as nne-container-status-importer (section 11) | later |

The static HTML prototype of phase 1 (`prototype/`) settled the rules of sections 4–6 and the page ideas of sections 7–8;
it is removed at the end of phase 3.

Figures quoted below were measured on 2026-11-06.

## 1. Scope
- A Dash application (Dash Pages, dash-ag-grid, Plotly) in the look of nne-viz, served by gunicorn behind nginx / TLS
  on oculus (section 11).
- Pages: **Containers**, the container status dashboard (sections 7–8); **Plots**, the plots now rendered in the
  nne-report and nne-exploratory notebooks, added later page by page.
- Live data, read-only: through nnedbtools with the nne-reader account, nothing is written to `nne` or `report`;
  loaded data are cached for a few minutes (section 10).
- Python only, apart from client-side callbacks where a request to the server makes no sense (the clock).
- The timeline shows the last 14 days; the table keeps more.
- Not part of nne-viz (React, TypeScript): a separate project that shares its look (colours, logos, page frame).

## 2. Data sources

| Table | Used for |
|---|---|
| `report.container_rawdata` | heartbeat runs, see below |
| `nne.node_info` | active interface: `valid_to IS NULL` |
| `nne.measurement_instance` | active experiment: `stop_time IS NULL`; udpping instances: `measurement_desc_id = 1`; `parameters` (JSON string, up to 4000 characters) |
| `nne.node_status`, `nne.status` | status group of the node |
| `nne.node_address`, `nne.address` | site address, `municipality` optional |

`report.container_rawdata`:

- Key `(node_id, start_ts, container, version, process)`; one row per container run and process (thread).
  The importer updates `seen_ts` and `uptime` of the row while the run lasts; a restart creates a new row.
- Heartbeats arrive about hourly; most `seen_ts` values are on the full hour.
- `uptime` equals `seen_ts − start_ts` within seconds; `extra` is always empty.
- Not partitioned, about 13,000 rows, no index on `seen_ts`: read in one statement (`SELECT *`).
- Data quality seen: a few rows with node clock errors (`start_ts` 2011-11-11), version `--`.

`nne.node_status` holds one row per node (no interval semantics); the nimbus sync (`nnedbtools.batch.node_status`)
maintains it.

Not used: the view `nne.v_node_status` (nne-viz map). On 2026-11-06 it returned `UNREACHABLE` or no row for every
active node: not maintained.

## 3. Reported nodes

A node is reported when all of these hold:

1. at least one active interface (`nne.node_info`),
2. at least one active experiment (`nne.measurement_instance`),
3. `node_id >= 3100` (older nodes are not reported),
4. `nne.node_status` is DEPLOYED or TESTING (all other statuses, and nodes without a status record, are excluded).

On 2026-11-06: DEPLOYED 100, TESTING 16. Missing status records found on the way were fixed in `nne.node_status`:
11085 DESTROYED (from 2026-11-06), 10964 and 11165 TESTING (from 2026-09-01).

## 4. Containers and threads

| Container | Group | Expected threads (`process`) | Version line |
|---|---|---|---|
| metadata | main | `homekeeping`, `metadata` | `geo-*` |
| mqtt | main | `container`, `mqtt` | `locum-*` |
| speedtest | main | `container` | `dendro-*` |
| udpping | main | `container`, plus `sender-<N>` and `receiver-<N>` per active udpping instance `N` | `electro-*` |
| traceroute | extra | `container` | `chrono-*` |
| netperfmeter | extra | `container` | `cryo-*` |
| hipercontracer | extra | `container` (assumed, not in the data yet) | – |

`homekeeping` is a thread of the `metadata` container, not a container of its own. A typical node runs two udpping
experiments, so two sender and two receiver threads.

### Crosscheck with the experiment setup

`N` in `sender-<N>` / `receiver-<N>` is `nne.measurement_instance.id`. The expected udpping threads of a node are
derived from its active udpping instances:

- an active instance without a running sender or receiver makes the cell **partial**;
- a sender or receiver that is still running while `N` is not an active udpping instance of that node (stopped,
  belonging to another node, or unknown) is an **orphan** and counts as a problem.

On 2026-11-06 all 432 running sender/receiver threads belonged to active udpping instances of the same node.

## 5. Classification

Reference time is the generation time (UTC). Each thread is classified by its latest row.

| Last seen class | Time since last heartbeat |
|---|---|
| running | ≤ 2 h |
| late | 2–6 h |
| stale | 6–24 h |
| down | 1–7 d |
| long down | > 7 d |
| never | no row |

| Uptime class (running threads) | Uptime |
|---|---|
| fresh | < 1 h |
| young | 1 h – 1 d |
| stable | 1–7 d |
| long-run | > 7 d |

Starts in 24 h / 7 d are the distinct `start_ts` values in that period; **flapping** means 3 or more starts in 24 h.

A grid cell is one node and one container:

- **state**: worst last seen class among the expected threads that have rows
  (running < late < stale < down < long down);
- **never** when no expected thread has a row (main container); **not deployed** for an extra container without rows;
- **shade**: uptime class of the freshest running thread;
- **partial**: some, but not all, expected threads running; label `k/n`, for udpping `S a/n R b/n`;
- **flapping**: any thread flapping;
- **orphans**: see the crosscheck; label `⚠+k`.

Per node (Overview tab): *all main OK* = every main cell running, not partial, without orphans; *nothing running* =
no cell has a running thread; *some issue* = the rest.

A node is listed on the Problems tab when a cell is not running (except not deployed), partial, flapping or has
orphans; DEPLOYED first, then the longest silent.

## 6. Colour rules

Colours follow nne-viz (`web/src/constants/colors.tsx`). Every state also has a symbol or text, so the grid does not
depend on colour alone.

| Class | Background | Symbol |
|---|---|---|
| running, fresh | `#bfddd3` | ✓ |
| running, young | `#80bca8` | ✓ |
| running, stable | `#409a7c` | ✓ |
| running, long-run | `#007850` | ✓ |
| late | `#efc94d` | ! |
| stale | `#e16437` | ! |
| down | `#e13737` | × |
| long down | `#a50f15` | × |
| never (main) | `#dddddd`, hatched | – |
| not deployed (extra) | white | |

| Marker | Look |
|---|---|
| partial | amber inner border `#d39e00` |
| orphan | dark red inner border `#a50f15`, `⚠+k` |
| flapping | white dot in the corner |
| TESTING node | dashed cell border |
| status chips | DEPLOYED `#1f3a93`, TESTING `#7b3fb5` |
| theme (header line, active tab) | `#f15d22` |
| udpping bars in the timeline | provider colour (Telenor `#19aaf8`, Telia `#9308db`, ICE `#ffb900`, …) |

## 7. Page structure
**Page frame** (every page, as nne-viz): header with the NorNet logo (link to nntb.no), "NorNet edge", one navigation
button per page and the Norway clock; the page; orange footer with the SimulaMet logo. Pages: Containers (`/`),
Plots (`/plots`).

**Containers page**: the time of the last data load, then sub-tabs in the nne-viz TabButton style.

| Sub-tab | Content |
|---|---|
| Overview | per status (DEPLOYED, TESTING, all): nodes, *all main OK*, *some issue*, *nothing running*; per container the nodes running it, per status |
| Grid | AG Grid, one row per node (DEPLOYED then TESTING, by `node_id`): node, status, municipality, then the main and the extra containers as column groups. A container cell shows the symbol and label of its state (section 5) and is coloured by the rules of section 6 (AG Grid cell style conditions built from the palette, section 9); its tooltip lists every thread (state, version, uptime, last seen, starts). Sorting and filters per column. Click on a cell: Node detail of that node and container |
| Problems | AG Grid, one row per node that is not fully OK: node, status, municipality, issues, last heartbeat; DEPLOYED first, then the longest silent. Click on a row: Node detail of that node |
| Node detail | see below |

**Node detail**:

- Node selector (searchable list of the reported nodes) and container selector; both are also in the URL
  (`/?node=<id>&container=<name>`), so the view of a node can be linked.
- Header: site address, status since, active interfaces and experiments, main containers never seen.
- Timeline (Plotly): one row per thread, one bar per run from `start_ts` to `seen_ts`; green shade by the uptime class
  of the run, udpping sender / receiver in the provider colour of their experiment, a thin bar from the last
  heartbeat to now in the last seen colour, a marker at a version change, orphan rows in dark red. Range buttons
  1 / 3 / 7 / 14 d, zoom and pan, hover with start, last seen, uptime and version. Click on a bar: the run detail
  below the timeline, for udpping with the parameters of the experiment.
- Threads (AG Grid): thread, experiment, version, started, uptime, last seen, state, starts in 24 h / 7 d.
- Experiments (AG Grid): the active measurement instances and the stopped ones that threads seen in the window refer
  to: id, `measurement_desc_id`, network, iccid, start, stop, udpping thread states. Click on a row: its `parameters`
  as pretty-printed JSON below the table.

**Plots page**: one section per plot from the notebooks; a matplotlib figure of nnedbtools is shown as an image
first and rewritten in Plotly when it needs interaction.

## 8. Interaction
Dash server callbacks and the built-in interaction of AG Grid and Plotly; no hand-written JavaScript apart from the
clock.

| Action | Result |
|---|---|
| Header button | the page (Dash Pages) |
| Sub-tab | the content of the sub-tab |
| Grid cell click (`cellClicked`) | Node detail of that node and container, URL updated |
| Problems row click | Node detail of that node |
| Node or container selector | Node detail redrawn, URL updated |
| Timeline range button, zoom, pan | Plotly: range changed; double click resets |
| Timeline bar click (`clickData`) | the run detail below the timeline, udpping with the experiment parameters |
| Experiments row click | the `parameters` of the instance below the table |
| Hover on a grid cell or timeline bar | tooltip or hover label with the detail |

The page shows when its data were loaded; every page load uses the cached data until their time-to-live ends
(section 10).

## 9. Code structure
Package `src/container_status_webpage` (layout in `documentation/DEVELOPMENT.md`); modules added in phase 3 or 4
are marked.

| Module | Content |
|---|---|
| `app.py` | Dash app, `server` for gunicorn, development server |
| `settings.py` | environment variables `DEBUG`, `DB_ENV_FILE`; from phase 3 `DATA_SOURCE` (`synthetic` or `database`) and `CACHE_TTL` |
| `data/status.py` (3) | the rules of sections 4–6 ported from the prototype: thread states, cells, crosscheck, overview, problems; pandas only, no Dash |
| `data/synthetic.py` (3) | synthetic data with the scenarios of the prototype |
| `data/cache.py` (3) | the frames of the selected source with their load time, kept per process for `CACHE_TTL` |
| `data/loader.py` (4) | the frames from the database through nnedbtools, read-only (section 10) |
| `components/frame.py`, `components/tabs.py` | page frame and sub-tabs |
| `components/palette.py` (3) | the colours of section 6 as Python constants for the grid and the timeline; the colours of the page frame stay in `assets/style.css` |
| `components/grid.py` (3) | AG Grid column definitions, cell style conditions and tooltips of the Grid and Problems sub-tabs |
| `components/timeline.py` (3) | Plotly timeline figure of one node and container |
| `pages/containers.py` | layout and callbacks of the Containers page |
| `pages/plots.py` | Plots page |

Input contract: the synthetic data and the loader produce the same three frames.

| Frame | Columns |
|---|---|
| `nodes` | `node_id`, `status`, `valid_from`, `interfaces`, `experiments`, `name`, `address`, `zip`, `municipality`, `country_code` |
| `experiments` | `id`, `node_id`, `network_id`, `provider`, `measurement_desc_id`, `iccid`, `start_time`, `stop_time`, `parameters` |
| `raw` | the columns of `report.container_rawdata` |

Synthetic data: 18 scenarios × DEPLOYED / TESTING = 36 nodes with ids from 90001: all long-run, fresh restart, young,
stable, late, stale, down, long down, never, udpping partial, thread missing, thread down, flapping, version change,
extra containers, nothing running, no data, inactive experiment. The target container of a scenario rotates over the
main containers; experiments carry made-up parameters; some nodes have no municipality.

Tests without a browser: the rule checks of the prototype (class boundaries, flapping, worst thread / partial /
orphan, synthetic coverage) on `data/status.py`; the grid columns and the timeline figure as built objects; page
callbacks called as functions; the smoke tests of the skeleton. The prototype (`prototype/`) is removed at the end of
phase 3.

## 10. Data loading and cache (phase 4)
`data/loader.py` returns the three frames, read-only through nnedbtools:

- `nodes`: the filter of section 3 (`nne.node_info`, `nne.measurement_instance`, `nne.node_status` / `nne.status`)
  and the site address from `nnedbtools.queries.address.select_from_nne_node_adreess_and_nne_addresss(node_ids)`,
  keeping `address_type` site with `valid_to IS NULL`;
- `experiments`: `nne.measurement_instance` rows of those nodes (active, plus the ones udpping threads refer to), with
  the provider name of `network_id`;
- `raw`: `SELECT * FROM report.container_rawdata`.

Credentials: the nnedbtools env file of the nne-reader account (`DB_ENV_FILE`, read access to `nne` and `report`),
loaded with `nnedbtools.identityprovider.load_from_enviroment`. Development reads go through the nnedbtools test
harness (read-only guards). The first real run is compared with the figures in this document.

`data/cache.py` keeps the frames with their load time in each gunicorn worker for `CACHE_TTL` (default 5 minutes; the
importer writes at minute 10 and 40 of every hour). `DATA_SOURCE=synthetic` serves the synthetic data without a
database, for development and tests.

## 11. Deployment on oculus (phase 6)

As the batch nne-container-status-importer on the same host (its `documentation/INSTALLATION.md`): a virtual
environment with the project, run by systemd. Docker is only for local development.

- Checkout `/nne/nne-container-status-webpage`, virtual environment `.venv` with the project (`pip install .`);
  nnedbtools from its release tag over SSH, as for the importer.
- systemd service `deploy/nne-container-status-webpage.service` under the service user of the importer: runs
  `gunicorn container_status_webpage.app:server` bound to localhost, restarted on failure, logs in the journal.
- Settings as environment variables of the unit; `DB_ENV_FILE` points to the nne-reader env file outside the
  repository (e.g. `~/.config/nne-container-status-webpage/`).
- nginx with TLS in front (phase 5), set up from scratch; access control is decided there.
- `deploy/` and `documentation/INSTALLATION.md` are written in this phase.

## 12. Open points

- `hipercontracer` is not in the data yet; its thread names are assumed (`container`).
- `measurement_desc_id` names: only udpping (1) is known.
- Network → provider mapping for the colours (nne-viz provider names).
- The real `parameters` format (the synthetic JSON is made up).
- Nodes without a `nne.node_status` record drop out of the report silently; the nimbus sync may overwrite records
  fixed by hand.
- Thresholds (2 h, 6 h, 24 h, 7 d; 1 h, 1 d, 7 d; 3 starts) are constants to calibrate after real use.
- Cache per gunicorn worker: with 2 workers the data are loaded twice per time-to-live; a shared cache only if the load
  turns out heavy.
- Timeline with real data: about 13,000 runs in the table, far fewer per node and 14 days.

## 13. Code conventions

The Python code follows nnedbtools (its `documentation/DEVELOPMENT.md` and `.pylintrc`).

- **Module header**: every module starts with the nnedbtools header block, adapted to this project:

  ```python
  #!/usr/bin/python3
  # -*- coding: utf-8 -*-
  # =================================================================
  #
  #   <project banner in the nnedbtools ASCII-art style (figlet)>
  #
  #         ---   The NorNet Edge  Container Status Webpage   ---
  #                    https://www.nntb.no
  # =================================================================
  #
  # <one line: what the module is for>
  #
  # Copyright (C) 2026 by Simulamet CRNA research team
  #
  # <GNU General Public License v3 notice, word for word as in nnedbtools>
  #
  # Contact: crna-eng@simula.no

  """
  <Purpose of the module.>

  Integrations:
      <databases, services, files the module reads>

  Sample code:
  <how the module is used or run>
  """
  ```

- **Imports**: three groups – standard library, third party, nnedbtools and local modules – sorted with `isort`;
  nnedbtools modules under the nnedbtools aliases (`import nnedbtools.connection as con`,
  `import nnedbtools.tables as tb`).
- **Constants**: module level, upper case, with a type annotation (`UNDEFINED_NODE_STATUS: int = -1`).
- **Docstrings**: Google style with `Args:`, `Returns:`, `Raises:`, an example for public functions; raw strings
  when a docstring contains a backslash.
- **Step comments** inside functions as in nnedbtools: lettered phases, numbered steps, lettered sub-steps
  (`# A. Normalize input`, `# 1. Check if node exists`, `# a. Shorthand for nne.node table`); short aliases for
  ORM tables (`mi = tb.NneMeasurementInstance`).
- **Type annotations** on parameters, return values and locals whose type is not obvious, as in nnedbtools.
- **Database access** only through nnedbtools and read-only: select builders from `nnedbtools.queries` where they
  exist, new selects as SQLAlchemy `select` in the same style, engines from `nnedbtools.connection`.
- **Logging** with `logging`, no `print` in the application.
- **JavaScript** only where Dash needs it (client-side callbacks), short and commented the same way.
- **Formatting and linting** as nnedbtools: `black .`, `isort .`, `pylint --rcfile .pylintrc .` with a copy of the
  nnedbtools `.pylintrc` (maximum line length 100).
- **Branches** `feat/{feature}` and `fix/{fix}`, merged through pull requests on
  https://github.com/simula/nne-container-status-webpage.
