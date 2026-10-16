# SPDX-License-Identifier: GPL-3.0-or-later
"""GUI check for the recorder with real WindowManager.reports, in two Blender runs.

Phase 1 records a scripted session (modal tools, cancel, typed values, duplicate,
undo/redo, subdivision, edit-mode extrude, an N-panel dimension edit, pause/resume,
save and reopen the file), then exits WITHOUT stopping, the way a crash would.
Phase 2 starts a new Blender, continues the unfinished recording, does one more
action, stops, and writes a summary of both journals.

    & $B --factory-startup --enable-event-simulate --python tests/blender/gui_check_recorder.py -- phase1
    & $B --factory-startup --enable-event-simulate --python tests/blender/gui_check_recorder.py -- phase2
Output: spikes/out/recordings/<id>/ and spikes/out/gui_check_recorder_<phase>.json
"""
import collections
import os
import shutil
import sys
import tempfile

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "spikes"))
from _gui_runner import OUT_DIR, area_region, run, simulate, tap, view3d_area  # noqa: E402
from extension_loader import load_extension  # noqa: E402

PHASE = sys.argv[sys.argv.index("--") + 1]
REC_DIR = os.path.join(OUT_DIR, "recordings")
DIM_X_FIELD = (1425, 1009 - 410)  # N-panel Item > Dimensions X in the 1920x1009 factory layout
DIGITS = {"0": "ZERO", "1": "ONE", "2": "TWO", "3": "THREE", "4": "FOUR", "5": "FIVE"}

ext = load_extension()
rec = ext.blender.recorder.recorder


def win():
    return bpy.context.window_manager.windows[0]


def center():
    reg = area_region(view3d_area(win().screen))
    return reg.x + reg.width // 2, reg.y + reg.height // 2


def move(dx=0, dy=0):
    x, y = center()
    simulate(win(), "MOUSEMOVE", x=x + dx, y=y + dy)


def type_text(text):
    for ch in text:
        simulate(win(), DIGITS[ch], "PRESS", unicode=ch)
        simulate(win(), DIGITS[ch], "RELEASE")


def step(fn):
    fn.__name__ = fn.__name__
    return fn


def setup_phase1(results):
    if os.path.isdir(REC_DIR):
        shutil.rmtree(REC_DIR)
    os.makedirs(REC_DIR)
    ext.register()
    tap(win(), "ESC")
    move()
    results["recording_id"] = rec.start(directory=REC_DIR)


def grab(results):
    move()
    tap(win(), "G")
    move(60, 0)
    move(120, 30)
    tap(win(), "LEFTMOUSE")


def grab_cancel(results):
    move()
    tap(win(), "G")
    move(80, 40)
    tap(win(), "ESC")


def rotate_45(results):
    move()
    tap(win(), "R")
    tap(win(), "Z")
    type_text("45")
    tap(win(), "RET")


def scale_2(results):
    move()
    tap(win(), "S")
    type_text("2")
    tap(win(), "RET")


def duplicate(results):
    move()
    tap(win(), "D", shift=True)
    move(0, 100)
    tap(win(), "LEFTMOUSE")


def undo(results):
    tap(win(), "Z", ctrl=True)


def redo(results):
    tap(win(), "Z", ctrl=True, shift=True)


def subdivision(results):
    move()
    tap(win(), "TWO", ctrl=True)


def extrude(results):
    move()
    tap(win(), "TAB")
    tap(win(), "E")
    move(0, 60)
    tap(win(), "LEFTMOUSE")
    tap(win(), "TAB")


def open_n_panel(results):
    move()
    tap(win(), "N")


def hover_dimension(results):
    simulate(win(), "MOUSEMOVE", x=DIM_X_FIELD[0], y=DIM_X_FIELD[1])


def type_dimension(results):
    tap(win(), "LEFTMOUSE")
    tap(win(), "A", ctrl=True)
    type_text("3")
    tap(win(), "RET")


def pause(results):
    rec.pause()


def grab_while_paused(results):
    grab(results)


def resume(results):
    rec.resume()


def save_and_reopen(results):
    path = os.path.join(tempfile.mkdtemp(prefix="blendersage-rec-file-"), "session.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path)
    bpy.ops.wm.open_mainfile(filepath=path)


def wait(results):
    pass


def record_status_and_crash(results):
    results["status_before_crash"] = rec.status()
    # The runner exits Blender next without calling rec.stop(): a simulated crash.


def setup_phase2(results):
    ext.register()
    tap(win(), "ESC")
    move()
    unfinished = rec.unfinished_recordings(REC_DIR)
    results["unfinished_found"] = unfinished
    results["recording_id"] = rec.start(directory=REC_DIR, continue_id=unfinished[-1])


def stop_and_summarise(results):
    results["status_at_stop"] = rec.status()
    rec.stop()
    folder = os.path.join(REC_DIR, results["recording_id"])
    _, actions, a_trunc = ext.core.journal.read_journal(os.path.join(folder, "actions.jsonl"))
    _, states, s_trunc = ext.core.journal.read_journal(os.path.join(folder, "state.jsonl"))
    reports = [e for e in actions if e["kind"] == "report"]
    results["summary"] = {
        "action_kinds": [e["kind"] for e in actions if e["kind"] != "report"],
        "report_count": len(reports),
        "reports": [f"{e['type']}: {e['message'][:90]}" for e in reports],
        "state_entries": collections.Counter(e["kind"] for e in states),
        "diff_triggers": collections.Counter(t for e in states if e["kind"] == "diff" for t in e["triggers"]),
        "truncated": [a_trunc, s_trunc],
        "uids_increasing_per_session": all(
            a["uid"] < b["uid"] for a, b in zip(reports, reports[1:]) if a["bs"] == b["bs"]),
        "blender_sessions": sorted({e["bs"] for e in reports}),
        "actions_bytes": os.path.getsize(os.path.join(folder, "actions.jsonl")),
        "state_bytes": os.path.getsize(os.path.join(folder, "state.jsonl")),
    }
    ext.unregister()


D = 0.7
if PHASE == "phase1":
    steps = [(D, setup_phase1)]
    for fn in (grab, grab_cancel, rotate_45, scale_2, duplicate, undo, redo, subdivision, extrude,
               open_n_panel, hover_dimension, type_dimension, pause, grab_while_paused, resume,
               save_and_reopen, grab, wait, wait):
        steps.append((D, fn))
    steps.append((0.3, record_status_and_crash))
    run("gui_check_recorder_phase1", steps)
else:
    run("gui_check_recorder_phase2", [(D, setup_phase2), (D, grab), (1.5, wait), (0.3, stop_and_summarise)])
