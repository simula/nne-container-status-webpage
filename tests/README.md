# Tests

Without a browser and without a database: the tests run on the synthetic data (`model/synthetic.py`) or on hand-made
frames.

| File | Protects |
|---|---|
| `test_status.py` | the rules of `model/status.py`: class boundaries, flapping, receiver restart warning, worst thread / partial / orphans, satellite nodes, grade, problem list and Overview counts; the synthetic data cover every class and marker |
| `test_cache.py` | one load per refresh point; a failed load keeps the previous snapshot |
| `test_grid.py` | tables of Overview, Grid and Problems: a style condition for every cell, tooltip rows, toolbar filter |
| `test_node.py` | Node page (`model/timeline.py`, `view/node.py`): timeline segments, range buttons and date pickers, threads and experiments tables, header |
| `test_nodemap.py` | Overview map: one dot per located node, status filter, grade order, click target |
| `test_loader.py` | the frames built from the database frames (`model/loader.py` `reported`): status and interface filter, satellite nodes, site addresses, experiments of the reported nodes |
| `test_app.py` | smoke tests: pages registered in order, Node page from its URL query, pages and assets served |
| `test_layers.py` | the layer rules of DESIGN section 9 on every module: the model without Dash, Plotly, view and controller; the views without the controller and the data sources; the cache and the callbacks only in the controller; no SQL as text |

Not covered: the database reads of `model/loader.py` (they need the database) and the callbacks in `controller/`. Tests never import a
page module: Dash Pages loads it as `pages.<name>`, and a second import registers the pages twice.

```bash
conda activate nne-container-status-webpage
pytest
```
