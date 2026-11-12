# Tests

Without a browser and without a database: the tests run on the synthetic data (`data/synthetic.py`) or on hand-made
frames.

| File | Protects |
|---|---|
| `test_status.py` | the rules of `data/status.py`: class boundaries, flapping, receiver restart warning, worst thread / partial / orphans, satellite nodes, grade, problem list and Overview counts; the synthetic data cover every class and marker |
| `test_cache.py` | one load per refresh point; a failed load keeps the previous snapshot |
| `test_grid.py` | tables of Overview, Grid and Problems: a style condition for every cell, tooltip rows, toolbar filter |
| `test_node.py` | Node page: timeline segments, range buttons and date pickers, threads and experiments tables, header |
| `test_nodemap.py` | Overview map: one dot per located node, status filter, grade order, click target |
| `test_app.py` | smoke tests: pages registered in order, Node page from its URL query, pages and assets served |

Not covered: `data/loader.py` (needs the database) and the callbacks of `pages/containers.py`. Tests never import a
page module: Dash Pages loads it as `pages.<name>`, and a second import registers the pages twice.

```bash
conda activate nne-container-status-webpage
pytest
```
