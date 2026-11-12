# BlenderSage

A free, open-source Blender extension for teaching inside Blender. Teachers create guided lessons; learners follow them step by step with instructions, visual guidance in the viewport, and automatic checks.

> **Status: early development (Milestone 1).** The guidance prototype and the teacher recorder work; the lesson editor, lesson packages and LMS integration come in later milestones. See [`docs/plan.md`](docs/plan.md) for the full plan and [`docs/m1-findings.md`](docs/m1-findings.md) for current results.

## What it does

- **Guided lessons for learners.** A *Lesson* panel in the 3D viewport sidebar (**N** → *BlenderSage*) and a collapsible instruction card in the viewport. Each step says what to do and why, highlights the target object, and checks completion automatically (mode, transforms, modifiers, and so on) or asks the learner to confirm. Next, Back and Skip are always available.
- **Recording for teachers.** A *Recorder* panel records a modelling session into two append-only journals on disk: the actions Blender reports, and throttled snapshots of the scene state. Recording survives file loads, can be paused, and can be continued after a crash. The journals become the raw material for draft lesson steps.
- **Lessons are data, not code.** Lessons are declarative JSON, validated against a strict schema. Nothing from a lesson or a recording is ever executed as Python.
- **No telemetry, no network.** The recorder is a teacher authoring tool; nothing records learner sessions.

An example lesson, *Model a desk organiser*, ships in [`lessons/`](lessons/).

## Requirements

- **Blender 5.2 LTS** or newer (packaged as a Blender extension, `blender_manifest.toml`).
- Targeted at **Windows** classroom computers for the first pilot. Other platforms should work but are not tested yet.

## Install

1. Build the extension zip from the repository root (the output folder must already exist):

   ```
   blender --command extension build --output-dir dist
   ```

2. In Blender: **Edit → Preferences → Get Extensions → ⌄ → Install from Disk…**, and choose the zip from `dist/`.
3. Open the sidebar in the 3D viewport (**N**) and pick the **BlenderSage** tab.

## Repository layout

```
blender_manifest.toml   extension manifest
__init__.py             register/unregister
core/                   pure Python, no bpy: lesson schema, targets, checks, session, journals, state diffs
blender/                everything that touches bpy: lifecycle, scene snapshots, guidance UI, recorder
lessons/                bundled example lessons
tests/unit/             pytest, no Blender needed
tests/blender/          tests run inside headless Blender
spikes/                 small API experiments
docs/                   plan, milestone brief, findings
```

## Development

The repository includes a VS Code Dev Container (`.devcontainer/`) with Python 3.13, headless Blender 5.2.2 for Linux and pytest. Start it with **Dev Containers: Reopen in Container**, or without VS Code:

```
npx -y @devcontainers/cli@latest up --workspace-folder .
```

Run the tests from the host:

```
docker exec blendersage-dev python -m pytest tests/unit
docker exec blendersage-dev blender -b --factory-startup --python-exit-code 1 --python tests/blender/run_all.py
```

UI, overlay and display-scaling behaviour need a real Blender window on Windows; those checks and their results are recorded in [`docs/m1-findings.md`](docs/m1-findings.md). [`CLAUDE.md`](CLAUDE.md) has the full list of test commands and project rules.

## Licence

GPL-3.0-or-later. Every source file carries an SPDX licence header.
