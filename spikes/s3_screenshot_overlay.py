# SPDX-License-Identifier: GPL-3.0-or-later
"""Spikes 3 + 4: screenshot APIs and overlay drawing in a GUI session.

3. Window.screenshot (new in 5.2) vs the screen.screenshot_area operator: availability,
   signature, return value, timing.
4. Viewport overlay with gpu/blf: an instruction card (filled box + wrapped text), an
   object outline marker, and an outline around the Properties editor region. Draw
   timings per call, behaviour at UI scale 1.0 / 1.5 / 2.0, and clean removal.

    & $B --factory-startup --enable-event-simulate --python spikes/s3_screenshot_overlay.py
Output: spikes/out/s3_screenshot_overlay.json and s3_*.png
"""
import os
import sys
import time

import blf
import bpy
import gpu
from bpy_extras.view3d_utils import location_3d_to_region_2d
from gpu_extras.batch import batch_for_shader

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _gui_runner import OUT_DIR, run, tap  # noqa: E402

draw_ms = {"view3d": [], "properties": []}
handles = []


def win():
    return bpy.context.window_manager.windows[0]


def ui_scale():
    return bpy.context.preferences.system.ui_scale


def draw_rect_outline(shader, x, y, w, h, color, width=2.0):
    pts = [(x, y), (x + w, y), (x + w, y + h), (x, y + h), (x, y)]
    gpu.state.line_width_set(width)
    batch = batch_for_shader(shader, "LINE_STRIP", {"pos": pts})
    shader.uniform_float("color", color)
    batch.draw(shader)


def draw_view3d():
    t0 = time.perf_counter()
    s = ui_scale()
    shader = gpu.shader.from_builtin("UNIFORM_COLOR")
    gpu.state.blend_set("ALPHA")
    # Instruction card, bottom-left, sized in UI-scaled pixels.
    x, y, w, h = 20 * s, 20 * s, 360 * s, 90 * s
    card = batch_for_shader(shader, "TRIS", {"pos": [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]},
                            indices=[(0, 1, 2), (0, 2, 3)])
    shader.uniform_float("color", (0.08, 0.08, 0.1, 0.85))
    card.draw(shader)
    draw_rect_outline(shader, x, y, w, h, (1.0, 0.6, 0.1, 1.0))
    font = 0
    blf.size(font, 15 * s)
    blf.color(font, 1, 1, 1, 1)
    blf.position(font, x + 12 * s, y + h - 28 * s, 0)
    blf.draw(font, "Step 2 of 6: Scale the cube to 30 x 20 x 10 cm")
    blf.size(font, 12 * s)
    blf.color(font, 0.8, 0.8, 0.85, 1)
    blf.position(font, x + 12 * s, y + h - 52 * s, 0)
    blf.draw(font, "Press N, then type the values under Item > Dimensions")
    # Marker at the active object's origin (semantic target -> projected each frame).
    ob = bpy.context.view_layer.objects.active
    region, rv3d = bpy.context.region, bpy.context.region_data
    if ob is not None and rv3d is not None:
        p = location_3d_to_region_2d(region, rv3d, ob.matrix_world.translation)
        if p is not None:
            r = 40 * s
            draw_rect_outline(shader, p.x - r, p.y - r, 2 * r, 2 * r, (0.2, 0.9, 1.0, 1.0), 3.0)
    gpu.state.blend_set("NONE")
    draw_ms["view3d"].append((time.perf_counter() - t0) * 1000)


def draw_properties():
    t0 = time.perf_counter()
    region = bpy.context.region
    shader = gpu.shader.from_builtin("UNIFORM_COLOR")
    draw_rect_outline(shader, 2, 2, region.width - 4, region.height - 4, (1.0, 0.6, 0.1, 1.0), 4.0)
    draw_ms["properties"].append((time.perf_counter() - t0) * 1000)


def setup(results):
    tap(win(), "ESC")
    results["window_has_screenshot"] = hasattr(win(), "screenshot")
    fn = bpy.types.Window.bl_rna.functions.get("screenshot")
    results["window_screenshot_rna"] = None if fn is None else {
        "description": fn.description,
        "params": [(p.identifier, p.type, p.is_output) for p in fn.parameters],
    }
    handles.append((bpy.types.SpaceView3D, bpy.types.SpaceView3D.draw_handler_add(draw_view3d, (), "WINDOW", "POST_PIXEL")))
    handles.append((bpy.types.SpaceProperties, bpy.types.SpaceProperties.draw_handler_add(draw_properties, (), "WINDOW", "POST_PIXEL")))
    for area in win().screen.areas:
        area.tag_redraw()


def try_window_screenshot(results):
    out = {}
    if hasattr(win(), "screenshot"):
        t0 = time.perf_counter()
        try:
            value = win().screenshot()
            out["ms"] = round((time.perf_counter() - t0) * 1000, 2)
            out["type"] = type(value).__name__
            out["repr"] = repr(value)[:200]
            out["size"] = list(getattr(value, "size", [])) or None
            if isinstance(value, memoryview):
                out["shape"] = list(value.shape)
                out["format"] = value.format
                out["nbytes"] = value.nbytes
            out["doc"] = (getattr(win().screenshot, "__doc__", None) or "")[:400]
            if hasattr(value, "save"):
                path = os.path.join(OUT_DIR, "s3_window_screenshot.png")
                try:
                    value.save(filepath=path)
                    out["saved"] = path
                except Exception as exc:
                    out["save_error"] = repr(exc)
        except Exception as exc:
            out["error"] = repr(exc)
    results["window_screenshot"] = out


def area_shot(label):
    def step(results):
        area = next(a for a in win().screen.areas if a.type == "VIEW_3D")
        path = os.path.join(OUT_DIR, f"s3_view3d_{label}.png")
        t0 = time.perf_counter()
        with bpy.context.temp_override(window=win(), area=area):
            bpy.ops.screen.screenshot_area(filepath=path)
        results.setdefault("area_shots", []).append({"label": label, "ms": round((time.perf_counter() - t0) * 1000, 2)})
        path = os.path.join(OUT_DIR, f"s3_window_{label}.png")
        with bpy.context.temp_override(window=win()):
            bpy.ops.screen.screenshot(filepath=path)
        results.setdefault("draw_stats", []).append({
            "label": label,
            "ui_scale": ui_scale(),
            "region_overlap": bpy.context.preferences.system.use_region_overlap,
            "view3d_regions": {r.type: [r.x, r.y, r.width, r.height] for r in area.regions},
            **{k: {"calls": len(v), "mean_ms": round(sum(v) / len(v), 3) if v else None,
                   "max_ms": round(max(v), 3) if v else None} for k, v in draw_ms.items()},
        })
        for v in draw_ms.values():
            v.clear()
    step.__name__ = "area_shot_" + label
    return step


def set_scale(value):
    def step(results):
        bpy.context.preferences.view.ui_scale = value
        for area in win().screen.areas:
            area.tag_redraw()
    step.__name__ = f"set_scale_{value}"
    return step


def orbit(results):
    # Rotate the view a little so the marker must be reprojected; forces redraws.
    for area in win().screen.areas:
        if area.type == "VIEW_3D":
            area.spaces.active.region_3d.view_rotation.rotate(__import__("mathutils").Euler((0, 0, 0.4)))
            area.tag_redraw()


def remove(results):
    for space, h in handles:
        space.draw_handler_remove(h, "WINDOW")
    handles.clear()
    for v in draw_ms.values():
        v.clear()
    for area in win().screen.areas:
        area.tag_redraw()


def after_remove(results):
    results["draw_calls_after_remove"] = {k: len(v) for k, v in draw_ms.items()}


D = 0.8
run("s3_screenshot_overlay", [
    (D, setup), (D, try_window_screenshot),
    (D, orbit), (D, area_shot("scale_1.0")),
    (D, set_scale(1.5)), (D, orbit), (D, area_shot("scale_1.5")),
    (D, set_scale(2.0)), (D, orbit), (D, area_shot("scale_2.0")),
    (D, set_scale(1.0)), (D, remove), (D, orbit), (D, after_remove),
])
