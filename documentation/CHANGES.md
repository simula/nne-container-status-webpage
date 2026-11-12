# Changes

## Unreleased

- Skeleton webpage with the nne-viz look: Dash Pages app with header, navigation, Norway clock and footer; pages
  Containers (placeholder sub-tabs Overview, Grid, Problems, Node detail) and Plots (placeholder).
- Package `container_status_webpage` (src layout, `pyproject.toml`), nnedbtools pinned to `v.2026-11-06-Heartbeat-Split`.
- Development Docker image (gunicorn) and compose file; the nne-reader env file is mounted as a secret.
- Container dashboard on synthetic data (phase 3): rules of the container status (`data/status.py`), 44 synthetic
  nodes in 22 scenarios including a mobile node, a release history, an orphan container and receiver restarts, cache
  refreshed after each importer run (`CONTAINERS_CACHE_MINUTES`).
- Overview, Grid (colour grid, thread table tooltip, toolbar filters) and Problems (toolbar filters, issues text
  search, sortable last heartbeat); display names for containers and status, sentence case headers.
- Node detail: node selector and links from Grid / Problems (`/?tab=node&node=<id>&container=<name>`), header,
  timeline of all threads (runs, down periods, silence to now, version changes, range buttons), segment detail,
  threads and experiments tables with the parameters JSON.
- Header "NorNet is on the Edge", light background behind the SimulaMet footer logo.
- Manual for starting and restarting the container and the environment (DEVELOPMENT.md).
- Expected containers from the node configuration map of nnedbtools (metadata always; "never" when configured without
  rows, empty when not configured); a running container without a configured instance is a problem.
- UDP Ping receiver restart warning (`extra` per hour of the run): above 60 per hour, or 1440 per day after 7 days;
  `↻` and an amber dot in the grid, an issue in Problems, a Receiver restarts column in the tooltip and the Threads
  table.
- Node header with the interface and experiment counts and one network chip per network and service (`Telenor:5G`,
  names and colours from the nnedbtools enum_mapper); Experiments table with the container of the measurement.
- Read-only database loader (`DATA_SOURCE=database`, `data/loader.py`): reported nodes, satellite nodes 4071–4073 as
  DEPLOYED without Metadata and MQTT, municipality and location of the site, measurement instances,
  `report.container_rawdata`; compose passes `DATA_SOURCE` and maps the nnedbtools log files to `exports/logs`.
- Overview: node map on the left (OpenStreetMap, one dot per node in the colour of its grade, legend with counts,
  hover with the issues, click opens Node detail, Deployed / Testing filter), the tables on the right with the title
  "Nodes by status".
- Map: satellite nodes 4071–4073 shown next to the site of node 7056 (SimulaMet), 0.01° longitude apart.
- Overview, Grid, Problems and Node detail are header pages (`/`, `/grid`, `/problems`,
  `/node?node=<id>&container=<name>`) instead of sub-tabs of Containers; the Plots placeholder page removed.
- Fixed: database coordinates arrive as strings: converted to numbers, so the rounding to 2 decimals applies.
- Fixed: map clicks reached the server without the node id (`customdata` as a plain list); a 500 at page load from
  the navigation callback on the empty values of the tables and the node selector.
- Header title "Container Status"; the header clock shows UTC ("UTC:") instead of Norway time.
