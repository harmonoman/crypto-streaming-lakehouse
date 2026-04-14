# ── Dev Container — Crypto Streaming Pipeline ────────────────────────────────
FROM python:3.11-slim

ARG DEBIAN_FRONTEND=noninteractive

# ── System dependencies ───────────────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
      git \
      curl \
      build-essential \
      libpq-dev \
      procps \
      sudo \  
      ca-certificates \
      gnupg \
      lsb-release \
  && install -m 0755 -d /etc/apt/keyrings \
  && curl -fsSL https://download.docker.com/linux/debian/gpg \
       | gpg --dearmor -o /etc/apt/keyrings/docker.gpg \
  && chmod a+r /etc/apt/keyrings/docker.gpg \
  && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
       https://download.docker.com/linux/debian $(lsb_release -cs) stable" \
       > /etc/apt/sources.list.d/docker.list \
  && apt-get update \
  && apt-get install -y --no-install-recommends \
       docker-ce-cli \
       docker-compose-plugin \
  && apt-get clean \
  && rm -rf /var/lib/apt/lists/*

# ── Non-root user ─────────────────────────────────────────────────────────────
ARG USERNAME=vscode
ARG USER_UID=1000
ARG USER_GID=1000

RUN groupadd --gid ${USER_GID} ${USERNAME} \
  && useradd --uid ${USER_UID} --gid ${USER_GID} --shell /bin/bash --create-home ${USERNAME} \
  && groupadd -f docker \
  && usermod -aG docker ${USERNAME} \
  && echo "${USERNAME} ALL=(root) NOPASSWD:/bin/chown" >> /etc/sudoers.d/vscode-docker \
  && chmod 0440 /etc/sudoers.d/vscode-docker

# ── uv ────────────────────────────────────────────────────────────────────────
# Install uv system-wide as root. Pinned — bump deliberately.
#
# IMPORTANT: Do NOT set UV_PROJECT_ENVIRONMENT, VIRTUAL_ENV, or WORKDIR to any
# path under the workspace here. The workspace is mounted by Dev Containers
# AFTER the image is built — those paths don't exist at build time and any
# ENVs pointing there would be stale or empty.
# All workspace-relative config lives in devcontainer.json instead.
ARG UV_VERSION=0.4.18
RUN curl -LsSf https://astral.sh/uv/install.sh | UV_VERSION=${UV_VERSION} sh \
  && mv /root/.local/bin/uv /usr/local/bin/uv \
  && chmod +x /usr/local/bin/uv

WORKDIR /home/vscode

USER vscode

CMD ["bash"]
