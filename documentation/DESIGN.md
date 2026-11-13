# NNE container status webpage – design

A web application (Dash) that shows, for every reported NNE node, whether its docker containers and their threads are
running. The data are the container heartbeats that
[nne-container-status-importer](https://github.com/simula/nne-container-status-importer) imports into
`report.container_rawdata`, checked against the experiment setup in the `nne` database.

| Phase | Content | State |
|---|---|---|
| 1 | Prototype: static HTML generator, interaction, colour rules on synthetic data (local) | done |
| 2 | Skeleton webpage resembling nne-viz: page frame with header navigation, code conventions (section 13), Docker for development | done |
| 3 | Container dashboard in Dash (AG Grid, Plotly) on synthetic data | done |
| 4 | Database loader through nnedbtools (read-only), cache; expected containers from the node configuration map, names and colours from the nnedbtools enums; node map on the Overview (sections 4, 7, 9, 10) | done |
| – | Code structure by the model–view–controller pattern, database statements as SQLAlchemy selects (section 9); further steps in the refactoring plan (section 14) | structure done, plan open |
| 5 | nginx / TLS, set up from scratch | before deployment |
| 6 | Deployment on specula: venv and systemd service, as nne-container-status-importer (section 11) | later |

Figures quoted below were measured on 2026-11-06 unless dated otherwise (first database run: 2026-11-09).

## 1. Scope
- A Dash application (Dash Pages, dash-ag-grid, Plotly) in the look of nne-viz, served by gunicorn behind nginx / TLS
  on specula (section 11).
- Pages: **Overview**, **Grid**, **Problems** and **Node**, the container status dashboard (sections 7–8).
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
| `nne.node_address`, `nne.address` | current site address: `municipality` and the location `loc_lat`, `loc_lon` (optional, rounded to 2 decimals); street, zip and name are not loaded |
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

Exception: the satellite nodes **4071–4074** are reported as DEPLOYED although nne has no `node`, `node_info`
or `node_status` row for them (hardcoded, `model/status.py` `SATELLITE_NODES`). They run neither the metadata nor
the mqtt container: both are never expected there, and their experiment count has no +1 for metadata. Satellite
measurements on other nodes are ad hoc and follow the rules above. Without an address, the map shows them next to
the site of node 7056 (SimulaMet), 0.01° longitude apart (`model/loader.py` `SATELLITE_SITE_NODE`).

On 2026-11-06: DEPLOYED 100, TESTING 16, unchanged with the conditions above on 2026-11-09. Missing status records
found on the way were fixed in `nne.node_status`: 11085 DESTROYED (from 2026-11-06), 10964 and 11165 TESTING (from
2026-09-01). On 2026-11-09 ten nodes ≥ 3100 had no status record (3100, 3178, 4071–4073, 4157, 8000, 9000, 9001,
11447); none of them has an active interface, so none drops out only for the missing record. `nne.node_status` is
synchronised manually.

First database run (2026-11-09): DEPLOYED 103 (the 100 above and the 3 satellite nodes), TESTING 16; 112 of the 119
nodes have a municipality and a location.

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
node configuration generator (`nnedbtools.batch.node_config.SupportedExperimentMapper.CONTAINER_NAME_MAP`); the
satellite nodes expect neither metadata nor mqtt (section 3). QUIC
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
| young | 1–24 h |
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
  start_ts)`, the run counted as at least 1 h. Warning above 60 restarts per hour (a second rule, 1440 per day after
  7 days, was the same rate and was dropped). Chosen on 2026-11-09 from the rates of 233 receivers of 115 nodes:
  median 0.2 per hour, 90th percentile 53, 95th 289; 60 per hour flagged 12 nodes, 1 / 1 had flagged 89 of 119 nodes,
  10 / 10 still 50. The cell state stays; label `↻`; issue "UDP Ping: receiver-<N> restarts <rate>".
  On 2026-11-09: 7056 about 480 per hour, 4120 `receiver-10376` 8 per day over 743 h, the mobile nodes 26–108 in the
  first hour.

Per node (Overview page), each node counted once: *nothing running* = no cell has a running thread (checked first);
*all main OK* = something runs and every configured main cell is running, not partial, without orphans or warnings;
*some issue* = the rest. Flapping alone and issues of the extra containers do not count here: such a node is *all
main OK* and still listed in Problems.

A node is listed on the Problems page when a cell is not running (except not configured), partial, flapping, has
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

**Grade of a node** (map dot, section 7): the worst colour class of its configured containers, from best to worst
long-run, stable, young, fresh, late, stale, down, long down, never; containers that are not configured do not count.
Dark green (long-run) means every configured container has run 7 days or more. The markers (partial, flapping,
orphans, restarts) do not change the grade; they are listed in the hover.

## 7. Page structure
**Page frame** (every page, as nne-viz): header with the NorNet logo (link to nntb.no), "Container Status", one
navigation button per page and the UTC clock; the page; orange footer with the SimulaMet logo on a light
background. Pages: Overview (`/`), Grid (`/grid`), Problems (`/problems`), Node (`/node`). Pages have no title
of their own: the selected header button names the view. Each page starts with the time of the last data load.

| Page | Content |
|---|---|
| Overview | left (60 %): node map on OpenStreetMap (Plotly `Scattermap`, zoom and pan), one dot per node with a location in the colour of its grade (section 6), one legend entry per grade with its count (a click hides it), hover with node, status, municipality, grade and issues, click on a dot: Node of that node; toolbar: Status (Deployed / Testing) and the number of nodes without location. Right (40 %): "Nodes by status" (Deployed, Testing, All: nodes, *all main OK*, *some issue*, *nothing running*) and "Running containers by node status" (per container the nodes running it / the nodes, per status), columns sharing the width with wrapped headers. Below 1000 px the two halves stack |
| Grid | AG Grid, one row per node (Deployed then Testing, by `node_id`): node, status, municipality, then the main and the extra containers as column groups. A container cell shows the symbol and label of its state (section 5) and is coloured by the rules of section 6 (AG Grid cell style conditions built from the palette, section 9); its tooltip is a table of the threads (state on its colour, version, up, last seen, ago, starts 24 h / 7 d; never-seen and orphan rows). Toolbar: Status, State (a node matches when any cell has a chosen state or marker), Node and Municipality (multi-select with search). Sorting per column. Click on a row: Node of that node, on a container cell also of that container |
| Problems | AG Grid, one row per node that is not fully OK: node, status, municipality, issues, last heartbeat (sortable, never first); Deployed first, then the longest silent. Toolbar: Status, Issues (text, case-insensitive), Node, Municipality. Click on a row: Node of that node |
| Node | see below |

Display names: container names Metadata, MQTT, Speedtest, UDP Ping, Traceroute, NetPerfMeter; status Deployed /
Testing; headers in sentence case. The data keep the database values.

**Node** (all containers of a node in one view: a node-wide outage or a release shows across all rows):

- Node selector (searchable), range buttons 1 / 3 / 7 / 14 d and All (7 d first) and the From / To date pickers that
  the buttons fill (UTC days as the timeline; To ends at the end of its day, at most at the newest data). The URL
  `/node?node=<id>&container=<name>` opens the view; `container` highlights the rows of that container.
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

## 8. Interaction
Dash server callbacks and the built-in interaction of AG Grid and Plotly; hand-written JavaScript only for the clock
and the Grid tooltip (`ThreadTable` in `assets/dashAgGridComponentFunctions.js`, React elements, no HTML strings).

| Action | Result |
|---|---|
| Header button | the page (Dash Pages) |
| Grid / Problems toolbar | the rows filtered in a callback from a store of all rows |
| Grid / Problems row click (`cellClicked`) | the URL query of the node (and of a container cell): the page is built again on Node |
| Map toolbar (Status) | the map drawn again in a callback from the map rows of the open page (store `map-nodes`, not the cache, so the map keeps the data of the tables after a refresh); zoom and pan stay (`uirevision`) |
| Map dot click (`clickData`) | the URL query of the node: the page is built again on Node |
| Node selector | the URL query of the node: the page is built again |
| Range button | the exact x range of the timeline (`x_range`) set in a callback; fills the From / To pickers with its days |
| From / To pickers | whole days as x range in the same callback (`picker_range`; an invalid range leaves it); clears the range button; zoom and pan in Plotly do not update the pickers |
| Timeline bar click (`clickData`) | the segment detail below the timeline |
| Experiments row click | the `parameters` of the instance below the table |
| Hover on a grid cell, timeline bar or map dot | tooltip table or hover label with the detail |

When the tables, the map and the node selector appear, Dash reports their empty values (`cellClicked`, `clickData`,
`value`) despite `prevent_initial_call`; the navigation ignores them. The node ids of the map dots are a plain list:
Plotly sends a numpy column base64-encoded, and `dcc.Graph` then passes the click without `customdata`.

The page shows when its data were loaded; every page load uses the cached data until the next refresh point (section
10).

## 9. Code structure
Package `src/container_status_webpage`, split by the model–view–controller pattern:

- **model** (`model/`): the data and the rules. Pandas only: it imports neither Dash nor Plotly, and nothing from
  the view or the controller.
- **view** (`view/`): functions that build Dash and Plotly objects from the page data of `model/pages.py`. No
  callbacks; a view never loads data, never takes the snapshot and calls no model function that derives data (only
  constants and text helpers).
- **controller** (`controller/`, one module per page): the function that builds the page on a page load (`page`:
  reads the cached data, builds the page data with `model/pages.py` and hands it to the views) and the callbacks of
  the page. The only place with callbacks
  and the only place that reads the cache.

`tests/test_layers.py` checks these rules on every module, and that no module writes SQL as text.

| Module | Content |
|---|---|
| `app.py` | Dash app, `server` for gunicorn, development server |
| `settings.py` | environment variables `DEBUG`, `DB_ENV_FILE`, `DATA_SOURCE` (`synthetic` or `database`), `CONTAINERS_CACHE_MINUTES` |
| `model/limits.py` | the limits of the classes and warnings: last seen, uptime, flapping, receiver restarts, down gap, first deployment |
| `model/orders.py` | the orders of the statuses and classes: reported statuses, last seen classes from best to worst, grades |
| `model/status.py` | the rules of sections 4–6: thread states, cells, crosscheck, overview, problems, issue texts; network names of the experiments |
| `model/timeline.py` | timeline of a node: rows, segments, time span, x ranges of the range buttons and the date pickers |
| `model/pages.py` | what each page shows, prepared from the snapshot: one dataclass per page (`OverviewData`, `GridData`, `ProblemsData`, `NodeData`) and the function that builds it; `map_nodes` for the map filter |
| `model/synthetic.py` | synthetic data: 22 scenarios covering every class and marker, including a mobile node, a release history, an orphan container and receiver restarts |
| `model/snapshot.py` | `Snapshot`: the three frames of a source with their summary and load time; `load` reads them from a source |
| `model/cache.py` | the snapshot of the selected source, kept per process until the next refresh point |
| `model/loader.py` | the frames from the database through nnedbtools, read-only, as SQLAlchemy selects: `load_database` reads, `reported` builds the frames without database access (section 10) |
| `view/frame.py` | page frame |
| `view/layouts.py` | the four pages composed of the views, with the toolbar items, the filter toolbar of the tables and the data line |
| `view/formatting.py` | text of times, durations and missing values, shared by the tables and the timeline |
| `view/palette.py` | every colour of the Python views as constants: the colours of section 6, status chips, timeline and map; the colours of the page frame stay in `assets/style.css` |
| `view/grid.py` | AG Grid column definitions, cell style conditions, tooltip rows and toolbar filter of the Overview, Grid and Problems pages |
| `view/node.py` | Node: header, timeline figure, segment detail, threads and experiments tables |
| `view/nodemap.py` | Overview map: hover lines, located nodes with their grade, `Scattermap` figure |
| `assets/dashAgGridComponentFunctions.js` | `ThreadTable`, the tooltip table of a grid cell |
| `controller/frame.py` | navigation highlight and clock of the page frame (`app.layout` is `view/frame.py` `layout`) |
| `controller/overview.py` | Overview: page load, map status filter, map click |
| `controller/grid.py` | Grid: page load, toolbar filter, row click |
| `controller/problems.py` | Problems: page load, toolbar filter, row click |
| `controller/node.py` | Node: URL of the page, page load from the URL query, node selector, range buttons and date pickers, clicks on a segment and on an experiment |
| `pages/containers.py` | registration of the four pages with the `page` functions of their controllers (Dash Pages needs this folder) |

Input contract: the synthetic data and the loader produce the same three frames.

| Frame | Columns |
|---|---|
| `nodes` | `node_id`, `status`, `interfaces`, `experiments`, `municipality`, `loc_lat`, `loc_lon` (the only parts of the site address that are loaded; the coordinates rounded to 2 decimals, about 1 km, so the map does not pinpoint the sites); the synthetic frame adds `scenario`, used by the tests |
| `experiments` | `id`, `node_id`, `network_id`, `service_id`, `measurement_desc_id`, `iccid`, `start_time`, `stop_time`, `parameters` |
| `raw` | the columns of `report.container_rawdata` |

Synthetic data: 22 scenarios × DEPLOYED / TESTING = 44 nodes with ids from 90001: all long-run, fresh restart, young,
stable, late, stale, down, long down, never, udpping partial, thread missing, thread down, flapping, version change,
extra containers, nothing running, no data, inactive experiment, mobile (three short trips a day, parked 5 days, as
7042 / 7045), release history (all containers change version together, a dev build, 50 h down, as 7056), orphan
container (NetPerfMeter alive without an instance), receiver restarts (480 per hour, as 7056). The target container of
a scenario rotates over the main containers; experiments use networks 1, 2 and 18 with 4G / 5G, MQTT the dummy
network 0, and carry made-up parameters; sites lie near five municipality centres (coordinates rounded as the loader
does); some nodes have no municipality and no location.

Tests without a browser: the rule checks (class boundaries, flapping, worst thread / partial / orphan, synthetic
coverage) on `model/status.py`; the grid columns, tooltip rows, timeline segments and figure as built objects; the
pure functions behind the callbacks (`filter_rows`, `click_query`, `x_range`, `picker_range`); the map figure (one
dot per located node, status filter, grade order, plain-list `customdata`); the cache (one load per refresh point, a
failed load keeps the snapshot); the smoke tests of the pages. One line per test file: `tests/README.md`. Tests never
import a page module (Dash Pages loads it as `pages.<name>`; a second import registers the page twice).

## 10. Data loading and cache (phase 4)
`model/loader.py` returns the three frames, read-only through nnedbtools:

- `nodes`: one SQLAlchemy select (`select_reported_node_candidates`) for the filter of section 3 (`node_info`, `measurement_instance`, `node_status` / `status`)
  with the interface and experiment counts, the satellite nodes added as DEPLOYED; then `municipality`, `loc_lat` and
  `loc_lon` from `nnedbtools.queries.address.select_from_nne_node_adreess_and_nne_addresss(node_ids)`, keeping
  `address_type` SITE with `valid_to IS NULL`, the coordinates rounded to 2 decimals;
- `experiments`: all `measurement_instance` rows of those nodes, active and stopped
  (`queries.augumentation.select_from_nne_measurement_instance(node_ids)`), with `network_id` and `service_id`;
- `raw`: `select(tables.ReportContainerRawdata)` on the report engine, all rows.

`load_database` only reads: the candidate nodes, the site addresses and experiments of all candidates, the
container runs. `reported` builds `nodes` and `experiments` from these frames without database access (the
satellite nodes, the filter of section 3, the coordinates, the site merge, the experiments of the reported nodes);
`tests/test_loader.py` checks it on hand-made frames. Reading for all candidates costs little: 134 candidates for 119
reported nodes, 92 more `measurement_instance` rows (2026-11-13).

No lookup tables are read: the container of a `measurement_desc_id`, network and service names and colours come from
the nnedbtools enums (section 2), without a database round trip. What the page shows stays as implemented (display
names of section 4, sentence case).

Credentials: the nnedbtools env file of the nne-reader account (`DB_ENV_FILE`, read access to `nne` and `report`),
loaded with `nnedbtools.identityprovider.load_from_enviroment`. The SSL CA / CRL of the Apollo hosts come with the
installed nnedbtools (`nnedbtools.certificates`): the Docker container needs only the env file (secret `db_env`).
Development: `DATA_SOURCE=database` in the container with `.db_env_test`, generated from the nnedbtools test harness
(DEVELOPMENT.md); compose maps the nnedbtools log files to `exports/logs`.

First run from the container (2026-11-09): the reader account has SELECT / SHOW VIEW only on `nne` and `report`; 119
nodes (section 3); 713 measurement instances (624 active), none without `service_id`; every network named by the
service decorator (5G on all mobile networks, LAN with GeoSat, OneWeb, Starlink); `parameters` plain JSON text;
13,563 rows of `container_rawdata`; header and Experiments built for every node. Problems: 96 of 119 nodes with the
first receiver restart rule (1 per hour / 1 per day), 24 with 60 / 1440 (12 of them for receiver restarts).

`model/cache.py` keeps the frames with their load time in each gunicorn worker until the next refresh point:
`CONTAINERS_CACHE_MINUTES`, default minute 15 and 45 of every hour (the importer writes at minute 10 and 40 and gets
5 minutes to finish). A load that fails is logged and the previous snapshot stays: the pages keep the older data and
show their load time; the next request tries again. `DATA_SOURCE=synthetic` serves the synthetic data without a
database, for development and tests.

## 11. Deployment on specula (phase 6)

Set up as the batch nne-container-status-importer is on its host oculus (its `documentation/INSTALLATION.md`): a
virtual environment with the project, run by systemd. Docker is only for local development.

- Checkout `/nne/nne-container-status-webpage`, virtual environment `.venv` with the project (`pip install .`);
  nnedbtools from its release tag over SSH, as for the importer.
- systemd service `deploy/nne-container-status-webpage.service` under a service user of its own on specula: runs
  `gunicorn container_status_webpage.app:server` bound to localhost, restarted on failure, logs in the journal.
- Settings as environment variables of the unit; `DB_ENV_FILE` points to the nne-reader env file outside the
  repository (e.g. `~/.config/nne-container-status-webpage/`).
- nginx with TLS in front (phase 5), set up from scratch; access control is decided there.
- nnedbtools writes `logs/robustnet<timestamp>.log` into the working directory on import: the unit sets
  `WorkingDirectory=` to a directory the service user can write (the Docker image uses `/home/app`).
- `deploy/` and `documentation/INSTALLATION.md` are written in this phase.

## 12. Open points

- Networks missing from `enum_mapper` get the colour "red" from nnedbtools (none on 2026-11-09).
- The map tiles come from `tile.openstreetmap.org`: fine for light use under the OpenStreetMap tile usage policy;
  heavier use on specula needs another tile provider.
- Thresholds (2 h, 6 h, 24 h, 7 d; 1 h, 1 d, 7 d; 3 starts; receiver restarts 60 per hour; down gap 1 h; first
  deployment 2026-01-01) are constants in `model/limits.py` to calibrate after real use; the legend and the timeline
  write them from there.
- Cache per gunicorn worker: with 2 workers the data are loaded twice per refresh point; a shared cache only if the
  load turns out heavy.
- Mobile nodes (7042, 7045, TESTING) appear in Problems under the general rules (section 5); a mobile marker needs a
  field in nne first. On All their timeline has about 2,000 bars.
- The nnedbtools log files (`logs/`, one per worker start) on specula: rotation or cleanup.
- The Experiments table shows ICCIDs and instance parameters to everyone who can open the page: access control is
  decided with nginx (phase 5).
- The open points of the code itself are steps of the refactoring plan (section 14).
- Code review of 2026-11-13, left as they are: the Grid filter sends its rows store (≈ 400 KB) with every change,
  not noticeable on the VPN, a filter in the browser was rejected (no JavaScript to maintain); names from the
  database are shown in Plotly text unescaped, clean names are the job of the data source (importer, nne); the
  Docker image is for development only and is not hardened (no digest pin, no healthcheck, GitHub host key by
  `ssh-keyscan`). Planned: a loading of `report.container_rawdata` that stays fast over years of growth, and no
  request waiting for the refresh load (part C of the review).

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
- **Docstrings**: Google style with `Args:`, `Returns:`, `Raises:`; an example in the module docstring
  (`Sample code:`); raw strings when a docstring contains a backslash.
- **Step comments** inside functions as in nnedbtools: lettered phases, numbered steps, lettered sub-steps
  (`# A. Normalize input`, `# 1. Check if node exists`, `# a. Shorthand for nne.node table`); short aliases for
  ORM tables (`mi = tb.NneMeasurementInstance`).
- **Type annotations** on parameters, return values and locals whose type is not obvious, as in nnedbtools.
- **Database access** only through nnedbtools and read-only: select builders from `nnedbtools.queries` where they
  exist, new selects as SQLAlchemy `select` in the same style, engines from `nnedbtools.connection`. No SQL as text.
- **Layers**: model, view and controller as in section 9. A new function goes to the layer of what it does, not to
  the module that calls it.
- **Logging** with `logging`, no `print` in the application.
- **JavaScript** only where Dash needs it (client-side callbacks), short and commented the same way.
- **Formatting and linting** as nnedbtools: `black .`, `isort .`, `pylint --rcfile .pylintrc src tests tools` with a copy of the
  nnedbtools `.pylintrc` (maximum line length 100).
- **Branches** `feat/{feature}` and `fix/{fix}`, merged through pull requests on
  https://github.com/simula/nne-container-status-webpage.

## 14. Refactoring plan

From the code review of 2026-11-12. The structure of section 9 is in place; these steps finish it, in this order.
Each step is its own `feat/` branch. Steps 0–3 change no behaviour: the layout of every page and the registered
callbacks, built on the synthetic data at a fixed time, are compared before and after and must be identical.

| Step | Content | Proven by | State |
|---|---|---|---|
| 0 | Safety net in the repository: a test that fails when a layer rule of section 9 is broken or SQL appears as text; the layout comparison as a development tool; no CI (internal page of a small team): the checks run locally as in DEVELOPMENT.md | the test fails on a deliberate violation, then passes | done |
| 1 | Loader: `load_database` only reads; a pure function builds the `nodes` frame from the read frames (satellite nodes, status and interface filter, site merge) | tests on hand-made frames; the same nodes on Apollo | done |
| 2 | Thread state (`status.thread_states`) as a dataclass instead of a dict with string keys | identical layouts | done |
| 3 | Controllers prepare the data, views only build: selection and derivation move from `view/` (`node.header`, `nodemap.located`, the timeline calls of `view/node.py`) to `model/`; views take prepared data instead of the snapshot | identical layouts | done |
| 4 | The rule points below; they change what the pages show, so each is decided first | a test per rule | done |
| 5 | Only when it hurts: component ids as constants shared by view and controller; `model/status.py` and `view/grid.py` split | the id test fails on a misspelled id | done |

Layout comparison: `python tools/layout_snapshot.py <file>` with `DATA_SOURCE` unset, on the base branch and on the
step branch, then `cmp` the two files; no output means the same layouts and callbacks.

Rule points of step 4, decided and done on 2026-11-13: one restart rule (60 per hour); the limits in `model/limits.py`,
legend and timeline texts written from them (young now "1–24 h"); the timeline starts no earlier than the first real
deployment (`FIRST_DEPLOYMENT`, 2026-01-01); the failed load keeps its retry on every request (`ponytail` note in
`model/cache.py`); the small points fixed (`isdecimal` also in `status.experiment_id`). The points as found:

- Receiver restart rule: 1440 per day after 7 days is the same rate as 60 per hour, so the second condition never
  decides (`status.restart_warning`); keep one rule, or give the long runs a lower limit.
- The legend and the timeline repeat the class limits as text (`view/grid.py` `legend`, `view/node.py`):
  a calibration of the constants in `model/status.py` must change them too.
- Rows with a node clock error (`start_ts` 2011, section 2) stretch All and the From picker of that node to 2011.
- A data load that fails is tried again on every request until it succeeds; a retry delay if an outage makes the
  pages slow.
- Small: `/node?node=²` answers 500 (`isdigit`); `settings.py` imports `marshmallow`, a dependency of environs that
  is not declared; an empty `CONTAINERS_CACHE_MINUTES` fails at the first request, not at the start;
  `assets/network_indicator.png` is not used.

Step 5, decided on 2026-11-13: the component ids stay strings, as Dash writes them; `tests/test_app.py` checks that
every id a callback uses exists in the page frame or a page (Dash Pages suppresses callback exceptions, so a
misspelled id would fail without an error). `model/status.py` and `view/grid.py` are not split: each holds one topic
in the order of this document (the rules of sections 4–6; the AG Grid tables with their cell styles and legend),
the functions are short, and a split would only move code and imports.
