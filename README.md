# nne-container-status-webpage

<img src="documentation/nornet-logo.png" alt="NorNet logo" width="480">

Web dashboard of the NorNet Edge node containers: which docker containers and threads run on the reported nodes,
from the heartbeats in `report.container_rawdata` checked against the experiment setup in `nne`, read-only through
[nnedbtools](https://github.com/simula/nnedbtools). A Dash app with the look of nne-viz, to run detached on specula.

## HTTPS: install the certificate once

The webpage runs at https://specula.proxmox.crnalab.net/ (internal VPN). Its certificate is signed by the project's
own CA: install the CA certificate [deploy/nne-ca.crt](deploy/nne-ca.crt) once per browser, then the page opens
without a warning, also after the server certificate is renewed. Compare its SHA-256 fingerprint before you trust it
(`openssl x509 -in nne-ca.crt -noout -fingerprint -sha256`; Firefox shows it in the certificate viewer):

`23:20:D3:44:13:B9:9E:0F:F8:B2:F4:E4:45:48:97:E8:ED:18:63:BB:63:8F:ED:7D:EE:8C:75:35:69:AD:00:8E`

- **Chrome or Brave on macOS** (both use the macOS keychain): download `nne-ca.crt`, then

  ```sh
  security add-trusted-cert -r trustRoot -k ~/Library/Keychains/login.keychain-db ~/Downloads/nne-ca.crt
  ```

  (asks for your password), or open the file, find "NNE Container Status CA" in Keychain Access and set *Trust* →
  *When using this certificate*: *Always Trust*. Quit and restart the browser.
- **Firefox on Linux** (its own certificate store): *Settings* → *Privacy & Security* → *Certificates* → *View
  Certificates…* → *Authorities* → *Import…* → `nne-ca.crt` → tick *Trust this CA to identify websites*
  (tested with Firefox ESR 153 on Debian).

Without the certificate, http://10.133.14.66/ works (plain HTTP by IP address).

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
- Installation on specula (systemd, nginx): [documentation/INSTALLATION.md](documentation/INSTALLATION.md)
- Changes: [documentation/CHANGES.md](documentation/CHANGES.md)
