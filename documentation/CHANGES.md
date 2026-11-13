# Changes

## Unreleased

First version of the container status dashboard (design: [DESIGN.md](DESIGN.md)).

- Dash Pages app with the nne-viz look: header "Container Status" with one button per page and a UTC clock, footer.
  Package `container_status_webpage` (src layout, `pyproject.toml`), nnedbtools pinned to
  `v.2026-11-06-Heartbeat-Split`.
- Rules of the container status (`model/status.py`): last seen and uptime classes per thread; the cell of a node and
  container (worst thread, partial, flapping); expected containers from the node configuration map of nnedbtools
  (metadata always; "never" when configured without rows, empty when not configured); orphan threads and orphan
  containers; UDP Ping receiver restart warning (above 60 per hour).
- Overview (`/`): node map on OpenStreetMap (one dot per node in the colour of its grade, legend with counts,
  Deployed / Testing filter, a click opens Node) and the tables "Nodes by status" and "Running containers by node
  status".
- Tab titles "Containers – <page>" (were "NorNet edge – <page>"); app title "NorNet Edge – Container Status".
- Limits of the classes and warnings in `model/limits.py`; the legend and the timeline write them from there (young
  now "1–24 h"). The timeline starts no earlier than the first real deployment (2026-01-01), so node clock errors
  (2011) no longer stretch it. `/node?node=²` no longer answers 500; `marshmallow` declared; an empty
  `CONTAINERS_CACHE_MINUTES` fails at the start; unused `assets/network_indicator.png` removed. The orders of the statuses and classes
  in `model/orders.py`; every colour of the Python views in `view/palette.py`.
- Grid, Problems and Overview fill the window: the Grid and Problems tables below their toolbar, scrolling inside
  (were 70 % of the window high), the Overview map down to the footer (was 650 px); no empty band above the footer
  on tall windows.
- Grid (`/grid`): one row per node, one coloured cell per container, thread table as tooltip, toolbar filters
  (status, state, node, municipality).
- Problems (`/problems`): nodes that are not fully OK, Deployed first, then the longest silent; toolbar filters with
  an issues text search.
- Node (`/node?node=<id>&container=<name>`): header with status, municipality, interface and experiment counts and
  network chips; timeline of all threads (runs, down periods, silence to now, version changes) with the range buttons
  1 / 3 / 7 / 14 d / All and From / To date pickers; segment detail; threads table; experiments table with the
  parameters JSON.
- Read-only database loader (`DATA_SOURCE=database`, `model/loader.py`): reported nodes with their municipality and
  location, measurement instances, `report.container_rawdata`; satellite nodes 4071–4074 reported as DEPLOYED without
  Metadata and MQTT, on the map next to the site of node 7056. `load_database` only reads; `reported` builds the
  frames without database access (tested on hand-made frames).
- Synthetic data (`DATA_SOURCE=synthetic`, the default): 44 nodes in 22 scenarios covering every class and marker.
- Cache per process, loaded again after each importer run (`CONTAINERS_CACHE_MINUTES`); a failed load is logged and
  the previous data stay.
- Code structure by the model–view–controller pattern: `model/`, `view/`, `controller/` with one module per page; the
  loaded data (`model/snapshot.py`) apart from their cache (`model/cache.py`); thread states as a dataclass
  (`status.ThreadState`); page data (`model/pages.py`), from which the views build; database statements as SQLAlchemy selects, no SQL as text.
- Development: Docker image (gunicorn) and compose file with the nne-reader env file as a secret, `build-web.sh`,
  manual in DEVELOPMENT.md.
- Safety net: `tests/test_layers.py` checks the layer rules and that no SQL is written as text;
  `tools/layout_snapshot.py` compares the pages before and after a refactoring.
- Header logo: the NorNet globe signal logo (`assets/nornet.png`, 757×256, 256 colours, 42 KB instead of 168 KB), shown
  3em high.
