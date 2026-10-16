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

## Manual guidance checklist (Step 2)

Not started. Covers workspace changes, display scaling at 100/150/200%, undo, loading a different file mid-lesson, and disabling the extension mid-lesson.

## Performance timings

| Measurement | Result | Source |
|---|---|---|
| Viewport overlay draw (card, text, marker) | mean 0.31–0.33 ms, max 1.32 ms | `s3_screenshot_overlay.py`, dev PC |
| First draw of a new shader | 80 ms, once | same |
| `Window.screenshot()` full window | 5–6 ms | same |
| `screenshot_area` to PNG | 53–66 ms | same |
| State snapshots | not measured yet (Step 3) | |

Timings are from the development PC, not lab hardware. They need repeating on a lab machine.
