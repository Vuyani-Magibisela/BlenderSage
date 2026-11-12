# SPDX-License-Identifier: GPL-3.0-or-later
"""GUI check for the draft list in the Recorder panel (cannot be checked headless).

Makes drafts from the teacher's 10-minute fixture recording and screenshots the
panel at UI scale 1.0 and 1.5. Results: spikes/out/gui_check_drafts.json and *.png.

    & $B --factory-startup --enable-event-simulate --python tests/blender/gui_check_drafts.py
"""
import os
import shutil
import sys
import tempfile

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(REPO, "spikes"))
from _gui_runner import OUT_DIR, area_region, run, simulate, tap, view3d_area  # noqa: E402
from extension_loader import load_extension  # noqa: E402

FIXTURE = os.path.join(REPO, "tests", "unit", "fixtures", "recordings", "teacher-10min")
ext = load_extension()
ui = ext.blender.recorder.ui


def win():
    return bpy.context.window_manager.windows[0]


def setup(results):
    ui.BLENDERSAGE_PT_recorder.bl_options = set()  # open by default, for the screenshot
    ext.register()
    directory = tempfile.mkdtemp(prefix="blendersage-gui-drafts-")
    shutil.copytree(FIXTURE, os.path.join(directory, "teacher-10min"))
    result = ext.blender.recorder.drafts.make_drafts("teacher-10min", directory)
    ui._last_drafts.update(id="teacher-10min", result=result)
    results["stats"] = result.stats
    w = win()
    reg = area_region(view3d_area(w.screen))
    tap(w, "ESC")  # close the splash screen
    simulate(w, "MOUSEMOVE", x=reg.x + reg.width // 2, y=reg.y + reg.height // 2)
    tap(w, "N")


def open_tab(results):
    area_region(view3d_area(), "UI").active_panel_category = "BlenderSage"


def shot(label):
    def step(results):
        path = os.path.join(OUT_DIR, f"drafts_{label}.png")
        with bpy.context.temp_override(window=win()):
            bpy.ops.screen.screenshot(filepath=path)
        results.setdefault("shots", []).append(path)
    step.__name__ = "shot_" + label
    return step


def set_scale(value):
    def step(results):
        bpy.context.preferences.view.ui_scale = value
    step.__name__ = f"scale_{value}"
    return step


def teardown(results):
    bpy.context.preferences.view.ui_scale = 1.0
    ext.unregister()


run("gui_check_drafts", [
    (1.0, setup),
    (0.5, open_tab),
    (1.0, shot("scale1.0")),
    (0.2, set_scale(1.5)),
    (1.0, shot("scale1.5")),
    (0.2, teardown),
])
