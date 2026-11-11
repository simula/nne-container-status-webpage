# Development

## Setup (macOS)

Prerequisites: conda, Docker Desktop, an SSH key with access to https://github.com/simula/nnedbtools (pip and the
Docker build fetch nnedbtools from its release tag over SSH).

```bash
conda env create -f environment.yml          # Python 3.14.4, the project editable with [test,dev], nnedbtools
conda activate nne-container-status-webpage
```

After a change of `pyproject.toml` (e.g. a new nnedbtools tag): `pip install -e ".[test,dev]"`.

## Start and restart

All commands run from the repository root. Docker is only for local development; the deployment on oculus uses a
virtual environment with a systemd service ([DESIGN.md section 11](DESIGN.md#11-deployment-on-oculus-phase-6)).

### Before you start

1. **Docker Desktop is running**: `docker info` answers. If not: `open -a Docker`.
2. **The SSH key is in the agent**: `ssh-add -l` lists a key. The build (and `conda env create`) clone nnedbtools from
   GitHub over SSH. After a restart of the Mac the agent is empty (`The agent has no identities.`):

   ```bash
   ssh-add --apple-load-keychain                 # loads the keys whose passphrase is in the macOS keychain
   ssh-add --apple-use-keychain ~/.ssh/<key>     # only once, if the passphrase is not in the keychain yet
   ```

3. **The database env file is set**, once per terminal. The pages run on synthetic data and need no database:

   ```bash
   export DB_ENV_FILE=/dev/null                  # synthetic data
   export DB_ENV_FILE=./.db_env_test             # with database (DATA_SOURCE=database, see Database mode)
   ```

   The env file is mounted as the secret `/run/secrets/db_env` and never copied into the image.

### Container

| Task | Command |
|---|---|
| Build and start on the database, loading the SSH key first | `./build-web.sh` |
| Build and start on synthetic data | `./build-web.sh synthetic` |
| Build and start | `docker compose up -d --build` → http://localhost:8050 |
| Build and start on the database (Database mode below) | `DB_ENV_FILE=./.db_env_test DATA_SOURCE=database docker compose up -d --build` |
| Start the last built image (no GitHub access needed) | `docker compose up -d` |
| Status | `docker compose ps` |
| Does the page answer? (expect `200`) | `curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8050/` |
| Logs | `docker compose logs -f webpage` |
| Restart (same image) | `docker compose restart` |
| After a code change | `docker compose up -d --build` |
| Stop (keep the container) | `docker compose stop` |
| Stop and remove the container | `docker compose down` |

The source is copied into the image (no bind mount): every code change needs a rebuild. The nnedbtools log files land
in `exports/logs/` (git-ignored).

### Full reset of the container

```bash
docker compose down
docker image rm nne-container-status-webpage:dev
docker compose build --no-cache
docker compose up -d
```

### Database mode (nne-reader)

`DATA_SOURCE=database` loads the data from Apollo with the nne-reader account, read-only (grants: SELECT / SHOW VIEW).
The container reads the nnedbtools env file `.db_env_test` in the repository root (git- and docker-ignored, mode
600): the nnedbtools keys `NNE_DB_*` and `REPORT_DB_*` of the reader account, no SSL paths (nnedbtools uses its
bundled Apollo CA / CRL). It is generated from the nnedbtools test harness (a checkout next to this repository with
its test settings), without printing a value; run from the repository root with the conda env:

```python
import os
import sys

TARGET = os.path.abspath(".db_env_test")
sys.path.insert(0, os.path.abspath("../nnedbtools/tests"))
import harness  # merges the nnedbtools test settings with the reader account
from nnedbtools.identityprovider import IdentityProvider

with open(harness.ENV_FILE, encoding="utf-8") as handle:
    values = dict(line.rstrip("\n").split("=", 1) for line in handle if "=" in line)
values.update({key.upper(): value for key, value in harness.APOLLO_REPORT.items()})  # report on Apollo
keys = [k.value for k in IdentityProvider.EnvironmentKey if "_SSL_" not in k.value]
fd = os.open(TARGET, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
with os.fdopen(fd, "w", encoding="utf-8") as handle:
    handle.writelines(f"{key}={values[key]}\n" for key in keys if key in values)
```

Checks against the real data run inside the container, with its env file and data source:
`docker compose exec -T webpage python - < check.py` (SELECT statements only).

### Development server without Docker

```bash
conda activate nne-container-status-webpage
DEBUG=true container-status-webpage           # hot reload, http://localhost:8050
```

The container uses the same port: stop it first (`docker compose stop`).

### Rebuild the conda environment

```bash
conda deactivate
conda env remove -n nne-container-status-webpage
conda env create -f environment.yml          # needs the SSH key in the agent (see above)
```

After a change of `pyproject.toml` only: `pip install -e ".[test,dev]"` in the activated environment.

On this Mac `conda run -n nne-container-status-webpage …` runs the wrong interpreter; in scripts call
`/opt/anaconda3/envs/nne-container-status-webpage/bin/python` by its absolute path.

### Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Build step `pip install` fails with `Permission denied (publickey)` | SSH agent empty | `ssh-add --apple-load-keychain` |
| `Cannot connect to the Docker daemon` | Docker Desktop not running | `open -a Docker` |
| `port is already allocated` / `Address already in use` | container or development server already on 8050 | `lsof -i :8050`, stop that process or `docker compose down` |
| compose reports the secret file `./.db_env` missing | `DB_ENV_FILE` not set | `export DB_ENV_FILE=/dev/null` |
| `gunicorn` fails with `Permission denied: '/home/app'` | image built from an old Dockerfile | full reset (above) |
| Map empty in a headless browser screenshot | no WebGL in headless Chrome | `--headless=new --use-angle=swiftshader --enable-unsafe-swiftshader` |

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
| `src/container_status_webpage/settings.py` | settings from environment variables: `DEBUG`, `DB_ENV_FILE`, `DATA_SOURCE` (`synthetic` or `database`), `CONTAINERS_CACHE_MINUTES` (default `15,45`) |
| `src/container_status_webpage/data/` | rules (`status.py`), synthetic data (`synthetic.py`), database loader (`loader.py`), cache (`cache.py`) |
| `src/container_status_webpage/components/` | page frame, palette, formatting, Grid / Problems / Overview tables (`grid.py`), Overview map (`nodemap.py`), Node (`node.py`) |
| `src/container_status_webpage/pages/` | `containers.py`: the pages Overview, Grid, Problems and Node (Dash Pages) |
| `src/container_status_webpage/assets/` | nne-viz style (`style.css`), logos, the Grid tooltip component (`dashAgGridComponentFunctions.js`), served by Dash |
| `tests/` | rules, cache, tables, node detail and smoke tests, without a browser; never import a page module |

Synthetic nodes worth opening (`/node?node=<id>`): 90019 mobile, 90020 release history, 90018 orphan threads,
90010 UDP Ping partial.
