# SPDX-License-Identifier: GPL-3.0-or-later
"""Spike 2a: open the N-panel and the modifier tab, add a Bevel, screenshot the window.

Used once to find on-screen positions of the Dimensions X field and Bevel Amount field
for spike 2b (spike-only; the extension never stores screen coordinates).

    & $B --factory-startup --enable-event-simulate --python spikes/s2a_layout_shot.py
"""
import os
import sys

import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _gui_runner import OUT_DIR, area_region, run, simulate, tap, view3d_area  # noqa: E402


def win():
    return bpy.context.window_manager.windows[0]


def prepare(results):
    w = win()
    reg = area_region(view3d_area(w.screen))
    tap(w, "ESC")
    simulate(w, "MOUSEMOVE", x=reg.x + reg.width // 2, y=reg.y + reg.height // 2)
    tap(w, "N")
    cube = bpy.data.objects["Cube"]
    cube.modifiers.new("Bevel", "BEVEL")
    props = next(a for a in w.screen.areas if a.type == "PROPERTIES")
    props.spaces.active.context = "MODIFIER"
    results["window"] = [w.width, w.height]
    results["properties_area"] = [props.x, props.y, props.width, props.height]
    v3d = view3d_area(w.screen)
    results["view3d_ui_region"] = [(r.x, r.y, r.width, r.height) for r in v3d.regions if r.type == "UI"]


def shot(results):
    path = os.path.join(OUT_DIR, "s2a_layout.png")
    with bpy.context.temp_override(window=win()):
        bpy.ops.screen.screenshot(filepath=path)
    results["shot"] = path


run("s2a_layout_shot", [(0.8, prepare), (0.8, shot)])
