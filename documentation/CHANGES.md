# Changes

## Unreleased

First version of the container status dashboard (design: [DESIGN.md](DESIGN.md)).

- Dash Pages app with the nne-viz look: header "Container Status" with one button per page and a UTC clock, footer.
  Package `container_status_webpage` (src layout, `pyproject.toml`), nnedbtools pinned to
  `v.2026-11-06-Heartbeat-Split`.
- Rules of the container status (`model/status.py`): last seen and uptime classes per thread; the cell of a node and
  container (worst thread, partial, flapping); expected containers from the node configuration map of nnedbtools
  (metadata always; "never" when configured without rows, empty when not configured); orphan threads and orphan
  containers; UDP Ping receiver restart warning (above 60 per hour, or 1440 per day after 7 days).
- Overview (`/`): node map on OpenStreetMap (one dot per node in the colour of its grade, legend with counts,
  Deployed / Testing filter, a click opens Node) and the tables "Nodes by status" and "Running containers by node
  status".
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
  Metadata and MQTT, on the map next to the site of node 7056.
- Synthetic data (`DATA_SOURCE=synthetic`, the default): 44 nodes in 22 scenarios covering every class and marker.
- Cache per process, loaded again after each importer run (`CONTAINERS_CACHE_MINUTES`); a failed load is logged and
  the previous data stay.
- Code structure by the model–view–controller pattern: `model/`, `view/`, `controller/` with one module per page;
  database statements as SQLAlchemy selects, no SQL as text.
- Development: Docker image (gunicorn) and compose file with the nne-reader env file as a secret, `build-web.sh`,
  manual in DEVELOPMENT.md.
