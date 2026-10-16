# Milestone 1 Findings

Runtime evidence for Milestone 1 (see `docs/milestone-1-brief.md` and `docs/plan.md` section 4).

## Step 0: API verification

Date: 2026-10-16. Blender **5.2.2 LTS** (build `d13f752e3b9c`), Windows 11, bundled Python 3.13.13. Every result below comes from a spike in `spikes/`, run against `D:\Program Files\Blender Foundation\Blender 5.2\blender.exe`. GUI spikes open a fresh `--factory-startup` window and drive it with `Window.event_simulate` (`--enable-event-simulate`). Raw results are written to `spikes/out/` (not committed).

| Spike | Question |
|---|---|
| `s0_api_inventory.py` | Which relevant APIs exist (background mode) |
| `s1_action_reports.py` | What modal, cancelled, undo/redo, edit-mode and Python-called actions produce |
| `s1c_typed_and_rollover.py` | Typed values in modal tools; report and history limits |
| `s1d_reports_file_load.py` | Whether reports survive save and file load |
| `s2a_layout_shot.py`, `s2b_property_edits.py` | Which signals fire for edits in the N-panel and Properties editor |
| `s3_screenshot_overlay.py` | `Window.screenshot`, `screenshot_area`, gpu/blf overlay, UI scale, handler removal |

### 1. Action reports

**API.** `WindowManager.reports` is a read-only collection of `Report` with `message` (string), `type` (enum) and `session_uid` (int). `WindowManager.operators` still holds the operator history. There is no app handler that fires when an operator runs; `undo_pre/post` and `redo_pre/post` exist.

**Behaviour observed:**

| User action | `wm.reports` | `wm.operators` | Other signal |
|---|---|---|---|
| Grab (G, move, click) | `OPERATOR`: `bpy.ops.transform.translate(value=(0.815658, 1.84671, …), …)` | `TRANSFORM_OT_translate` | depsgraph update |
| Grab cancelled (G, move, Esc) | nothing | nothing | depsgraph updates from the live preview only |
| Rotate with typed value (R Z 45 Enter) | `OPERATOR`: `transform.rotate(value=0.785398, orient_axis='Z', …)` | added | |
| Scale with typed value (S 2 Enter) | `OPERATOR`: `transform.resize(value=(2, 2, 2), …)` | added | |
| Duplicate (Shift+D) | `OPERATOR`: `object.duplicate_move(OBJECT_OT_duplicate={…}, TRANSFORM_OT_translate={…})` | added | |
| Ctrl+2 | `OPERATOR`: `object.subdivision_set(level=2, …)` | added | |
| Tab, extrude, Tab | `editmode_toggle()`, `mesh.extrude_region_move(…)`, `editmode_toggle()` | added | |
| Undo (Ctrl+Z) | nothing | **cleared** | `undo_post` fires |
| Redo (Ctrl+Shift+Z) | nothing | stays empty | `redo_post` fires |
| Operator called from Python | `OPERATOR` report | **not** added | |

- Reports carry the final, confirmed values of modal tools, including typed values. Each report message is a complete Python-call string.
- Reports have **no timestamp**. The recorder must stamp them when it polls.
- **No cap observed:** 400 operator calls in one session gave 402 reports, `session_uid` 1 to 402, none dropped.
- **Cleared on file load.** After `open_mainfile` the collection is empty. `session_uid` keeps increasing across loads, so it is a safe de-duplication key for one Blender session.
- **Background mode stores no reports at all.** Three `primitive_cube_add` calls under `-b` left `wm.reports` empty. Recorder tests that need reports must run in a GUI session.
- `wm.operators` is not usable as a source: undo clears it and Python-called operators never enter it.

### 2. Property edits

| Edit | msgbus | depsgraph | `wm.reports` |
|---|---|---|---|
| Type Location X = 1 in the N-panel | `location` fires once | 1 update | `PROPERTY`: `bpy.context.object.location[0] = 1` |
| Type Bevel Amount = 2 in Properties | `width` fires once | 1 update | `PROPERTY`: `bpy.context.object.modifiers["Bevel"].width = 2` |
| Drag Bevel Amount slider | `width` fires **once**, at release | 1 update | `PROPERTY`: `…width = 2.55` (final value only) |
| Type Dimensions X = 3 in the N-panel | `scale` fires (dimensions are stored as scale) | 1 update | **nothing** |
| Python `modifier.width = 0.25` | `width` fires | 1 update | nothing |
| Viewport grab | **nothing** | 1 update | `OPERATOR` report |

- Edits through UI fields and sliders produce `PROPERTY` reports with an RNA path relative to `bpy.context`, except **Dimensions**: a derived property that is written through `scale`, which leaves no report.
- msgbus fires once per completed edit, for UI and Python changes alike, and never for viewport transforms. That matches the bundled `bpy.msgbus` docs.

### 3. Screenshots

- **`Window.screenshot(*, region=None, use_alpha=False)`** is new in 5.2. It returns a `memoryview` of shape `(height, width, 4)`, format `B` (uint8). A full 1920×1009 window is 7.7 MB and took **5–6 ms**. `region=((min_x, min_y), (max_x, max_y))` crops it. It is a Python method, not an RNA function, so it does not show in `bl_rna.functions`.
- `bpy.ops.screen.screenshot_area(filepath=…)` writes a PNG of one area in **53–66 ms**.
- Not tested yet: turning the memoryview into a saved PNG through the new 5.2 imbuf pixel access. This matters for teacher reference images and is checked in Step 2.

### 4. Overlay drawing

- `SpaceView3D.draw_handler_add(fn, (), "WINDOW", "POST_PIXEL")` with `gpu` (`UNIFORM_COLOR` shader, `TRIS` and `LINE_STRIP` batches) and `blf` drew an instruction card, a marker projected from the active object's origin, and text. `SpaceProperties.draw_handler_add` outlined the Properties editor. Screenshot: `spikes/out/s3_window_scale_2.0.png`.
- **Cost per viewport draw:** mean 0.31–0.33 ms, max 1.05–1.32 ms, at UI scale 1.0, 1.5 and 2.0.
- **The first draw of a new shader took 80 ms** (Properties outline, first frame only; 0.13 ms afterwards). Expect a one-off hitch the first time guidance appears unless it is warmed up.
- **Sizing:** multiply sizes by `preferences.system.ui_scale` and they scale correctly.
- **Region overlap (default on):** the viewport `WINDOW` region extends under the toolbar and header. The card drawn 20 px from the region edge was half hidden behind the toolbar at scale 2.0. Toolbar width was 56 / 84 / 113 px at scale 1.0 / 1.5 / 2.0. Guidance must offset by the `TOOLS`, `UI` and `HEADER` region sizes read from `area.regions` at draw time.
- `draw_handler_remove` stopped all drawing (0 calls after removal).

### Assumptions checked against the plan

The plan (section 2) says: "Blender 5.2's action reports and screenshot APIs support this approach." **Confirmed, with gaps that the state stream must cover:**

1. **Action stream = `wm.reports`** (`OPERATOR` and `PROPERTY` types), polled on a timer and de-duplicated by `session_uid`. Report text is evidence only. It may be parsed with `ast.parse`/`ast.literal_eval`, which never executes code. It must never be run (CLAUDE.md rule 1).
2. **Gaps the state snapshot stream must cover:** Dimensions edits (no report), undo and redo (no report; `undo_post`/`redo_post` fire), and any edit made outside the reported paths. A cancelled action leaves no report, which is correct.
3. **Noise to flag as review items:** operators called by other add-ons or scripts are reported exactly like user actions, with nothing that tells them apart.
4. **Journal must be written incrementally and survive file loads:** reports are cleared on load, and non-persistent timers are dropped on load (seen when a spike stalled after `open_mainfile`). Recorder timers and handlers must be registered as persistent.
5. **msgbus is a cheap change signal** (once per completed edit) that can schedule throttled snapshots. It misses viewport transforms, so depsgraph updates or reports must cover those.

**Design change (approved 2026-10-16):** the plan's direction stands. The journal rules above were written into `docs/plan.md` section 2, "Recorder design", and the brief now points there.

### Testing notes for later steps

`Window.event_simulate` works for automated GUI tests with these quirks:
- Launch with `--enable-event-simulate`.
- `MOUSEMOVE` events must use value `NOTHING`.
- Key events must carry `x`/`y`; otherwise they land at (0, 0), outside the viewport.
- Typed digits need `unicode=` as well as the key type.
- Hover a field in one event-loop tick and click it in a later one.
- Screen positions found for spikes are for this test only; the extension never stores them (CLAUDE.md rule 5).

## Step 2: Guidance prototype

Date: 2026-10-16. Blender 5.2.2 on Windows.

**What exists:**
- `lessons/desk_organiser.json`: 8 steps, schema version 1. It ships inside the extension.
- `core/tutorial_schema.py` (strict validation), `core/targets.py`, `core/checks.py` and `core/session.py`: pure Python.
- `blender/state.py`: read-only scene snapshot.
- `blender/guidance/`:
  - `runtime.py`: one active lesson, evaluated by a persistent 0.5 s timer that only reads.
  - `overlay.py`: instruction card, target box, editor outline.
  - `operators.py`: sidebar buttons. Back, Next, Skip and Confirm push no undo step.
  - `sidebar.py`: the lesson panel.

**Check types:** `object_exists`, `mode`, `dimensions` and `scale` (with tolerance), `modifier` (type plus settings with tolerance), and `material_assigned` (optional name prefix).

**Lesson change found during testing:** the first version added a Bevel to a cube whose scale had not been applied. Blender showed "Active object has non-uniform scale", and the bevel would be uneven. The lesson now has an "Apply the scale" step, checked by `scale`. To stay at 8 steps, the separate Edit Mode step was merged into "Delete the top face".

### Automated results

- **Unit tests:** 35/35 pass (`pytest tests/unit` in the dev container, Python 3.13). They cover:
  - schema rejection with paths: unknown keys, unknown check types, dangling targets, NaN, duplicate ids;
  - target resolution: tag beats name rule; ambiguous and missing are never guessed;
  - every check type;
  - navigation: Next needs completion, Skip leaves the step incomplete, Confirm only where allowed.
- **Blender tests:** 20/20 pass headless on Windows and in the Linux container. They include:
  - a walk through all 8 lesson steps on a real scene;
  - starting and stopping a lesson removing exactly its timer and draw handlers;
  - disabling the extension mid-lesson leaving nothing behind;
  - navigation leaving the scene snapshot unchanged;
  - the lesson surviving `read_homefile`, with its target reported missing in an empty file;
  - **Use selected** tagging the target.
- **Install check (`tests/blender/check_install.py`):** the built zip (19 KB, lesson included) installs, starts the bundled lesson, disables mid-lesson with no panel or handlers left, and uninstalls.
- **GUI check (`tests/blender/gui_check_guidance.py`):** screenshots of steps 1, 2 and 4 at UI scale 1.0, 1.5 and 2.0, of the ambiguous-target state, after **Use selected**, and of the collapsed card.
  - The card stays clear of the toolbar at every scale.
  - The Properties editor is outlined for Properties steps.
  - With two cubes, both get candidate boxes, and the card and sidebar ask the learner to select one and click **Use selected**.
  - After unregistering, nothing is left in the registry.

**Known limits:**
- The target box is drawn from the object's bounding box. At 30 × 20 × 10 cm it is small at the default zoom; the "Where" path and the hints carry the guidance there.
- Saving `Window.screenshot()` pixels as a PNG reference image (open since Step 0) is not needed for this lesson and is still untested.

### Manual guidance checklist

Run by the project owner on 2026-10-16 in Windows Blender 5.2: all 9 checks passed.

These need a person at Windows Blender 5.2. Start Blender normally, enable the extension from the built zip (Edit > Preferences > Get Extensions > Install from Disk), press N in the 3D Viewport, open the **BlenderSage** tab and click **Start Example Lesson**.

| # | Check | Expected | Result |
|---|---|---|---|
| 1 | Follow all 8 steps with the mouse and keyboard | Each step turns "Done" by itself once the model matches, except step 6, which needs Confirm. Next is only available after Done. | Done |
| 2 | Change workspace (Modeling, Shading, back to Layout) mid-lesson | Card and target box appear in every 3D Viewport; sidebar state is unchanged | Done |
| 3 | Display scaling 100%, 150%, 200% (Preferences > Interface > Resolution Scale, and Windows display scaling) | Card text readable and clear of the toolbar; no clipped text in the sidebar | Done |
| 4 | Undo (Ctrl+Z) after Next | Undoes your last modelling action, not the navigation; the lesson re-checks the step | Done |
| 5 | Back, then Next again | The model is unchanged; completed steps stay completed | Done |
| 6 | Open a different file mid-lesson (File > Open) | Blender asks to save as usual. The lesson keeps running and shows "Waiting for the organiser box" if there is no cube. | Done |
| 7 | Rename the cube to "Box" | The step asks you to select the organiser and click **Use selected**; after that it is found again | Done |
| 8 | Disable the extension mid-lesson (Preferences > Add-ons) | Card, box, outline and panel disappear; no errors in the console (Window > Toggle System Console) | Done |
| 9 | Collapse and expand the card | Collapsed shows only the step title; expanding brings the full card back | Done |

## Step 3: Recorder (checkpoint)

Date: 2026-10-16. Blender 5.2.2 on Windows. Implements plan section 2, "Recorder design".

**What exists:**
- `core/journal.py`: JSON Lines with a header line. Every entry is flushed to the OS as it is written, so a Blender crash loses nothing already written. `sync()` (fsync) runs on pause and stop. A half-written last line is skipped and flagged, and reopening starts on a fresh line.
- `core/state_diff.py`: `diff_states` / `apply_diff`. Applying the diffs in order rebuilds the state; this round trip is tested.
- `blender/recorder/recorder.py`:
  - A persistent 0.1 s timer collects new `OPERATOR` and `PROPERTY` reports (de-duplicated by `session_uid`) and writes queued entries in order.
  - Five persistent handlers (`undo_post`, `redo_post`, `load_pre`, `load_post`, `depsgraph_update_post`) only collect reports and queue entries or mark the state as changed.
  - A 0.25 s idle timer writes a diff at most once per second.
  - Pause and resume. Continue after a crash. "extension disabled" stop on unregister.
- `blender/recorder/ui.py`: a "Recorder" panel in the BlenderSage tab: Start, Pause, Resume, Stop, Continue Unfinished Recording, and Open Recordings Folder. Recordings go to the extension's user folder (`bpy.utils.extension_path_user(…, "recordings")`), one folder per recording holding `actions.jsonl` and `state.jsonl`.

**Journal entries:**
- `actions.jsonl`:
  - `start` and `recovered`: wall time, Blender session, version and file name;
  - `report`: `t`, `bs`, `uid`, `type`, `message`;
  - `undo`, `redo`, `pause`, `resume`, `file_loaded` and `stop` (with a reason).
- `state.jsonl`:
  - `snapshot`: a full state, written at start, resume and recovery;
  - `diff`: the changes since the last snapshot, plus the triggers that caused it.
- `t` is seconds since the start of that segment and restarts at a `recovered` entry.

### Automated results

- **Unit tests:** 47/47 pass, including 7 for the journal and 5 for the state diff.
- **Blender tests:** 31/31 pass on Windows and in the Linux container. The 11 recorder tests cover:
  - headers and the initial snapshot;
  - reports journaled once, only `OPERATOR`/`PROPERTY`, and none from before the start;
  - snapshot throttling, and no entry when nothing changed;
  - pause skipping actions, and a full snapshot on resume;
  - undo and redo entries;
  - reports captured at `load_pre` before a file load clears them;
  - persistent hooks surviving a file load and removed on stop;
  - disabling mid-recording writing a `stop` entry;
  - continuing an unfinished recording.
  Background mode has no reports, so these tests feed stand-in reports.

### GUI check with real reports (`tests/blender/gui_check_recorder.py`)

Phase 1 recorded a scripted 14-second session in a fresh window and then exited without stopping, simulating a crash. Phase 2, in a new Blender, found the unfinished recording, continued it, did one more action and stopped.

- **10 reports recorded, in order:** grab, rotate (`value=0.785398`, typed 45), resize (`(2, 2, 2)`, typed), `duplicate_move`, `subdivision_set`, `editmode_toggle`, `extrude_region_move`, `editmode_toggle`, a grab after save-and-reopen, and a grab after recovery.
- **Correctly absent:** the cancelled grab and the grab made while paused.
- **Action journal order:** `start, undo, redo, pause, resume, file_loaded, recovered, stop`, with reports between them. Report IDs increase within each Blender session; the two sessions have different `bs` values. No truncated lines.
- **The Dimensions X edit typed in the N-panel** produced no report, as Step 0 found. It is in the state journal: a diff at t=8.58 with `Cube.001.dimensions = [3, 4, 4]` and `scale = [1.5, 2, 2]`.
- **Diffs combine nearby changes:** at a 1 s throttle, one diff can cover several actions. The redo diff at t=6.08 already includes the Subdivision modifier added 0.7 s later. The Step 4 generator must line up diffs with report times, not treat a diff as one action.
- **Size:** 6.3 KB of actions and 6.4 KB of state for this session, roughly 0.6 KB per action including snapshots.

### Checkpoint: ~10-minute recording by the teacher

To be recorded with the real interface. Steps:
1. Install `dist/blendersage-0.1.0.zip`.
2. In the BlenderSage tab, open **Recorder** and click **Start Recording**.
3. Model for about 10 minutes. Include property edits in the N-panel and Properties editor, undo and redo, a cancelled tool, Pause and Resume, and opening a file.
4. Click **Stop Recording**.
5. Use **Open Recordings Folder** to find the journals.

Results: *pending*.

## Performance timings

| Measurement | Result | Source |
|---|---|---|
| Viewport overlay draw (card, text, marker) | mean 0.31–0.33 ms, max 1.32 ms | `s3_screenshot_overlay.py`, dev PC |
| First draw of a new shader | 80 ms, once | same |
| `Window.screenshot()` full window | 5–6 ms | same |
| `screenshot_area` to PNG | 53–66 ms | same |
| Guidance card draw (real lesson) | mean 0.16–0.97 ms, max 2.3 ms, scales 1.0–2.0 | `gui_check_guidance.py`, dev PC |
| Target box draw | mean 0.14–0.27 ms, max 0.36 ms | same |
| Editor outline draw | mean 0.05–0.55 ms, max 3.0 ms (first frame) | same |
| State snapshot + diff (factory scene, 3–4 objects) | mean 0.58 ms, max 2.5 ms | `gui_check_recorder.py`, dev PC |
| State snapshots on a 10-minute real session | pending checkpoint recording | |

Timings are from the development PC, not lab hardware. They need repeating on a lab machine.
