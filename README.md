# nne-container-status-webpage

<img src="documentation/nornet-logo.png" alt="NorNet logo" width="480">

Web dashboard of the NorNet Edge node containers: which docker containers and threads run on the reported nodes,
from the heartbeats in `report.container_rawdata` checked against the experiment setup in `nne`, read-only through
[nnedbtools](https://github.com/simula/nnedbtools). A Dash app with the look of nne-viz, to run detached on specula.

## Quick start

```bash
conda env create -f environment.yml
conda activate nne-container-status-webpage
container-status-webpage            # development server on http://localhost:8050, synthetic data
./build-web.sh                      # or the Docker container on the real data, read-only (DEVELOPMENT.md)
```

## Documentation

- Design, rules and code conventions: [documentation/DESIGN.md](documentation/DESIGN.md)
- Development (setup, run, tests, Docker): [documentation/DEVELOPMENT.md](documentation/DEVELOPMENT.md)
- Changes: [documentation/CHANGES.md](documentation/CHANGES.md)
