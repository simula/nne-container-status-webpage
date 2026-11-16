# syntax=docker/dockerfile:1
# Local stand-in for specula (DESIGN §11): Ubuntu with systemd, the service user webpage, the project in a virtual
# environment, the systemd unit and the nginx site of deploy/. Only for rehearsing the deployment – runs privileged.
#   ./build-deployment.sh   →  https://localhost:8443 (throwaway CA for localhost: the browser warns)
# nnedbtools is fetched from GitHub over SSH at build time (compose.yaml forwards the SSH agent).
FROM ubuntu:26.04

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        systemd systemd-sysv nginx python3 python3-venv git openssh-client ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --system --user-group --create-home webpage

WORKDIR /nne/nne-container-status-webpage
COPY pyproject.toml README.md LICENSE ./
COPY src/ src/
COPY deploy/ deploy/
RUN --mount=type=ssh mkdir -p -m 0700 /root/.ssh \
    && ssh-keyscan github.com >> /root/.ssh/known_hosts \
    && python3 -m venv .venv \
    && .venv/bin/pip install --no-cache-dir .

RUN cp deploy/nne-container-status-webpage.service deploy/nne-container-status-webpage-certificate.service deploy/nne-container-status-webpage-certificate.timer \
        /etc/systemd/system/ \
    && systemctl enable nne-container-status-webpage nne-container-status-webpage-certificate.timer \
    && cp deploy/nginx-site.conf /etc/nginx/sites-available/nne-container-status-webpage \
    && ln -s /etc/nginx/sites-available/nne-container-status-webpage /etc/nginx/sites-enabled/ \
    && rm /etc/nginx/sites-enabled/default

# CA and server certificate by the script of specula (INSTALLATION.md, TLS certificate), for the name localhost
RUN install -d -m 700 /etc/ssl/private \
    && NAME=localhost DOMAIN=localhost IP=127.0.0.1 deploy/make-certificates.sh \
    && mkdir /etc/systemd/system/nne-container-status-webpage-certificate.service.d \
    && printf '[Service]\nEnvironment=NAME=localhost DOMAIN=localhost IP=127.0.0.1\n' \
        > /etc/systemd/system/nne-container-status-webpage-certificate.service.d/localhost.conf

# Container only: the kernel belongs to the Docker host, loading kernel modules fails
RUN systemctl mask systemd-modules-load.service

EXPOSE 80 443
# systemd shuts down on SIGRTMIN+3, not on SIGTERM
STOPSIGNAL SIGRTMIN+3
CMD ["/sbin/init"]
