# Dev Container — Design

Date: 2026-10-03
Status: Approved (2026-10-03)

## Purpose

A reproducible Linux development environment for this Blender extension, opened from VS Code with **Reopen in Container**. It runs pure-Python unit tests and headless Blender 5.2 tests/spikes identically every time.

## Agreed scope

- **User:** the developer, working through VS Code Dev Containers.
- **Claude Code** keeps running on the Windows host and runs commands inside the container with `docker exec blendersage-dev ...`. Claude Code is not installed in the image.
- **Not covered by the container:** viewport overlay, display scaling, UI behaviour, and anything Windows-specific. These stay in the Windows install of Blender 5.2 (`D:\Program Files\Blender Foundation\Blender 5.2\blender.exe`) and the manual checklist in `docs/m1-findings.md`, as `CLAUDE.md` requires.
- **Assumption:** single developer. Lab machines and CI are out of scope, though the image should be usable by CI later without changes.

## Files

| File | Purpose |
|---|---|
| `.devcontainer/Dockerfile` | Builds the image. |
| `.devcontainer/devcontainer.json` | VS Code configuration, container name, extensions, post-create step. |
| `requirements-dev.txt` | Python development dependencies, installed into the container's Python. |
| `.dockerignore` | Keeps `.git`, caches and build output out of the build context. |
| `CLAUDE.md` | Adds a short section with the container commands. |

## Image

- **Base:** `python:3.13-slim-bookworm`. Python 3.13 matches the interpreter bundled with Blender 5.2 (verified on Windows: 3.13.13), so `core/` is unit-tested on the same minor version Blender runs.
- **Blender:** `blender-5.2.2-linux-x64.tar.xz` from `https://download.blender.org/release/Blender5.2/`, matching the Windows install. The version is a build `ARG BLENDER_VERSION=5.2.2`.
  - Verify the archive against `blender-${BLENDER_VERSION}.sha256` from the same directory; the build fails on mismatch.
  - Unpack to `/opt/blender`, symlink `/usr/local/bin/blender`.
- **System libraries:** only those headless `blender -b` needs to start. The list is determined empirically by building and running Blender, not guessed, and each package stays only if removing it breaks startup.
- **User:** non-root `dev`, UID/GID 1000, so files created in the bind-mounted workspace have sensible ownership.
- **Python dependencies:** `requirements-dev.txt` contains `pytest` and `fake-bpy-module-5.2` (PyPI package confirmed to exist on 2026-10-03; provides `bpy` stubs for editor autocompletion only — it is never imported at runtime and must not be installed into Blender's bundled Python).

## VS Code configuration (`devcontainer.json`)

- Build from `.devcontainer/Dockerfile`.
- `runArgs: ["--name", "blendersage-dev"]` so host-side commands can target a fixed name.
- `remoteUser: dev`.
- Extensions: `ms-python.python`, `ms-python.vscode-pylance`.
- Python interpreter: the image's `/usr/local/bin/python`.
- `postCreateCommand`: `pip install --user -r requirements-dev.txt` (keeps dependency changes out of the image rebuild loop).
- No port forwarding, no X11/Wayland forwarding, no GPU passthrough.

## Host-side usage (for Claude Code and the developer)

With the container running (opened in VS Code):

```
docker exec blendersage-dev python -m pytest tests/unit
docker exec blendersage-dev blender -b --factory-startup --python-exit-code 1 --python tests/blender/run_all.py
```

The Dockerfile sets `WORKDIR /workspaces/BlenderSage` (the path VS Code mounts the repo at), so `docker exec` runs from the repo root without `-w`. Commands run as `dev`, so the `pip install --user` packages are on its path.

## Explicitly out of scope

- Installing or enabling the extension inside the container's Blender. There is no `blender_manifest.toml` until Milestone 1 Step 1; that step adds it.
- Linters/formatters (none chosen for the project yet).
- Docker Compose, Node.js, Claude Code CLI, Blender GUI in the container.

## Verification

Docker Desktop must be running (Linux engine). Build the image, start the container, and capture real output of:

1. `blender -b --factory-startup --python-expr "import sys, bpy; print(bpy.app.version_string, sys.version)"` → expects `5.2.2 LTS` and Python 3.13.
2. `python --version` and `python -m pytest --version`.
3. `python -c "import bpy"` in the container's Python resolves to the fake stubs (autocompletion check).
4. A file written in the container appears in the Windows workspace and vice versa, owned by `dev`.
5. `docker exec blendersage-dev ...` works from the Windows host.

Results are reported in the conversation; any surprise (missing libraries, line-ending issues on the bind mount) is fixed and noted in `CLAUDE.md` if it affects future work.

## Risks

- **Line endings:** the workspace is on Windows; Git is configured with `core.autocrlf` behaviour that converts to CRLF (seen as a warning on `CLAUDE.md`). Shell scripts executed in the container would break with CRLF. The design avoids shell scripts in the repo; if one becomes necessary, add a `.gitattributes` rule (`*.sh text eol=lf`).
- **Bind-mount performance:** Windows-to-Linux bind mounts are slower than native files. Acceptable for this project's size; revisit only if test runs become noticeably slow.
- **Download availability:** the build depends on download.blender.org. If that becomes a problem, cache the archive; not needed now.
