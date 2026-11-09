# NNE container status webpage – design

A web application (Dash) that shows, for every reported NNE node, whether its docker containers and their threads are
running. The data are the container heartbeats that
[nne-container-status-importer](https://github.com/simula/nne-container-status-importer) imports into
`report.container_rawdata`, checked against the experiment setup in the `nne` database.

| Phase | Content | State |
|---|---|---|
| 1 | Prototype: static HTML generator, interaction, colour rules on synthetic data (local) | done |
| 2 | Skeleton webpage resembling nne-viz: header navigation (Containers, Plots), placeholder sub-tabs on the Containers page (Overview, Grid, Problems, Node detail) in the nne-viz TabButton style, code conventions (section 13), Docker for development | done |
| 3 | Container dashboard in Dash (AG Grid, Plotly) on synthetic data | done |
| 4 | Database loader through nnedbtools (read-only), cache; expected containers from the node configuration map, names and colours from the nnedbtools enums (sections 4, 9, 10) | next |
| 5 | nginx / TLS, set up from scratch | before deployment |
| 6 | Deployment on oculus: venv and systemd service, as nne-container-status-importer (section 11) | later |

Figures quoted below were measured on 2026-11-06.

## 1. Scope
- A Dash application (Dash Pages, dash-ag-grid, Plotly) in the look of nne-viz, served by gunicorn behind nginx / TLS
  on oculus (section 11).
- Pages: **Containers**, the container status dashboard (sections 7–8); **Plots**, the plots now rendered in the
  nne-report and nne-exploratory notebooks, added later page by page.
- Live data, read-only: through nnedbtools with the nne-reader account, nothing is written to `nne` or `report`;
  loaded data are cached for a few minutes (section 10).
- Python only, apart from client-side callbacks where a request to the server makes no sense (the clock).
- The timeline opens on the last 7 days; All shows the whole history of the table.
- Not part of nne-viz (React, TypeScript): a separate project that shares its look (colours, logos, page frame).

## 2. Data sources

| Table | Used for |
|---|---|
| `report.container_rawdata` | heartbeat runs, see below |
| `nne.node_info` | active interface: `valid_to IS NULL` |
| `nne.measurement_instance` | active experiment: `stop_time IS NULL`; `measurement_desc_id` (expected containers, section 4; udpping instances: 1), `network_id`, `service_id`; `parameters` (JSON string, up to 4000 characters) |
| `nne.node_status`, `nne.status` | status group of the node |
| `nne.node_address`, `nne.address` | site address, `municipality` optional |
| nnedbtools enums, no table | container of a `measurement_desc_id` (`batch.node_config.SupportedExperimentMapper`), network and service names and colours (`enums.enum_mapper`), container names (`enums.DockerContainer`) |

`report.container_rawdata`:

- Key `(node_id, start_ts, container, version, process)`; one row per container run and process (thread).
  The importer updates `seen_ts` and `uptime` of the row while the run lasts; a restart creates a new row.
- Heartbeats arrive about hourly; most `seen_ts` values are on the full hour.
- `uptime` equals `seen_ts − start_ts` within seconds; `extra` holds an integer on `receiver-*` threads only (354 of
  4098 rows of nodes 7042, 7045, 7056, 4120, 4124 on 2026-11-09), otherwise empty.
- Not partitioned, about 13,000 rows, no index on `seen_ts`: read in one statement (`SELECT *`).
- Data quality seen: a few rows with node clock errors (`start_ts` 2011-11-11), version `--`.

`nne.node_status` holds one row per node (no interval semantics); the nimbus sync (`nnedbtools.batch.node_status`)
maintains it.

Not used: the view `nne.v_node_status` (nne-viz map). On 2026-11-06 it returned `UNREACHABLE` or no row for every
active node: not maintained.

## 3. Reported nodes

A node is reported when all of these hold:

1. at least one active interface: `nne.node_info` with `valid_to IS NULL` and `service_id <> 7` (service 7, M2M, is
   the SIM of the power switch, not used for measurements),
2. at least one active experiment bound to a network and a service: `nne.measurement_instance` with
   `stop_time IS NULL`, `network_id <> 0` and `service_id <> 0`,
3. `node_id >= 3100` (older nodes are not reported),
4. `nne.node_status` is DEPLOYED or TESTING (all other statuses, and nodes without a status record, are excluded).

Exception: the satellite nodes **4071, 4072, 4073** are reported as DEPLOYED although nne has no `node`, `node_info`
or `node_status` row for them (hardcoded, `data/status.py` `SATELLITE_NODES`). They run neither the metadata nor
the mqtt container: both are never expected there, and their experiment count has no +1 for metadata. Satellite measurements on other nodes are ad hoc and follow
the rules above.

On 2026-11-06: DEPLOYED 100, TESTING 16, unchanged with the conditions above on 2026-11-09. Missing status records
found on the way were fixed in `nne.node_status`: 11085 DESTROYED (from 2026-11-06), 10964 and 11165 TESTING (from
2026-09-01). On 2026-11-09 ten nodes ≥ 3100 had no status record (3100, 3178, 4071–4073, 4157, 8000, 9000, 9001,
11447); none of them has an active interface, so none drops out only for the missing record. `nne.node_status` is
synchronised manually.

## 4. Containers and threads

| Container | Shown as | Group | Configured by `measurement_desc_id` | Expected threads (`process`) | Version line |
|---|---|---|---|---|---|
| metadata | Metadata | main | always (0) | `homekeeping`, `metadata` | `geo-*` |
| mqtt | MQTT | main | 26 | `container`, `mqtt` | `locum-*` |
| speedtest | Speedtest | main | 16, 17, 18, 19, 23 | `container` | `dendro-*` |
| udpping | UDP Ping | main | 1 | `container`, plus `sender-<N>` and `receiver-<N>` per active udpping instance `N` | `electro-*` |
| traceroute | Traceroute | extra | 27 | `container` | `chrono-*` |
| netperfmeter | NetPerfMeter | extra | 24 | `container` | `cryo-*` |

A node **expects** the metadata container and the container of every active measurement instance, by the map of the
node configuration generator (`nnedbtools.batch.node_config.SupportedExperimentMapper.CONTAINER_NAME_MAP`); the satellite nodes expect neither
metadata nor mqtt (section 3). QUIC
(25, `quic`) is not a standard container and is not shown. The group (main, extra) only orders the columns.

`homekeeping` is a thread of the `metadata` container, not a container of its own. A typical node runs two udpping
experiments, so two sender and two receiver threads.

### Crosscheck with the experiment setup

`N` in `sender-<N>` / `receiver-<N>` is `nne.measurement_instance.id`. The expected udpping threads of a node are
derived from its active udpping instances:

- an active instance without a running sender or receiver makes the cell **partial**;
- a sender or receiver that is still running while `N` is not an active udpping instance of that node (stopped,
  belonging to another node, or unknown) is an **orphan** and counts as a problem;
- a container that is alive (a running thread) while the node has no active instance configuring it (section 4) is an
  **orphan container** and counts as a problem; metadata is always configured.

The key point is the match between the settings in the database and the deployed experiments.

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

`report.container_rawdata` holds one row per run: `start_ts` and the last heartbeat `seen_ts` (on the full hour). More
than 1 h between the last heartbeat of a run and the next start means the thread was **down** in between; a shorter gap
is a restart (studied on nodes 7042, 7045, 7056, 4120, 4124 on 2026-11-09).

A grid cell is one node and one container:

- **state**: worst last seen class among the expected threads that have rows
  (running < late < stale < down < long down);
- **never** when the node expects the container (section 4) and no expected thread has a row, main or extra alike;
  **not configured** (empty cell) for a container the node does not expect;
- **shade**: uptime class of the freshest running thread;
- **partial**: some, but not all, expected threads running; label `k/n`, for udpping `S a/n R b/n`;
- **flapping**: any thread flapping;
- **orphans**: see the crosscheck; label `⚠+k`;
- **orphan container**: the cell keeps the state of its threads with the orphan marker; issue "<container>: running
  without a configured instance";
- **receiver restarts** (warning): `extra` of a `receiver-*` row counts the internal restarts of the udpping receiver
  after an error during the container run (reset when the container restarts). Rate = `extra / (seen_ts −
  start_ts)`, the run counted as at least 1 h. Warning above 60 restarts per hour, or above 1440 per day (the same rate) when the run
  has lasted 7 days or longer. Chosen on 2026-11-09 from the rates of 233 receivers of 115 nodes: median 0.2 per hour,
  90th percentile 53, 95th 289; 60 per hour flagged 12 nodes, 1 / 1 had flagged 89 of 119 nodes, 10 / 10 still 50. The cell state stays; label `↻`; issue "UDP Ping: receiver-<N> restarts <rate>".
  On 2026-11-09: 7056 about 480 per hour, 4120 `receiver-10376` 8 per day over 743 h, the mobile nodes 26–108 in the
  first hour.

Per node (Overview tab): *all main OK* = every main cell running, not partial, without orphans or warnings; *nothing
running* = no cell has a running thread; *some issue* = the rest.

A node is listed on the Problems tab when a cell is not running (except not configured), partial, flapping, has
orphans or a receiver restart warning; DEPLOYED first, then the longest silent. Mobile nodes follow these rules too:
nne has nothing that marks a node as mobile, and a hardcoded list cannot be maintained.

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
| never (expected, no rows) | `#dddddd`, hatched | – |
| not configured | white | |

| Marker | Look |
|---|---|
| partial | amber inner border `#d39e00` |
| receiver restart warning | amber dot, `↻` in the label |
| orphan thread / orphan container | dark red inner border `#a50f15`, `⚠+k` / `⚠` |
| flapping | white dot in the corner |
| TESTING node | dashed cell border |
| status chips | DEPLOYED `#1f3a93`, TESTING `#7b3fb5` |
| theme (header line, active tab) | `#f15d22` |
| network chips (node header) | one chip per network and service: `display_name` (`Telenor:5G`) and `color` of the nnedbtools service decorator `enum_mapper.map_network_service_to_plot_attributes_dataframe`; network 0 (dummy, no interface) without chip |
| timeline: run / silence to now | uptime class of the run / last seen class, as the grid |
| timeline: down period | down colour at 40 % |
| timeline: version change | dark diamond |

## 7. Page structure
**Page frame** (every page, as nne-viz): header with the NorNet logo (link to nntb.no), "NorNet is on the Edge", one
navigation button per page and the Norway clock; the page; orange footer with the SimulaMet logo on a light
background. Pages: Containers (`/`), Plots (`/plots`). Pages have no title of their own: the selected header button
and sub-tab name the view.

**Containers page**: the time of the last data load, then sub-tabs in the nne-viz TabButton style.

| Sub-tab | Content |
|---|---|
| Overview | per status (Deployed, Testing, All): nodes, *all main OK*, *some issue*, *nothing running*; "Running containers by node status": per container the nodes running it / the nodes, per status |
| Grid | AG Grid, one row per node (Deployed then Testing, by `node_id`): node, status, municipality, then the main and the extra containers as column groups. A container cell shows the symbol and label of its state (section 5) and is coloured by the rules of section 6 (AG Grid cell style conditions built from the palette, section 9); its tooltip is a table of the threads (state on its colour, version, up, last seen, ago, starts 24 h / 7 d; never-seen and orphan rows). Toolbar: Status, State (a node matches when any cell has a chosen state or marker), Node and Municipality (multi-select with search). Sorting per column. Click on a row: Node detail of that node, on a container cell also of that container |
| Problems | AG Grid, one row per node that is not fully OK: node, status, municipality, issues, last heartbeat (sortable, never first); Deployed first, then the longest silent. Toolbar: Status, Issues (text, case-insensitive), Node, Municipality. Click on a row: Node detail of that node |
| Node detail | see below |

Display names: container names Metadata, MQTT, Speedtest, UDP Ping, Traceroute, NetPerfMeter; status Deployed /
Testing; headers in sentence case. The data keep the database values.

**Node detail** (all containers of a node in one view: a node-wide outage or a release shows across all rows):

- Node selector (searchable) and range buttons 1 / 3 / 7 / 14 d and All (7 d first). The URL
  `/?tab=node&node=<id>&container=<name>` opens the view; `container` highlights the rows of that container.
- Header: node, status chip, municipality (never the street address: the nodes are not doxed), network chips of the
  active experiments (section 6), the number of active interfaces (`service_id <> 7`) and of experiments (active
  instances + 1 for metadata, which is always configured). No "status since": `nne.node_status.valid_from` is not
  reliable.
- Timeline (Plotly): one row per expected thread of every deployed container (main first), then the orphans (dark red,
  ⚠) and the never-seen threads ("(never)"). Bars: a run from `start_ts` to `seen_ts` in the uptime class of its
  length (a white edge separates restarts), a down period where the next start is more than 1 h after the last
  heartbeat, the silence from the last heartbeat to now in its last seen colour; a diamond at the start of a run with
  another version than the run before (hover: old → new). Hover boxes are white. Click on a bar: thread, segment,
  from, to, length, version, gap before and after below the timeline.
- Threads (AG Grid), in the order of the timeline: container, thread, state on its colour, version, up, last seen,
  ago, starts in 24 h / 7 d, receiver restarts (`314,076 (480/h)`, receivers only; also in the Grid tooltip).
- Experiments (AG Grid): the measurement instances of the node, active first, stopped ones in grey: id, measurement
  (the `measurement_desc_id` with the display name of its container, `1 (UDP Ping)`, `16 (Speedtest)`; the short
  names prevail over the long descriptions), network, iccid, start, stop. Click on a row: its `parameters` as
  indented JSON below the table.

**Plots page**: one section per plot from the notebooks; a matplotlib figure of nnedbtools is shown as an image
first and rewritten in Plotly when it needs interaction.

## 8. Interaction
Dash server callbacks and the built-in interaction of AG Grid and Plotly; hand-written JavaScript only for the clock
and the Grid tooltip (`ThreadTable` in `assets/dashAgGridComponentFunctions.js`, React elements, no HTML strings).

| Action | Result |
|---|---|
| Header button | the page (Dash Pages) |
| Sub-tab | the content of the sub-tab |
| Grid / Problems toolbar | the rows filtered in a callback from a store of all rows |
| Grid / Problems row click (`cellClicked`) | the URL query of the node (and of a container cell): the page is built again on Node detail |
| Node selector | the URL query of the node: the page is built again |
| Range button | the x range of the timeline set in a callback; zoom and pan in Plotly |
| Timeline bar click (`clickData`) | the segment detail below the timeline |
| Experiments row click | the `parameters` of the instance below the table |
| Hover on a grid cell or timeline bar | tooltip table or hover label with the detail |

The page shows when its data were loaded; every page load uses the cached data until the next refresh point (section
10).

## 9. Code structure
Package `src/container_status_webpage` (layout in `documentation/DEVELOPMENT.md`); modules added in phase 3 or 4
are marked.

| Module | Content |
|---|---|
| `app.py` | Dash app, `server` for gunicorn, development server |
| `settings.py` | environment variables `DEBUG`, `DB_ENV_FILE`; from phase 3 `DATA_SOURCE` (`synthetic` or `database`) and `CONTAINERS_CACHE_MINUTES` |
| `data/status.py` (3) | the rules of sections 4–6: thread states, cells, crosscheck, overview, problems; pandas only, no Dash |
| `data/synthetic.py` (3) | synthetic data: 20 scenarios covering every class and marker, including a mobile node and a release history |
| `data/cache.py` (3) | the frames of the selected source with their load time, kept per process until the next refresh point |
| `data/loader.py` (4) | the frames from the database through nnedbtools, read-only (section 10) |
| `components/frame.py`, `components/tabs.py` | page frame and sub-tabs |
| `components/palette.py` (3) | the colours of section 6 as Python constants for the grid and the timeline; the colours of the page frame stay in `assets/style.css` |
| `components/grid.py` (3) | AG Grid column definitions, cell style conditions, tooltip rows and toolbar filter of the Overview, Grid and Problems sub-tabs |
| `components/node.py` (3) | Node detail: URL query, header, timeline segments and figure, range, segment detail, threads and experiments tables |
| `assets/dashAgGridComponentFunctions.js` (3) | `ThreadTable`, the tooltip table of a grid cell |
| `pages/containers.py` | layout and callbacks of the Containers page: toolbars, filters, navigation, range, clicks |
| `pages/plots.py` | Plots page |

Input contract: the synthetic data and the loader produce the same three frames.

| Frame | Columns |
|---|---|
| `nodes` | `node_id`, `status`, `interfaces`, `experiments`, `municipality` (the only part of the site address that is loaded) |
| `experiments` | `id`, `node_id`, `network_id`, `service_id`, `measurement_desc_id`, `iccid`, `start_time`, `stop_time`, `parameters` |
| `raw` | the columns of `report.container_rawdata` |

Synthetic data: 20 scenarios × DEPLOYED / TESTING = 40 nodes with ids from 90001: all long-run, fresh restart, young,
stable, late, stale, down, long down, never, udpping partial, thread missing, thread down, flapping, version change,
extra containers, nothing running, no data, inactive experiment, mobile (three short trips a day, parked 5 days, as
7042 / 7045), release history (all containers change version together, a dev build, 50 h down, as 7056). The target
container of a scenario rotates over the main containers; experiments carry made-up parameters; some nodes have no
municipality.

Tests without a browser: the rule checks (class boundaries, flapping, worst thread / partial / orphan, synthetic
coverage) on `data/status.py`; the grid columns, tooltip rows, timeline segments and figure as built objects; the
pure functions behind the callbacks (`filter_rows`, `click_query`, `x_range`); the smoke tests of the skeleton. Tests
never import a page module (Dash Pages loads it as `pages.<name>`; a second import registers the page twice).

## 10. Data loading and cache (phase 4)
`data/loader.py` returns the three frames, read-only through nnedbtools:

- `nodes`: the filter of section 3 (`nne.node_info`, `nne.measurement_instance`, `nne.node_status` / `nne.status`)
  and the site address from `nnedbtools.queries.address.select_from_nne_node_adreess_and_nne_addresss(node_ids)`,
  keeping `address_type` site with `valid_to IS NULL`;
- `experiments`: `nne.measurement_instance` rows of those nodes (active, plus the ones udpping threads refer to), with
  `network_id` and `service_id`;
- `raw`: `SELECT * FROM report.container_rawdata`.

No lookup tables are read: the container of a `measurement_desc_id`, network and service names and colours come from
the nnedbtools enums (section 2), without a database round trip. What the page shows stays as implemented (display
names of section 4, sentence case).

Code changes with the loader: the expected containers of a node from the configuration map in `data/status.py`
(never / not configured, section 5) and the orphan container (section 4); synthetic experiments with `service_id` and
instances for the configured containers, plus an orphan container scenario and a receiver restart scenario; the
network chips through the service decorator (`palette.PROVIDER` removed); the Experiments measurement column with the
container name; the receiver restart warning and column (section 5); the header counts; the satellite nodes as a
loader constant (section 3); the `nodes` frame without `valid_from`, `name`, `address`, `zip`, `country_code`.

Credentials: the nnedbtools env file of the nne-reader account (`DB_ENV_FILE`, read access to `nne` and `report`),
loaded with `nnedbtools.identityprovider.load_from_enviroment`. The SSL CA / CRL of the Apollo hosts come with the
installed nnedbtools (`nnedbtools.certificates`): the Docker container needs only the env file (secret `db_env`).
Development reads go through the nnedbtools test harness (read-only guards). The first real run is compared with the
figures in this document.

`data/cache.py` keeps the frames with their load time in each gunicorn worker until the next refresh point. Containers
tab: `CONTAINERS_CACHE_MINUTES`, default minute 15 and 45 of every hour (the importer writes at minute 10 and 40 and
gets 5 minutes to finish). The other main tabs define their own cache rule. `DATA_SOURCE=synthetic` serves the
synthetic data without a database, for development and tests.

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
- nnedbtools writes `logs/robustnet<timestamp>.log` into the working directory on import: the unit sets
  `WorkingDirectory=` to a directory the service user can write (the Docker image uses `/home/app`).
- `deploy/` and `documentation/INSTALLATION.md` are written in this phase.

## 12. Open points

- Networks missing from `enum_mapper` get the colour "red" from nnedbtools; the chip text of an instance without
  `service_id` from the service decorator is to be checked with the loader.
- The real `parameters` format (the synthetic JSON is made up).
- Thresholds (2 h, 6 h, 24 h, 7 d; 1 h, 1 d, 7 d; 3 starts; receiver restarts 60 per hour / 1440 per day) are constants
  to calibrate after real use.
- Cache per gunicorn worker: with 2 workers the data are loaded twice per refresh point; a shared cache only if the
  load turns out heavy.
- Mobile nodes (7042, 7045, TESTING) appear in Problems under the general rules (section 5); a mobile marker needs a
  field in nne first. On All their timeline has about 2,000 bars.
- The nnedbtools log files (`logs/`, one per worker start) on oculus: rotation or cleanup.

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
