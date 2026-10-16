# Milestone 1 Brief — Prove Guidance and Recording

Read `CLAUDE.md` and `docs/plan.md` (sections 2 and 4) first.

## Goal

Produce runtime evidence, on Windows with Blender 5.2 LTS, that (a) in-viewport guidance works reliably and (b) the two-stream recorder can turn a real modelling session into usable draft steps. This is a prototype: favour learning speed over polish. Its main output is `docs/m1-findings.md` and a recorded decision on whether automatic recording ships in v1.

## Steps

### Step 0 — Verify the APIs the design depends on  ⛔ checkpoint

Write spike scripts in `spikes/` that confirm, in Blender 5.2:

1. **Action reports:** how operator/action reports are exposed, what they contain (operator id, properties, timing), whether modal operators (grab/rotate/scale, extrude) and cancelled operations are reported, and how undo/redo appears.
2. **Property edits:** what signal (if any) fires when a user drags a modifier slider or types a dimension in the Properties editor or N-panel — depsgraph updates, msgbus subscriptions, or neither.
3. **Screenshot API:** capturing the 3D viewport or an area to an image for reference images.
4. **Overlay drawing:** drawing text and shapes in the 3D viewport with `gpu`/`blf`, and outlining an editor region.

Write findings to `docs/m1-findings.md`.

**Stop here and report** before building anything else. If any recorder or guidance assumption in `docs/plan.md` section 2 is wrong, propose a design change.

### Step 1 — Extension skeleton

`blender_manifest.toml`, register/unregister, sidebar panel in the 3D viewport, and a test that enabling then disabling the extension leaves no handlers, timers, or subscriptions behind.

### Step 2 — Guidance prototype

Hand-write one small lesson as JSON (5–8 steps of the desk organiser: add cube, scale to dimensions, add bevel modifier, etc.) using a minimal schema in `core/tutorial_schema.py`. Implement:

- Collapsible instruction card in the viewport.
- Object outline/highlight for a semantic target; prompt for selection when the target is missing or ambiguous.
- Editor-region highlight plus a menu/property path text.
- Completion checks: object exists/type, mode, dimensions with tolerance, modifier present with settings, material assigned.
- Next/back/skip navigation that never undoes modelling work.

Verify manually: workspace changes, display scaling (100%, 150%, 200%), undo, loading a different file mid-lesson, disabling the extension mid-lesson. Record results in the findings checklist.

### Step 3 — Recorder  ⛔ checkpoint

Implement the action journal and state journal (plan section 2, "Recorder design"): incremental append-only journal on disk, throttled state snapshots of the documented property set, pause/resume, and recovery after Blender is closed unexpectedly.

**Stop and report** with a short recording (~10 minutes) and its raw journals before building the generator.

### Step 4 — Draft-step generator

Pure-Python module in `core/draft_generator.py` that merges the two journals into draft steps and review items, following the merge rules in plan section 2, "Recorder design". Unit-test it with recorded journal fixtures. A plain text or simple panel view of the drafts is enough; no editor UI yet.

### Step 5 — Decision-gate evidence

Prepare everything needed for the teacher to run the 60–90-minute desk-organiser recording (≥1,000 actions, including property edits, undo/redo, cancellations, pause/resume, and one forced Blender crash). After the session, report:

- Percentage of teaching steps that arrived as usable drafts or clear review items (gate threshold: 80%).
- Categories of missed or garbled steps.
- Snapshot and overlay timings on the lab machine.
- Recommendation: keep automatic recording in v1, or defer to v1.1.

## Out of scope for Milestone 1

Full lesson editor, package export/import, checkpoint `.blend` files, translation, any LMS or network code, polished visuals.

## Definition of done

`docs/m1-findings.md` contains API findings, the manual guidance checklist with results, performance timings, the desk-organiser recording results, and the gate recommendation for the teacher to approve.
