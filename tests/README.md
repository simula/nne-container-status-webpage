# Tests

Smoke tests without a browser and without a database (`test_app.py`):

- the pages are registered from `pages/` of the installed package, in page order;
- the Containers page has the placeholder sub-tabs;
- the pages, the page frame (`/_dash-layout`) and the nne-viz assets are served (Flask test client).

```bash
conda activate nne-container-status-webpage
pytest
```
