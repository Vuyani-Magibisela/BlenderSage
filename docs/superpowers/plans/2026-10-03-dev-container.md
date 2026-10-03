# Dev Container Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A VS Code Dev Container with Python 3.13, headless Blender 5.2.2 (Linux) and pytest, which can also be reached from the Windows host with `docker exec blendersage-dev ...`.

**Architecture:** The image is a `python:3.13-slim-bookworm` base with a checksum-verified Blender 5.2.2 tarball unpacked to `/opt/blender` and a non-root `dev` user. `devcontainer.json` names the container `blendersage-dev`, mounts the repo at `/workspaces/BlenderSage`, and installs `requirements-dev.txt` after the container is created. This repo has no product code yet, so the "tests" here are verification commands with exact expected output, run against the built image and the running container.

**Tech Stack:** Docker Desktop (Linux engine) on Windows 11, VS Code Dev Containers, Dev Containers CLI (`@devcontainers/cli`, run with `npx` for headless verification), Blender 5.2.2 LTS, Python 3.13, pytest, fake-bpy-module-5.2.

**Spec:** `docs/superpowers/specs/2026-10-03-dev-container-design.md`

## Global Constraints

- Base image: `python:3.13-slim-bookworm`.
- Blender: `blender-5.2.2-linux-x64.tar.xz` from `https://download.blender.org/release/Blender5.2/`, version as build `ARG BLENDER_VERSION=5.2.2`, verified against `blender-${BLENDER_VERSION}.sha256`; the build fails on mismatch.
- Blender unpacked to `/opt/blender`, symlinked to `/usr/local/bin/blender`.
- System libraries: only those headless `blender -b` needs; determined empirically.
- Non-root user `dev`, UID/GID 1000.
- Container name `blendersage-dev`; `remoteUser: dev`; `WORKDIR /workspaces/BlenderSage`.
- VS Code extensions: `ms-python.python`, `ms-python.vscode-pylance`.
- `postCreateCommand`: `pip install --user -r requirements-dev.txt`; `requirements-dev.txt` contains `pytest` and `fake-bpy-module-5.2`.
- fake-bpy-module is never installed into Blender's bundled Python.
- No port forwarding, no X11/Wayland forwarding, no GPU passthrough. No Compose, Node in the image, Claude Code CLI, or Blender GUI.
- Every source file the project owns carries `# SPDX-License-Identifier: GPL-3.0-or-later` where the format allows comments (Dockerfile, requirements file). JSON with comments (`devcontainer.json` is JSONC) gets `// SPDX-License-Identifier: GPL-3.0-or-later`.
- Git commits: no `Co-Authored-By` lines (CLAUDE.md rule).

**Spec deviation (flag to reviewer):** the spec lists a root `.dockerignore`. The build context in this plan is `.devcontainer/`, which holds only `Dockerfile` and `devcontainer.json`, and the Dockerfile copies nothing from the context. A root `.dockerignore` would have no effect and a `.devcontainer/.dockerignore` would have nothing to exclude, so it is omitted. If the context ever becomes the repo root, add one then.

## Review Focus

1. **Blender download is wrong or missing** (typo'd version, 404, truncated file) → the build must fail loudly, never produce an image without Blender. Pinned by Task 1 Step 6 (build with a non-existent version must fail).
2. **Python error inside Blender run via `docker exec`** → the host must see a non-zero exit code, or Claude Code on Windows will report failing Blender tests as passing. Pinned by Task 2 Step 6.
3. **Files on the Windows bind mount** → files created in the container must appear on Windows and Windows files must be writable by `dev`. Pinned by Task 2 Step 7.
4. **`core/` code importing `bpy` by mistake** → in this container `import bpy` succeeds through the fake stubs, so plain pytest would not catch it. Expected: `CLAUDE.md` warns about it, so whoever writes `core/` adds a guard test then. Pinned by Task 3 Step 1 (documentation; no `core/` exists yet to test).
5. **Container not running when Claude Code calls `docker exec`** → a clear "No such container" error, not a silent fallback to Windows tools. Documented in Task 3 Step 1; observed in Task 2 Step 9.

---

### Task 0: Branch

- [ ] **Step 1: Create a feature branch**

The repo is on `master`, and CLAUDE.md says to branch before committing work.

Run (repo root):
```bash
git switch -c dev-container
```
Expected: `Switched to a new branch 'dev-container'`

- [ ] **Step 2: Confirm Docker is running with the Linux engine**

Run:
```bash
docker info --format '{{.OSType}}'
```
Expected: `linux`. If it errors with `failed to connect to the docker API`, stop and ask the user to start Docker Desktop.

---

### Task 1: Image with Blender 5.2.2 and Python 3.13

**Files:**
- Create: `.devcontainer/Dockerfile`
- Create: `requirements-dev.txt`

**Interfaces:**
- Consumes: nothing.
- Produces: image tag `blendersage-dev:local` for verification only (VS Code builds its own tag from the same Dockerfile). Inside the image: `/usr/local/bin/blender` → `/opt/blender/blender`; `/usr/local/bin/python` (3.13); user `dev` (1000:1000) with `/home/dev/.local/bin` on `PATH`; working directory `/workspaces/BlenderSage`.

- [ ] **Step 1: Write `requirements-dev.txt`**

```text
# SPDX-License-Identifier: GPL-3.0-or-later
# Development-only dependencies for the dev container's Python.
# fake-bpy-module provides bpy stubs for editor autocompletion; never install it into Blender's bundled Python.
pytest
fake-bpy-module-5.2
```

- [ ] **Step 2: Write the Dockerfile with no Blender runtime libraries yet**

The spec requires the library list to be found by running Blender, so start with none.

`.devcontainer/Dockerfile`:
```dockerfile
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
```

Notes for the implementer:
- The `.sha256` file is LF-terminated with lines `<hash>  <filename>` (two spaces); verified on 2026-10-03. `grep` exits non-zero if the archive line is missing, and `set -e` then fails the build.
- `${BLENDER_VERSION%.*}` turns `5.2.2` into `5.2`. It works in `/bin/sh` (dash).

- [ ] **Step 3: Build and confirm Blender fails to start (expected, no libraries yet)**

Run (repo root):
```bash
docker build -t blendersage-dev:local .devcontainer
docker run --rm blendersage-dev:local blender -b --factory-startup --python-expr "import sys, bpy; print('VERIFY', bpy.app.version_string, sys.version)"
```
Expected: the build succeeds (and its log shows `blender-5.2.2-linux-x64.tar.xz: OK` from `sha256sum`). The run fails with `error while loading shared libraries: <libname>.so...: cannot open shared object file`.

If Blender starts and prints `VERIFY 5.2.2 LTS 3.13...`, no extra libraries are needed: skip to Step 5.

- [ ] **Step 4: Add libraries one at a time until Blender starts**

Loop:
1. List everything still missing at link time:
   ```bash
   docker run --rm blendersage-dev:local sh -c "ldd /opt/blender/blender | grep 'not found'"
   ```
2. Map each missing `.so` to its Debian bookworm package. Likely mappings:

   | Missing library | Package |
   |---|---|
   | `libX11.so.6` | `libx11-6` |
   | `libXi.so.6` | `libxi6` |
   | `libXxf86vm.so.1` | `libxxf86vm1` |
   | `libXfixes.so.3` | `libxfixes3` |
   | `libXrender.so.1` | `libxrender1` |
   | `libxkbcommon.so.0` | `libxkbcommon0` |
   | `libSM.so.6` | `libsm6` |
   | `libICE.so.6` | `libice6` |
   | `libGL.so.1` | `libgl1` |
   | `libEGL.so.1` | `libegl1` |
   | `libXext.so.6` | `libxext6` |
   | `libXrandr.so.2` | `libxrandr2` |

   For a library not in the table, find the package with `apt-file search <libname>` in a scratch `debian:bookworm` container, or from packages.debian.org.
3. Add the packages to the `apt-get install` line in alphabetical order, after `ca-certificates curl xz-utils git`.
4. Rebuild and rerun the Step 3 `docker run` command.

Repeat until `ldd` reports nothing missing **and** the Step 3 command prints the `VERIFY` line. Blender `dlopen`s some libraries at runtime (e.g. EGL), which `ldd` does not show, so the runtime error message is the final authority.

- [ ] **Step 5: Verify the finished image**

Run each command, then compare with the expected output:
```bash
docker run --rm blendersage-dev:local blender -b --factory-startup --python-expr "import sys, bpy; print('VERIFY', bpy.app.version_string, sys.version)"
```
Expected: a line starting `VERIFY 5.2.2 LTS 3.13.` (Blender's bundled Python, which is 3.13.13 on Windows; Linux should match).

```bash
docker run --rm blendersage-dev:local python --version
```
Expected: `Python 3.13.<n>`

```bash
docker run --rm blendersage-dev:local sh -c "id && pwd && readlink -f /usr/local/bin/blender"
```
Expected:
```
uid=1000(dev) gid=1000(dev) groups=1000(dev)
/workspaces/BlenderSage
/opt/blender/blender
```

- [ ] **Step 6: Review Focus 1 — a bad Blender version must fail the build**

Run:
```bash
docker build --build-arg BLENDER_VERSION=5.2.99 -t blendersage-dev:bad .devcontainer
```
Expected: the build **fails** at the Blender `RUN` step with `curl: (22) The requested URL returned error: 404`. Confirm no image was produced:
```bash
docker image inspect blendersage-dev:bad
```
Expected: `Error: No such image: blendersage-dev:bad` (or the equivalent "no such object" error).

- [ ] **Step 7: Commit**

```bash
git add .devcontainer/Dockerfile requirements-dev.txt
git commit -m "Add dev container image with Blender 5.2.2 and Python 3.13"
```

---

### Task 2: VS Code devcontainer configuration

**Files:**
- Create: `.devcontainer/devcontainer.json`

**Interfaces:**
- Consumes: `.devcontainer/Dockerfile` from Task 1 (user `dev`, `WORKDIR /workspaces/BlenderSage`, `/home/dev/.local/bin` on `PATH`).
- Produces: a running container named `blendersage-dev` with the repo mounted at `/workspaces/BlenderSage`, and `pytest` plus `fake-bpy-module-5.2` installed for user `dev`. Task 3 documents these commands.

- [ ] **Step 1: Write `devcontainer.json`**

`.devcontainer/devcontainer.json`:
```jsonc
// SPDX-License-Identifier: GPL-3.0-or-later
{
  "name": "BlenderSage",
  "build": {
    "dockerfile": "Dockerfile",
    "context": "."
  },
  "runArgs": ["--name", "blendersage-dev"],
  "workspaceMount": "source=${localWorkspaceFolder},target=/workspaces/BlenderSage,type=bind",
  "workspaceFolder": "/workspaces/BlenderSage",
  "remoteUser": "dev",
  "postCreateCommand": "pip install --user -r requirements-dev.txt",
  "customizations": {
    "vscode": {
      "extensions": [
        "ms-python.python",
        "ms-python.vscode-pylance"
      ],
      "settings": {
        "python.defaultInterpreterPath": "/usr/local/bin/python"
      }
    }
  }
}
```

`workspaceMount` and `workspaceFolder` are set explicitly so the mount path never depends on the folder name on the host, which keeps `WORKDIR` and `docker exec` consistent.

- [ ] **Step 2: Bring the container up headlessly with the Dev Containers CLI**

This uses the same engine VS Code uses, so the result matches "Reopen in Container". It needs Node (installed on the host) and is run with `npx` without a global install.

Run (repo root, from the Windows host):
```bash
npx -y @devcontainers/cli@latest up --workspace-folder .
```
Expected: the build output, then the `postCreateCommand` output ending in `Successfully installed ... fake-bpy-module-5.2-... pytest-...`, then a JSON line containing `"outcome":"success"`.

If it fails because a container named `blendersage-dev` already exists (e.g. from an earlier attempt), remove it with `docker rm -f blendersage-dev` and rerun.

- [ ] **Step 3: Verify the container from the host**

Run:
```bash
docker exec blendersage-dev sh -c "id -un && pwd"
```
Expected:
```
dev
/workspaces/BlenderSage
```

```bash
docker exec blendersage-dev ls
```
Expected: the repo contents, including `CLAUDE.md`, `docs` and `requirements-dev.txt`.

- [ ] **Step 4: Verify pytest from the host**

Run:
```bash
docker exec blendersage-dev python -m pytest --version
```
Expected: `pytest <version>`

- [ ] **Step 5: Verify the bpy stubs (spec verification 3)**

Run:
```bash
docker exec blendersage-dev python -c "import bpy; print(bpy.__file__)"
```
Expected: a path under `/home/dev/.local/lib/python3.13/site-packages/bpy/`. That shows the stubs are in the container's Python, not Blender's.

Then confirm Blender's own Python does **not** see the stubs:
```bash
docker exec blendersage-dev blender -b --factory-startup --python-expr "import bpy; print('REAL', bpy.__file__)"
```
Expected: a `REAL` line whose path is not under `/home/dev/.local`. In real Blender, `bpy.__file__` may be `None` or a path inside `/opt/blender`; either is fine.

- [ ] **Step 6: Review Focus 2 — a Python error in Blender gives a non-zero exit code on the host**

Run (bash on Windows):
```bash
docker exec blendersage-dev blender -b --factory-startup --python-exit-code 1 --python-expr "1/0"; echo "exit=$?"
```
Expected: a `ZeroDivisionError` traceback, then `exit=1`.

Then the success case:
```bash
docker exec blendersage-dev blender -b --factory-startup --python-exit-code 1 --python-expr "print('ok')"; echo "exit=$?"
```
Expected: `ok`, then `exit=0`.

- [ ] **Step 7: Review Focus 3 — round-trip files through the bind mount (spec verification 4)**

Run:
```bash
docker exec blendersage-dev sh -c "echo from-container > .mount-check-container.txt"
cat .mount-check-container.txt
```
Expected: `from-container` (Windows sees the file the container created).

```bash
echo from-host > .mount-check-host.txt
docker exec blendersage-dev sh -c "cat .mount-check-host.txt && echo appended >> .mount-check-host.txt && cat .mount-check-host.txt && ls -n .mount-check-host.txt"
```
Expected: `from-host`, then `from-host` and `appended`, then an `ls -n` line. On Docker Desktop's Windows bind mounts the owner normally shows as `1000 1000` or `0 0`; either is acceptable **as long as the append succeeded**. Record which one appears.

Clean up:
```bash
rm .mount-check-container.txt .mount-check-host.txt
```

- [ ] **Step 8: Rebuild check (spec: image usable without manual steps)**

Run:
```bash
docker rm -f blendersage-dev
npx -y @devcontainers/cli@latest up --workspace-folder .
docker exec blendersage-dev python -m pytest --version
```
Expected: `"outcome":"success"`, then `pytest <version>`. This proves a fresh container comes up working without manual steps.

- [ ] **Step 9: Review Focus 5 — behaviour when the container is stopped**

Run:
```bash
docker stop blendersage-dev
docker exec blendersage-dev python --version; echo "exit=$?"
docker start blendersage-dev
```
Expected: an error saying the container is not running, and a non-zero `exit=`. Record the exact message for Task 3. Leave the container started.

- [ ] **Step 10: Commit**

```bash
git add .devcontainer/devcontainer.json
git commit -m "Add VS Code devcontainer configuration"
```

---

### Task 3: Document the container in CLAUDE.md

**Files:**
- Modify: `CLAUDE.md` (the `## Testing` section, after the extension packaging bullet)

**Interfaces:**
- Consumes: container name `blendersage-dev`, workspace `/workspaces/BlenderSage`, and the stopped-container message recorded in Task 2 Step 9.
- Produces: documentation only.

- [ ] **Step 1: Add the container section**

Insert this as a new subsection at the end of `## Testing` (before `## Working style`). Replace `<message from Task 2 Step 9>` with the exact text recorded there.

```markdown
### Dev container

The repo has a VS Code Dev Container (`.devcontainer/`): Python 3.13, headless Blender 5.2.2 for Linux, pytest, and `fake-bpy-module-5.2` stubs. Open it with **Dev Containers: Reopen in Container**. The container is always named `blendersage-dev` and mounts the repo at `/workspaces/BlenderSage`.

From the Windows host (e.g. Claude Code), with the container running:

- Unit tests: `docker exec blendersage-dev python -m pytest tests/unit`
- Headless Blender: `docker exec blendersage-dev blender -b --factory-startup --python-exit-code 1 --python tests/blender/run_all.py`
- Start it without VS Code: `npx -y @devcontainers/cli@latest up --workspace-folder .`

If the container is stopped, `docker exec` fails with `<message from Task 2 Step 9>`. Start it (`docker start blendersage-dev`) rather than falling back to Windows tools without saying so.

Limits:
- The container can't test UI, overlay, display scaling or Windows behaviour. Use the Windows Blender 5.2 install and the manual checklist for those.
- `import bpy` **succeeds** in the container's plain Python because of the stubs, so pytest alone won't catch a `bpy` import in `core/`. When `core/` is created, add a unit test that fails if any `core/` module imports `bpy`.
- To change the Blender version, edit `ARG BLENDER_VERSION` in `.devcontainer/Dockerfile` and rebuild.
```

- [ ] **Step 2: Check the section matches reality**

Run both documented commands that don't need test files yet:
```bash
docker exec blendersage-dev python -m pytest --version
docker exec blendersage-dev blender -b --factory-startup --python-exit-code 1 --python-expr "print('ok')"
```
Expected: `pytest <version>`, then `ok`.

- [ ] **Step 3: Commit**

`CLAUDE.md` is currently untracked. Before adding it, confirm with the user that committing the whole file is wanted (it also contains earlier, uncommitted edits). If the user says no, skip this commit and report the section as an uncommitted change.

```bash
git add CLAUDE.md
git commit -m "Document dev container usage in CLAUDE.md"
```

---

### Task 4: Hand-off check in VS Code (manual, by the user)

Docker can't verify this headlessly, so the user does it and reports back.

- [ ] **Step 1: User opens the repo in VS Code and runs "Dev Containers: Reopen in Container"**

Expected: the window reopens with "Dev Container: BlenderSage" in the bottom-left corner, and the Python and Pylance extensions are installed in the container.

- [ ] **Step 2: User checks autocompletion**

In a scratch file in the container (e.g. `spikes/_scratch.py`, deleted afterwards), type `import bpy` then `bpy.context.` on the next line.
Expected: completions such as `active_object` and `scene` appear.

- [ ] **Step 3: Record results**

Report both results in the conversation. If anything fails, debug it before closing the branch.
