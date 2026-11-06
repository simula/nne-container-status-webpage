# Development

## Setup (macOS)

Prerequisites: conda, Docker Desktop, an SSH key with access to https://github.com/simula/nnedbtools (pip and the
Docker build fetch nnedbtools from its release tag over SSH).

```bash
conda env create -f environment.yml          # Python 3.14.4, the project editable with [test,dev], nnedbtools
conda activate nne-container-status-webpage
```

After a change of `pyproject.toml` (e.g. a new nnedbtools tag): `pip install -e ".[test,dev]"`.

## Run

```bash
DEBUG=true container-status-webpage           # development server with hot reload, http://localhost:8050
```

## Tests

```bash
pytest                                        # smoke tests without a browser (tests/README.md)
```

## Code conventions

As nnedbtools, see [DESIGN.md section 13](DESIGN.md#13-code-conventions). Before a commit:

```bash
isort . && black . && pylint --rcfile .pylintrc src tests
```

Branches `feat/{feature}` and `fix/{fix}`, pull requests on https://github.com/simula/nne-container-status-webpage.

## Code structure

| Path | Content |
|---|---|
| `src/container_status_webpage/app.py` | Dash app (`app`, `server` for gunicorn), development server `main()` |
| `src/container_status_webpage/settings.py` | settings from environment variables (`DEBUG`, `DB_ENV_FILE`) |
| `src/container_status_webpage/components/` | layout components in the nne-viz look: page frame, sub-tabs |
| `src/container_status_webpage/pages/` | one module per page (Dash Pages): Containers, Plots |
| `src/container_status_webpage/assets/` | nne-viz style (`style.css`) and logos, served by Dash |
| `tests/` | smoke tests |
| `prototype/` | static HTML prototype with the colour rules, reference for phase 3, then removed |

## Docker

```bash
DB_ENV_FILE=/path/to/nne-reader.db_env docker compose up --build    # http://localhost:8050
```

The nne-reader env file is mounted as the secret `/run/secrets/db_env` and never copied into the image. The pages of
the skeleton do not read the database; for a test run without the file: `DB_ENV_FILE=/dev/null docker compose up`.
