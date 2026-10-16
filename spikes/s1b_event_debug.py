# SPDX-License-Identifier: GPL-3.0-or-later
"""Spike 1b: diagnose why simulated input has no effect. Screenshots after each step.

    & $B --factory-startup --enable-event-simulate --python spikes/s1b_event_debug.py
"""
import os
import sys

import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _gui_runner import OUT_DIR, area_region, run, simulate, tap, view3d_area  # noqa: E402


def win():
    return bpy.context.window_manager.windows[0]


def shot(label):
    def step(results):
        path = os.path.join(OUT_DIR, f"s1b_{label}.png")
        os.makedirs(OUT_DIR, exist_ok=True)
        with bpy.context.temp_override(window=win()):
            bpy.ops.screen.screenshot(filepath=path)
        w = win()
        results.setdefault("windows", []).append({
            "label": label, "n_windows": len(bpy.context.window_manager.windows),
            "size": [w.width, w.height], "loc": list(bpy.context.view_layer.objects.active.location),
        })
    step.__name__ = "shot_" + label
    return step


def center(results):
    reg = area_region(view3d_area(win().screen))
    results["center"] = [reg.x + reg.width // 2, reg.y + reg.height // 2]
    results["region"] = [reg.x, reg.y, reg.width, reg.height]


def esc(results):
    tap(win(), "ESC")


def click_center(results):
    x, y = results["center"]
    simulate(win(), "MOUSEMOVE", x=x, y=y)
    tap(win(), "LEFTMOUSE", x=x, y=y)


def grab(results):
    x, y = results["center"]
    simulate(win(), "MOUSEMOVE", x=x, y=y)
    tap(win(), "G", x=x, y=y)
    simulate(win(), "MOUSEMOVE", x=x + 150, y=y)
    tap(win(), "LEFTMOUSE", x=x + 150, y=y)


run("s1b_event_debug", [
    (0.8, center), (0.5, shot("start")), (0.8, esc), (0.5, shot("after_esc")),
    (0.8, click_center), (0.5, shot("after_click")), (0.8, grab), (0.5, shot("after_grab")),
])
