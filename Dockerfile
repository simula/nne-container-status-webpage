# syntax=docker/dockerfile:1
# NNE container status webpage – development image (nginx / TLS is a separate step before deployment).
# nnedbtools is fetched from GitHub over SSH at build time: docker compose build (compose.yaml forwards the SSH agent).
FROM python:3.14-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends git openssh-client \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY src/ src/
RUN --mount=type=ssh mkdir -p -m 0700 /root/.ssh \
    && ssh-keyscan github.com >> /root/.ssh/known_hosts \
    && pip install --no-cache-dir .

RUN useradd --system --create-home app
USER app
# nnedbtools writes logs/ into the working directory: a directory the user app can write
WORKDIR /home/app
EXPOSE 8050
CMD ["gunicorn", "--bind", "0.0.0.0:8050", "--workers", "2", "container_status_webpage.app:server"]
