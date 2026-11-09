# Changes

## Unreleased

- Skeleton webpage with the nne-viz look: Dash Pages app with header, navigation, Norway clock and footer; pages
  Containers (placeholder sub-tabs Overview, Grid, Problems, Node detail) and Plots (placeholder).
- Package `container_status_webpage` (src layout, `pyproject.toml`), nnedbtools pinned to `v.2026-11-06-Heartbeat-Split`.
- Development Docker image (gunicorn) and compose file; the nne-reader env file is mounted as a secret.
- Container dashboard on synthetic data (phase 3): rules of the container status (`data/status.py`), 40 synthetic
  nodes in 20 scenarios including a mobile node and a release history, cache refreshed after each importer run
  (`CONTAINERS_CACHE_MINUTES`).
- Overview, Grid (colour grid, thread table tooltip, toolbar filters) and Problems (toolbar filters, issues text
  search, sortable last heartbeat); display names for containers and status, sentence case headers.
- Node detail: node selector and links from Grid / Problems (`/?tab=node&node=<id>&container=<name>`), header,
  timeline of all threads (runs, down periods, silence to now, version changes, range buttons), segment detail,
  threads and experiments tables with the parameters JSON.
- Header "NorNet is on the Edge", light background behind the SimulaMet footer logo.
- Manual for starting and restarting the container and the environment (DEVELOPMENT.md).
