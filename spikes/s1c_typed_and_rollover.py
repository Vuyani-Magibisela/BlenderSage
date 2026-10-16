# SPDX-License-Identifier: GPL-3.0-or-later
"""Spike 1c: typed numeric input in modal tools, and report/operator-history rollover.

    & $B --factory-startup --enable-event-simulate --python spikes/s1c_typed_and_rollover.py
Output: spikes/out/s1c_typed_and_rollover.json
"""
import os
import sys

import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _gui_runner import area_region, run, simulate, tap, view3d_area  # noqa: E402

DIGITS = {"0": "ZERO", "1": "ONE", "2": "TWO", "4": "FOUR", "5": "FIVE"}


def win():
    return bpy.context.window_manager.windows[0]


def setup(results):
    reg = area_region(view3d_area(win().screen))
    x, y = reg.x + reg.width // 2, reg.y + reg.height // 2
    tap(win(), "ESC")
    simulate(win(), "MOUSEMOVE", x=x, y=y)


def type_number(text):
    for ch in text:
        simulate(win(), DIGITS[ch], "PRESS", unicode=ch)
        simulate(win(), DIGITS[ch], "RELEASE")


def rotate_45(results):
    tap(win(), "R")
    tap(win(), "Z")
    type_number("45")
    tap(win(), "RET")


def scale_2(results):
    tap(win(), "S")
    type_number("2")
    tap(win(), "RET")


def record_transform(results):
    ob = bpy.context.view_layer.objects.active
    results["after_typed"] = {
        "rotation_z_deg": round(ob.rotation_euler.z * 57.29578, 3),
        "scale": [round(v, 4) for v in ob.scale],
        "last_reports": [r.message[:80] for r in list(bpy.context.window_manager.reports)[-2:]],
    }


def rollover(results):
    wm = bpy.context.window_manager
    area = view3d_area(win().screen)
    region = area_region(area)
    counts = []
    with bpy.context.temp_override(window=win(), area=area, region=region):
        for i in range(400):
            bpy.ops.transform.translate(value=(0.001, 0, 0))
            if i in (0, 9, 31, 32, 63, 99, 199, 399):
                uids = [r.session_uid for r in wm.reports]
                counts.append({
                    "after_ops": i + 1,
                    "reports_len": len(uids),
                    "min_uid": min(uids) if uids else None,
                    "max_uid": max(uids) if uids else None,
                    "operators_len": len(wm.operators),
                })
    results["rollover"] = counts


run("s1c_typed_and_rollover", [
    (0.6, setup), (0.6, rotate_45), (0.6, scale_2), (0.4, record_transform), (0.4, rollover),
])
