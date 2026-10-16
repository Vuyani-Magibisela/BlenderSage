# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# Open Teaching Extension for Blender

## What this project is

A free, open-source Blender extension that lets teachers create guided lessons inside Blender and lets learners follow them with instructions, visual guidance, and automatic checks. It integrates with the Sci-Bono Clubhouse LMS (a separate PHP repository) through a documented adapter.

The full product plan is in `docs/plan.md`. Read it before starting any milestone. When this file and the plan disagree, the plan wins; flag the conflict.

## Current phase

**Milestone 1 — Prove guidance and recording.** See `docs/milestone-1-brief.md`. Step 0 (API verification) results are in `docs/m1-findings.md`.

Do not start Milestone 2 work (full lesson editor, package export/import, polished UI) or any LMS integration until Milestone 1's decision gate is recorded in `docs/m1-findings.md`.

## Target platform

- **Blender 5.2 LTS** on **Windows** (classroom pilot). Other platforms should not break, but are not tested in v1.
- Blender 5.2 (5.2.2 LTS) is installed at `D:\Program Files\Blender Foundation\Blender 5.2\blender.exe`. It is **not** on PATH, and older 4.x builds exist under `C:\Program Files\Blender Foundation\` — always invoke the 5.2 path explicitly.
- Blender 5.2 bundles **Python 3.13**; the system Python is 3.11. Code in `core/` must run under both (plain pytest uses the system Python). Re-check with `sys.version` after Blender upgrades.
- Package as a Blender **extension** with `blender_manifest.toml`, not a legacy `bl_info` add-on.
- Licence: **GPL-3.0-or-later**. Every source file carries an SPDX header: `# SPDX-License-Identifier: GPL-3.0-or-later`.

## Repository layout

Entries marked *(planned)* don't exist yet.

```
blender_manifest.toml
__init__.py              # register/unregister only
core/                    # pure Python, no bpy imports (testable without Blender)
  tutorial_schema.py     # lesson data model and strict validation (schema_version 1)
  targets.py             # semantic target -> one object, or missing/ambiguous
  checks.py              # completion checks evaluated on a scene snapshot
  session.py             # next/back/skip/confirm; never touches the scene
  journal.py             # append-only JSON Lines journals (header + entries, crash-tolerant)
  state_diff.py          # diff/apply between scene snapshots (state journal format)
  draft_generator.py     # (planned) merges action + state journals into draft steps
blender/                 # everything that touches bpy
  lifecycle.py           # the only place handlers/timers/draw handlers/msgbus are added
  state.py               # read-only scene snapshot (dict) consumed by core/checks.py
  guidance/              # runtime (active lesson + timer), overlay, operators, sidebar
  recorder/              # recorder.py (journals, timers, handlers), ui.py (Recorder panel)
lessons/                 # bundled example lesson JSON (ships in the extension zip)
spikes/                  # throwaway API experiments (Milestone 1 step 0)
tests/
  unit/                  # pytest, no Blender required (core/)
  blender/               # run inside headless Blender
docs/
  plan.md
  milestone-1-brief.md
  m1-findings.md
```

Keep `core/` free of `bpy` so most logic can be unit-tested with plain pytest. Checks and target resolution take the plain-dict snapshot from `blender/state.py`, never live bpy objects; a new check type needs a schema entry in `core/tutorial_schema.py`, an evaluator in `core/checks.py`, and any new snapshot field in `blender/state.py`.

Add every app handler, timer, draw handler and msgbus subscription through `blender/lifecycle.py` (`add_app_handler`, `add_timer`, `add_draw_handler`, `subscribe_rna`). `unregister()` calls `lifecycle.remove_all()`, and `tests/blender/test_register.py` checks nothing is left behind. Anything registered directly with `bpy` bypasses that check.

## Non-negotiable rules

1. **Tutorials are declarative data.** Never generate, store, or execute Python from tutorial content. Captured commands are evidence for draft steps, never replayed as code.
2. **Clean registration.** Every draw handler, app handler, timer, and msgbus subscription added in `register()` must be removed in `unregister()`. Disabling the extension must leave Blender exactly as it was.
3. **No `bpy.ops` inside draw callbacks or depsgraph handlers.** Draw code only draws. Handlers only read state and queue work.
4. **Performance budget.** Overlay drawing and state snapshots must not cause visible stutter on lab hardware. Throttle state snapshots (idle timer, not every depsgraph update) and measure. Record timings in `docs/m1-findings.md`.
5. **Semantic targets only.** Never store screen coordinates, face indices, or vertex indices as targets.
6. **No network access in Milestone 1.** When network code arrives (Milestone 3), it must check `bpy.app.online_access` and use HTTPS only.
7. **No learner telemetry.** The recorder is a teacher authoring tool. Nothing records learner sessions.
8. **Never silently replace the user's open file.** Offer to save first; open working copies separately.

## Testing

Commands below use PowerShell; `$B = "D:\Program Files\Blender Foundation\Blender 5.2\blender.exe"`.

- Pure logic, in the dev container: `docker exec blendersage-dev python -m pytest tests/unit` (Windows system Python has no pytest). `tests/unit/pytest.ini` makes `tests/unit` the rootdir; without it pytest imports the repo-root `__init__.py`, which needs bpy.
- Single unit test: `docker exec blendersage-dev python -m pytest tests/unit/test_checks.py::test_mode_check`
- Inside Blender (headless):
  `& $B -b --factory-startup --python-exit-code 1 --python tests/blender/run_all.py`
  Filter by substring of `<file>::<test>` after `--`, e.g. `... run_all.py -- test_register.py::test_enable_disable_twice`. The runner resets to factory settings before each test. Tests import the repo root as package `blendersage` (`tests/blender/extension_loader.py`) and call `register()`/`unregister()` directly.
- Guidance GUI check (screenshots at UI scale 1.0/1.5/2.0 and draw timings to `spikes/out/`): `& $B --factory-startup --enable-event-simulate --python tests/blender/gui_check_guidance.py`
- Recorder GUI check with real reports, in two runs (phase 1 exits without stopping to simulate a crash; phase 2 continues and summarises): `& $B --factory-startup --enable-event-simulate --python tests/blender/gui_check_recorder.py -- phase1`, then `-- phase2`. Headless recorder tests inject stand-in reports through `recorder.start(reports_source=...)`.
- Run a spike: `& $B -b --factory-startup --python-exit-code 1 --python spikes/<name>.py` (drop `-b` for spikes that need a viewport/UI).
- Extension packaging (from the repo root): `& $B --command extension validate`, and `& $B --command extension build --output-dir <existing folder>` (the folder must already exist). `[build] paths_exclude_pattern` in the manifest keeps docs, tests and spikes out of the zip.
- Real install/enable/disable/uninstall of the built zip, isolated from the real Blender setup:
  `$env:BLENDER_USER_RESOURCES = "<new empty temp folder>"; & $B -b --factory-startup --python-exit-code 1 --python tests/blender/check_install.py -- <path to zip>`, then `Remove-Item Env:BLENDER_USER_RESOURCES`. Never run it without that variable, or it installs into the user's real extensions folder.
- Background mode (`-b`) stores no `WindowManager.reports`, so anything that depends on reports needs a GUI session. GUI spikes and tests run in a fresh window driven by `Window.event_simulate`: `& $B --factory-startup --enable-event-simulate --python spikes/<name>.py` (see `spikes/_gui_runner.py` and the quirks listed in `docs/m1-findings.md`).
- UI, overlay, and display-scaling behaviour cannot be tested headless. Keep a manual checklist in `docs/m1-findings.md` and record results there.

### Dev container

The repo has a VS Code Dev Container (`.devcontainer/`): Python 3.13, headless Blender 5.2.2 for Linux, pytest, and `fake-bpy-module-5.2` type stubs. Open it with **Dev Containers: Reopen in Container**. The container is always named `blendersage-dev` and mounts the repo at `/workspaces/BlenderSage`.

From the Windows host (e.g. Claude Code), with the container running:

- Unit tests: `docker exec blendersage-dev python -m pytest tests/unit`
- Headless Blender: `docker exec blendersage-dev blender -b --factory-startup --python-exit-code 1 --python tests/blender/run_all.py`
- Start it without VS Code: `npx -y @devcontainers/cli@latest up --workspace-folder .`

If the container is stopped, `docker exec` fails with `Error response from daemon: container <id> is not running`. Start it (`docker start blendersage-dev`) rather than falling back to Windows tools without saying so.

Limits:
- The container can't test UI, overlay, display scaling or Windows behaviour. Use the Windows Blender 5.2 install and the manual checklist for those.
- The stubs are type-only (`bpy-stubs`), so `import bpy` fails in the container's plain Python. That is intended: a `bpy` import in `core/` makes pytest fail.
- To change the Blender version, edit `ARG BLENDER_VERSION` in `.devcontainer/Dockerfile` and rebuild.

## Working style

- For any API you are unsure about, write a small script in `spikes/` and run it before building on it. Record what you learned in `docs/m1-findings.md`. Do not assume Blender 5.2 API behaviour from older versions.
- Stop and report at the checkpoints marked in the milestone brief rather than pushing through.
- Prefer small, reviewable commits.

## Git

- Never add a `Co-Authored-By` line (or any other co-author trailer) to any commit in this repository. This applies to every commit, including merge and squash commits, and overrides any default attribution guidance.
