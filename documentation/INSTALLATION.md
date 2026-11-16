# Installation

The webpage runs on specula as the service user `webpage`: gunicorn on `127.0.0.1:8050`, run by systemd, behind nginx
on ports 80 and 443 (design: [DESIGN.md section 11](DESIGN.md#11-deployment-on-specula)). Users open
https://specula.proxmox.crnalab.net/ after installing the CA certificate once
([README.md](../README.md#https-install-the-certificate-once)); without it http://10.133.14.66/ works: browsers switch
the name to HTTPS but keep plain HTTP for an IP address.

First installation: sections 1–10 in order. `./build-deployment.sh` rehearses sections 3–9 locally in a container
(Local rehearsal). Blocks marked *Mac* run in the Mac's terminal: zsh there takes `#` as a comment only after
`setopt interactivecomments`, so those blocks carry no comments. All other blocks run on specula.

## 1. SSH access with agent forwarding

specula fetches the project and nnedbtools from GitHub over SSH with your key, forwarded from the Mac (no key is stored
on specula). `~/.ssh/config` on the Mac (`ForwardAgent yes` is `ssh -A`):

```
Host specula
  HostName specula.proxmox.crnalab.net
  User <user on specula>
  ForwardAgent yes
```

Add `IdentityFile <key>` if the login to specula needs a particular key. Check (*Mac*):

```sh
ssh -G specula | grep -i forwardagent
ssh-add -l
```

The first prints `forwardagent yes`, the second lists the key registered on GitHub (after a restart of the Mac the
agent may be empty: `ssh-add --apple-load-keychain`). A changed config applies only to new logins. Then on specula
(`ssh specula`):

```sh
ssh-add -l                  # the same key as on the Mac
ssh -T git@github.com       # "Hi <name>! You've successfully authenticated"
```

The first connection asks to confirm GitHub's host key; its published ED25519 fingerprint is
`SHA256:+DiY3wvvV6TuJJhbpZisF/zLDA0zPMSvHdkr4UvCOqU`. Without the forwarded key, `git clone`, `git pull` and
`pip install .` fail with `Permission denied (publickey)`. While you are logged in, root on specula can use the
forwarded agent.

## 2. Server checks

```sh
lsb_release -ds; python3 --version                                    # Ubuntu 26.04, Python 3.14 or newer
getent ahosts apollo.backend.crnalab.net                              # database host, IPv4 and IPv6
timeout 3 bash -c '</dev/tcp/apollo.backend.crnalab.net/3306' && echo "3306 open"
sudo -v && echo "sudo ok"
```

The env file connects to `apollo.backend.crnalab.net`. `apollo.nntb.no`, which nnedbtools logs as `*_DB_SERVERNAME`,
is a name used inside nnedbtools and need not resolve. Ubuntu 24.04 ships Python 3.12: install Python 3.14 with uv as
nne-container-status-importer does (its `documentation/INSTALLATION.md`, Prerequisites) and create the virtual
environment in section 5 with `uv venv --python 3.14.4 .venv` and `uv pip install --python .venv/bin/python .`.

## 3. Packages (sudo)

```sh
sudo apt-get update
sudo apt-get install -y nginx python3-venv git
```

nginx starts with its default page on port 80 until section 9 replaces it.

## 4. Service user and checkout directory (sudo)

```sh
sudo useradd --system --user-group --create-home webpage     # user and group webpage, home /home/webpage
sudo install -d -o "$USER" -g "$USER" /nne                    # checkout directory, writable by you
id webpage; ls -ld /nne /home/webpage
```

The service runs in `/home/webpage`: nnedbtools creates an empty `logs/` there; the log records go to the journal.

## 5. Checkout and virtual environment

nnedbtools comes from GitHub over SSH (section 1), pinned in `pyproject.toml` to a release tag.

```sh
git clone git@github.com:simula/nne-container-status-webpage.git /nne/nne-container-status-webpage
cd /nne/nne-container-status-webpage
python3 -m venv .venv
.venv/bin/pip install .
.venv/bin/gunicorn --version
```

`.venv` is ignored by git. The user `webpage` only reads the checkout.

## 6. Database env file

The nnedbtools env file of the read-only account `nne-specula`: the keys `NNE_DB_*` and `REPORT_DB_*`, no SSL paths
(nnedbtools uses its bundled Apollo CA / CRL). The account needs SELECT on the tables of DESIGN section 2 and nothing
else. On the development Mac it is `.db_env_deployement` ([DEVELOPMENT.md](DEVELOPMENT.md#env-files-db_env)); it is
never committed or printed. Copy it into your home on specula; `-p` keeps its mode 600 (*Mac*, repository root):

```sh
scp -p .db_env_deployement specula:db_env.tmp
```

```sh
sudo -u webpage mkdir -p -m 700 /home/webpage/.config/nne-container-status-webpage
sudo install -o webpage -g webpage -m 600 ~/db_env.tmp /home/webpage/.config/nne-container-status-webpage/db_env
rm ~/db_env.tmp
sudo ls -l /home/webpage/.config/nne-container-status-webpage/      # db_env, webpage webpage, -rw-------
```

## 7. Service (sudo)

`deploy/nne-container-status-webpage.service` runs `gunicorn --bind 127.0.0.1:8050 --workers 2` as `webpage` with
`DATA_SOURCE=database` and `DB_ENV_FILE` set to the file above, restarted on failure. Without `DEBUG` the pages show
no data line.

```sh
sudo cp deploy/nne-container-status-webpage.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now nne-container-status-webpage
systemctl status nne-container-status-webpage --no-pager | head -5          # active (running)
sleep 10; curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8050/_dash-layout     # 200; loads the data
sudo journalctl -u nne-container-status-webpage -o cat | grep -E 'SUCCESS|Traceback'
```

Expected: `SUCCESS NNE Engine connected` and `SUCCESS Report Engine connected`. Known and harmless:
`FAILURE … ROOT Engine NOT connected` (no root credentials) and, at each worker start, lines
`ERROR - -- Parsing value failed NNE_DB_*` (DESIGN section 12).

Other settings (`CONTAINERS_CACHE_MINUTES`, DESIGN section 10) as `Environment=` lines in an override:
`sudo systemctl edit nne-container-status-webpage`.

## 8. TLS certificate and yearly renewal (sudo)

nginx serves HTTPS on port 443 with a server certificate signed by a CA of this project; users install the CA
certificate once. `deploy/make-certificates.sh` creates the CA on its first run (10 years; it may only sign names under
`crnalab.net` and the address `10.133.14.66`) and on every run a new server certificate for
`specula.proxmox.crnalab.net` and `10.133.14.66` (825 days, the longest macOS accepts). The keys stay on specula,
readable by root only. `nne-container-status-webpage-certificate.timer` runs the script once a year and reloads nginx,
so the server certificate never expires and users install nothing; the script replaces the served files only after
the new certificate verifies.

```sh
sudo deploy/make-certificates.sh      # prints the verification, the CA fingerprint and the end dates
sudo cp deploy/nne-container-status-webpage-certificate.service deploy/nne-container-status-webpage-certificate.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now nne-container-status-webpage-certificate.timer
systemctl list-timers nne-container-status-webpage-certificate.timer      # next run: 1 January
```

Test run of the renewal (done on specula on 2026-11-16):
`sudo systemctl start nne-container-status-webpage-certificate.service`, then
`systemctl show -p Result nne-container-status-webpage-certificate.service` shows `Result=success`; users notice
nothing.

**First installation only (a new CA):** its certificate goes into the repository, where users get it. Copy it and
compare its fingerprint with the one the script printed (*Mac*, repository root):

```sh
scp specula:/etc/ssl/certs/nne-ca.crt deploy/nne-ca.crt
openssl x509 -in deploy/nne-ca.crt -noout -fingerprint -sha256
```

Then write the fingerprint into README.md (section "HTTPS: install the certificate once") and commit both.

**Reinstallation with the same CA:** put the CA key and certificate in place before the script
(`/etc/ssl/private/nne-ca.key`, mode 600, and `/etc/ssl/certs/nne-ca.crt`); the script then only issues a server
certificate and users install nothing. Without the old key the script creates a new CA, and every user installs again.
The CA expires in 2036. A publicly trusted certificate needs Let's Encrypt with the DNS-01 challenge in the Cloudflare
zone `crnalab.net` (an API token with DNS edit rights): DESIGN section 12.

## 9. nginx (sudo)

`deploy/nginx-site.conf` forwards port 80 (HTTP) and port 443 (HTTPS, the certificate above) to gunicorn. Access is
limited to the internal VPN (decision 2026-11-16, DESIGN section 12): everyone on it may see the ICCIDs; no login.

```sh
sudo cp deploy/nginx-site.conf /etc/nginx/sites-available/nne-container-status-webpage
sudo ln -s /etc/nginx/sites-available/nne-container-status-webpage /etc/nginx/sites-enabled/
sudo rm /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx
ls /etc/nginx/sites-enabled/                      # only nne-container-status-webpage
curl -s -o /dev/null -w "%{http_code}\n" --cacert /etc/ssl/certs/nne-ca.crt https://specula.proxmox.crnalab.net/_dash-layout   # 200
curl -s -o /dev/null -w "%{http_code}\n" http://localhost/_dash-layout                                                         # 200
```

`/_dash-layout` answers 200 only through gunicorn; `/` gets 200 from nginx's default page as well. Both must also
answer 200 from the Mac (*Mac*, repository root):

```sh
curl -s -o /dev/null -w "%{http_code}\n" --cacert deploy/nne-ca.crt https://specula.proxmox.crnalab.net/_dash-layout
curl -s -o /dev/null -w "%{http_code}\n" http://10.133.14.66/_dash-layout
```

## 10. Users

Every user installs the CA certificate once: [README.md](../README.md#https-install-the-certificate-once) (Chrome and
Brave on macOS, Firefox on Linux). Then https://specula.proxmox.crnalab.net/ opens without a warning.

## Logs

The journal of a system service needs `sudo`, or once `sudo usermod -aG adm <user>` (applies from the next login), then
without `sudo`.

```sh
sudo journalctl -u nne-container-status-webpage -f            # gunicorn and the application, nnedbtools included
sudo journalctl -u nne-container-status-webpage-certificate   # yearly certificate renewal
sudo tail -f /var/log/nginx/error.log                         # nginx; 502 while gunicorn starts
```

## Update

Log in with `ssh specula` (agent forwarded, section 1):

```sh
cd /nne/nne-container-status-webpage
git pull --ff-only
.venv/bin/pip install .
sudo systemctl restart nne-container-status-webpage
```

When `deploy/` changed, copy the changed files again as in sections 7–9: units, then `sudo systemctl daemon-reload`
and a restart; the site, then `sudo nginx -t && sudo systemctl reload nginx`.

## Local rehearsal

`./build-deployment.sh` (development Mac, [DEVELOPMENT.md](DEVELOPMENT.md)) builds
`deploy/deployment-environment.Dockerfile`: Ubuntu 26.04 with systemd, sections 3–9 with the same units and site,
`./.db_env_deployement` mounted as the env file. https://localhost:8443 reaches nginx on port 443 with a certificate of
a throwaway CA for `localhost`, made by the same script (the browser warns, curl needs `-k`). The container runs
privileged and is for local use only; `systemd-modules-load` is masked there because a container cannot load kernel
modules.

```sh
docker compose --profile deploy exec deployment-environment systemctl status nne-container-status-webpage nginx
docker compose --profile deploy exec deployment-environment journalctl -u nne-container-status-webpage
docker compose --profile deploy down
```
