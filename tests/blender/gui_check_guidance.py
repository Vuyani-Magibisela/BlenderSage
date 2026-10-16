# SPDX-License-Identifier: GPL-3.0-or-later
"""GUI check for the guidance prototype: screenshots and draw timings.

Opens a fresh window, runs the example lesson and captures the states that cannot
be checked headless. Results: spikes/out/gui_check_guidance.json and *.png.

    & $B --factory-startup --enable-event-simulate --python tests/blender/gui_check_guidance.py
"""
import os
import sys
import time

import bpy
from mathutils import Matrix

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "spikes"))
from _gui_runner import OUT_DIR, area_region, run, simulate, tap, view3d_area  # noqa: E402
from extension_loader import load_extension  # noqa: E402

ext = load_extension()
runtime = ext.blender.guidance.runtime
overlay = ext.blender.guidance.overlay
timings = {}


def timed(name, fn):
    def wrapper(*args):
        t0 = time.perf_counter()
        fn(*args)
        timings.setdefault(name, []).append((time.perf_counter() - t0) * 1000)
    return wrapper


def win():
    return bpy.context.window_manager.windows[0]


def shot(label):
    def step(results):
        path = os.path.join(OUT_DIR, f"guidance_{label}.png")
        with bpy.context.temp_override(window=win()):
            bpy.ops.screen.screenshot(filepath=path)
        stats = {k: {"calls": len(v), "mean_ms": round(sum(v) / len(v), 3), "max_ms": round(max(v), 3)}
                 for k, v in timings.items() if v}
        results.setdefault("shots", []).append({"label": label, "scale": bpy.context.preferences.view.ui_scale,
                                                "timings": stats})
        timings.clear()
    step.__name__ = "shot_" + label
    return step


def setup(results):
    for name in ("draw_card", "draw_target", "draw_editor_outline"):
        setattr(overlay, name, timed(name, getattr(overlay, name)))
    ext.register()
    w = win()
    reg = area_region(view3d_area(w.screen))
    tap(w, "ESC")
    simulate(w, "MOUSEMOVE", x=reg.x + reg.width // 2, y=reg.y + reg.height // 2)
    tap(w, "N")


def open_tab(results):
    area_region(view3d_area(), "UI").active_panel_category = "BlenderSage"
    runtime.start_lesson(runtime.load_example_lesson())


def to_size_step(results):
    runtime.go_next()


def to_bevel_step(results):
    cube = bpy.data.objects["Cube"]
    cube.dimensions = (0.3, 0.2, 0.1)
    bpy.context.view_layer.update()
    runtime.refresh()
    runtime.go_next()  # -> apply scale
    cube.data.transform(Matrix.Diagonal(cube.scale.to_4d()))
    cube.scale = (1, 1, 1)
    bpy.context.view_layer.update()
    runtime.refresh()
    runtime.go_next()  # -> add bevel
    for area in win().screen.areas:
        if area.type == "PROPERTIES":
            area.spaces.active.context = "MODIFIER"


def make_ambiguous(results):
    cube = bpy.data.objects["Cube"]
    dup = cube.copy()
    dup.data = cube.data.copy()
    dup.location.x += 0.6
    bpy.context.collection.objects.link(dup)
    runtime.refresh()
    results["ambiguous_status"] = runtime.last_evaluation().resolutions["organiser"].status


def resolve_ambiguity(results):
    bpy.context.view_layer.objects.active = bpy.data.objects["Cube"]
    runtime.use_selected("organiser")
    results["after_use_selected"] = runtime.last_evaluation().resolutions["organiser"].name


def collapse(results):
    runtime.toggle_card()


def expand(results):
    runtime.toggle_card()


def set_scale(value):
    def step(results):
        bpy.context.preferences.view.ui_scale = value
    step.__name__ = f"scale_{value}"
    return step


def teardown(results):
    bpy.context.preferences.view.ui_scale = 1.0
    ext.unregister()
    results["lifecycle_after_unregister"] = ext.blender.lifecycle.active_counts()


D = 0.8
run("gui_check_guidance", [
    (D, setup), (D, open_tab), (D, shot("step1_scale1.0")),
    (D, to_size_step), (D, shot("step2_scale1.0")),
    (D, to_bevel_step), (D, shot("step4_properties_outline_scale1.0")),
    (D, set_scale(1.5)), (D, shot("step4_scale1.5")),
    (D, set_scale(2.0)), (D, shot("step4_scale2.0")),
    (D, set_scale(1.0)), (D, make_ambiguous), (D, shot("ambiguous_scale1.0")),
    (D, resolve_ambiguity), (D, shot("after_use_selected")),
    (D, collapse), (D, shot("collapsed")), (D, expand),
    (0.3, teardown),
])
