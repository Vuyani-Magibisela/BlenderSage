# SPDX-License-Identifier: GPL-3.0-or-later
FROM python:3.13-slim-bookworm

ARG BLENDER_VERSION=5.2.2
ARG USERNAME=dev
ARG USER_UID=1000
ARG USER_GID=1000

# Tools for fetching Blender, plus git for VS Code source control.
# Blender runtime libraries are added below this line, one per discovered need.
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      ca-certificates curl xz-utils git \
      libgl1 libice6 libsm6 libx11-6 libxext6 libxfixes3 libxi6 libxkbcommon0 libxrender1 \
 && rm -rf /var/lib/apt/lists/*

# Download Blender, verify against the official checksum, install to /opt/blender.
RUN set -eux; \
    series="${BLENDER_VERSION%.*}"; \
    base="https://download.blender.org/release/Blender${series}"; \
    archive="blender-${BLENDER_VERSION}-linux-x64.tar.xz"; \
    cd /tmp; \
    curl -fsSLO "${base}/${archive}"; \
    curl -fsSL "${base}/blender-${BLENDER_VERSION}.sha256" -o blender.sha256; \
    grep "  ${archive}\$" blender.sha256 > archive.sha256; \
    sha256sum -c archive.sha256; \
    mkdir -p /opt/blender; \
    tar -xJf "${archive}" -C /opt/blender --strip-components=1; \
    rm -f "${archive}" blender.sha256 archive.sha256; \
    ln -s /opt/blender/blender /usr/local/bin/blender

RUN groupadd --gid "${USER_GID}" "${USERNAME}" \
 && useradd --uid "${USER_UID}" --gid "${USER_GID}" --create-home --shell /bin/bash "${USERNAME}" \
 && mkdir -p /workspaces/BlenderSage \
 && chown "${USERNAME}:${USERNAME}" /workspaces/BlenderSage

ENV PATH="/home/${USERNAME}/.local/bin:${PATH}" \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /workspaces/BlenderSage
USER ${USERNAME}
