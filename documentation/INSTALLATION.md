# Installation

The webpage runs on specula as the service user `webpage`: gunicorn on `127.0.0.1:8050`, run by systemd, behind nginx
with HTTPS on port 443 (design: [DESIGN.md section 11](DESIGN.md#11-deployment-on-specula)). `./build-deployment.sh` rehearses
these steps locally in a container (Local rehearsal below).

## Prerequisites (once per machine, with sudo)

```sh
sudo apt-get update
sudo apt-get install -y nginx python3-venv git
python3 --version                      # 3.14 or newer
```

Ubuntu 26.04 ships Python 3.14. On Ubuntu 24.04 (Python 3.12) install Python 3.14 with uv as
nne-container-status-importer does (its `documentation/INSTALLATION.md`, Prerequisites) and create the virtual
environment below with `uv venv --python 3.14.4 .venv` and `uv pip install --python .venv/bin/python .`.

The env file names the database host (`NNE_DB_*`, `REPORT_DB_*`); specula must resolve it: `getent hosts <host>`. If
not, add it to `/etc/hosts` as the importer does on oculus.

## Service user

```sh
sudo useradd --system --user-group --create-home webpage     # user and group webpage, home /home/webpage
```

The service runs in `/home/webpage`: nnedbtools creates an empty `logs/` there; the log records go to the journal.

## Virtual environment with the project and nnedbtools

`/nne` must exist and be writable by the deploying user. The project installs nnedbtools from GitHub over SSH, pinned
in `pyproject.toml` to a release tag: the deploying user needs a key with access to `simula/nnedbtools` and
`simula/nne-container-status-webpage`, e.g. a forwarded agent (`ssh -A specula`).

Agent forwarding for every login to specula, in `~/.ssh/config` on the Mac (`ForwardAgent yes` is `-A`):

```
Host specula
  HostName specula.proxmox.crnalab.net
  User <user>
  ForwardAgent yes
```

The key must be in the Mac's agent (`ssh-add -l`; after a restart `ssh-add --apple-load-keychain`); on specula
`ssh-add -l` lists it and `ssh -T git@github.com` greets you. Without it `git clone`, `git pull` (Update) and
`pip install .` fail with `Permission denied (publickey)`. While you are logged in, root on specula can use the
forwarded agent.

```sh
git clone git@github.com:simula/nne-container-status-webpage.git /nne/nne-container-status-webpage
cd /nne/nne-container-status-webpage
python3 -m venv .venv
.venv/bin/pip install .
.venv/bin/gunicorn --version
```

`.venv` is ignored by git. The user `webpage` only reads the checkout.

## Database env file

The nnedbtools env file of the read-only account `nne-specula`: the keys `NNE_DB_*` and `REPORT_DB_*`, no SSL paths
(nnedbtools uses its bundled Apollo CA / CRL). The account needs SELECT on the tables of DESIGN section 2 and nothing
else. The file is never committed.

```sh
sudo -u webpage mkdir -p -m 700 /home/webpage/.config/nne-container-status-webpage
sudo install -o webpage -g webpage -m 600 <prepared env file> /home/webpage/.config/nne-container-status-webpage/db_env
```

## Service (with sudo)

`deploy/nne-container-status-webpage.service` runs `gunicorn --bind 127.0.0.1:8050 --workers 2` as `webpage` with
`DATA_SOURCE=database` and `DB_ENV_FILE` set to the file above, restarted on failure. Without `DEBUG` the pages show
no data line.

```sh
sudo cp deploy/nne-container-status-webpage.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now nne-container-status-webpage
systemctl status nne-container-status-webpage
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8050/    # 200 after a few seconds
```

Other settings (`CONTAINERS_CACHE_MINUTES`, DESIGN section 10) as `Environment=` lines in an override:
`sudo systemctl edit nne-container-status-webpage`.

## TLS certificate (with sudo)

nginx serves HTTPS with a self-signed certificate for `specula.proxmox.crnalab.net`: there is no internal CA, and a
public CA cannot reach the VPN-only host. It is valid 825 days, the longest macOS accepts for a certificate trusted by
hand; the key stays on specula, readable by root only.

```sh
sudo openssl req -x509 -newkey rsa:3072 -sha256 -days 825 -nodes \
  -subj "/CN=specula.proxmox.crnalab.net" \
  -addext "subjectAltName=DNS:specula.proxmox.crnalab.net" -addext "extendedKeyUsage=serverAuth" \
  -keyout /etc/ssl/private/nne-container-status-webpage.key \
  -out /etc/ssl/certs/nne-container-status-webpage.crt
sudo chmod 600 /etc/ssl/private/nne-container-status-webpage.key
openssl x509 -in /etc/ssl/certs/nne-container-status-webpage.crt -noout -enddate -fingerprint -sha256
```

## nginx (with sudo)

`deploy/nginx-site.conf` serves HTTPS on port 443 with the certificate above and forwards to gunicorn; port 80 only
redirects to HTTPS. Access control is open (DESIGN section 12): the page shows ICCIDs, so it must stay on the internal
VPN until then.

```sh
sudo cp deploy/nginx-site.conf /etc/nginx/sites-available/nne-container-status-webpage
sudo ln -s /etc/nginx/sites-available/nne-container-status-webpage /etc/nginx/sites-enabled/
sudo rm /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx
curl -s -o /dev/null -w "%{http_code}\n" --cacert /etc/ssl/certs/nne-container-status-webpage.crt https://specula.proxmox.crnalab.net/   # 200
curl -s -o /dev/null -w "%{http_code}\n" http://localhost/          # 301 to HTTPS
```

## Trust the certificate (each viewer's Mac, once)

On the VPN; the fingerprint must match the one printed on specula:

```sh
openssl s_client -connect specula.proxmox.crnalab.net:443 -servername specula.proxmox.crnalab.net </dev/null \
  | openssl x509 > ~/Downloads/specula.crt
openssl x509 -in ~/Downloads/specula.crt -noout -fingerprint -sha256
sudo security add-trusted-cert -d -r trustRoot -k /Library/Keychains/System.keychain ~/Downloads/specula.crt
```

Then https://specula.proxmox.crnalab.net/ opens without a warning. Renewal before the end date: the `openssl req` and
`chmod` above, `sudo systemctl reload nginx`, and every viewer trusts the new certificate the same way.

## Logs

```sh
journalctl -u nne-container-status-webpage -f      # gunicorn and the application, nnedbtools included
sudo tail -f /var/log/nginx/error.log              # nginx; 502 while gunicorn starts
```

## Update

```sh
cd /nne/nne-container-status-webpage
git pull
.venv/bin/pip install .
sudo systemctl restart nne-container-status-webpage
```

When `deploy/` changed, copy the unit or the site again as above, then `sudo systemctl daemon-reload` or
`sudo nginx -t && sudo systemctl reload nginx`.

## Local rehearsal

`./build-deployment.sh` (development Mac, [DEVELOPMENT.md](DEVELOPMENT.md)) builds
`deploy/deployment-environment.Dockerfile`: Ubuntu 26.04 with systemd, the steps above with the same unit and site,
`./.db_env_deployement` mounted as the env file. https://localhost:8443 reaches nginx on port 443 with a throwaway
certificate for `localhost` (the browser warns, curl needs `-k`). The container runs
privileged and is for local use only; `systemd-modules-load` is masked there because a container cannot load kernel
modules.

```sh
docker compose --profile deploy exec deployment-environment systemctl status nne-container-status-webpage nginx
docker compose --profile deploy exec deployment-environment journalctl -u nne-container-status-webpage
docker compose --profile deploy down
```
