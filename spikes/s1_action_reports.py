# SPDX-License-Identifier: GPL-3.0-or-later
"""Spike 1: what does Blender 5.2 expose when a user performs actions?

Drives a fresh GUI session with simulated keyboard/mouse input and records, after
each action: new WindowManager.reports (by session_uid), the operator history
(WindowManager.operators), and basic scene state. Also counts undo/redo and
depsgraph handler calls.

    & $B --factory-startup --enable-event-simulate --python spikes/s1_action_reports.py
Output: spikes/out/s1_action_reports.json
"""
import os
import sys
import time

import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _gui_runner import area_region, run, simulate, tap, view3d_area  # noqa: E402

seen_uids = set()
counters = {"undo_post": 0, "redo_post": 0, "depsgraph_update_post": 0}
report_log = []  # every report seen, with the time the poller saw it
T0 = time.perf_counter()


def poll_reports():
    for r in bpy.context.window_manager.reports:
        if r.session_uid not in seen_uids:
            seen_uids.add(r.session_uid)
            report_log.append({
                "uid": r.session_uid,
                "type": r.type,
                "message": r.message,
                "seen_s": round(time.perf_counter() - T0, 3),
            })
    return 0.02


def on_undo(*_):
    counters["undo_post"] += 1


def on_redo(*_):
    counters["redo_post"] += 1


def on_depsgraph(*_):
    counters["depsgraph_update_post"] += 1


def op_props(op):
    out = {}
    for p in op.properties.bl_rna.properties:
        if p.identifier == "rna_type":
            continue
        try:
            v = getattr(op.properties, p.identifier)
            out[p.identifier] = list(v) if hasattr(v, "__len__") and not isinstance(v, str) else v
        except Exception as exc:
            out[p.identifier] = repr(exc)
    return out


def snapshot(label):
    def step(results):
        wm = bpy.context.window_manager
        ob = bpy.context.view_layer.objects.active
        results.setdefault("snapshots", []).append({
            "label": label,
            "t_s": round(time.perf_counter() - T0, 3),
            "new_reports": [r for r in report_log if r.get("label") is None],
            "operators": [{"id": o.bl_idname, "name": o.name, "props": op_props(o)} for o in wm.operators],
            "mode": bpy.context.mode,
            "objects": sorted(o.name for o in bpy.context.scene.objects),
            "active": None if ob is None else {
                "name": ob.name,
                "location": [round(v, 4) for v in ob.location],
                "rotation": [round(v, 4) for v in ob.rotation_euler],
                "scale": [round(v, 4) for v in ob.scale],
                "modifiers": [m.type for m in ob.modifiers],
            },
            "counters": dict(counters),
        })
        for r in report_log:
            r.setdefault("label", label)
    step.__name__ = "snapshot_" + label
    return step


def setup(results):
    bpy.app.timers.register(poll_reports, first_interval=0.02, persistent=True)
    bpy.app.handlers.undo_post.append(on_undo)
    bpy.app.handlers.redo_post.append(on_redo)
    bpy.app.handlers.depsgraph_update_post.append(on_depsgraph)
    win = bpy.context.window_manager.windows[0]
    area = view3d_area(win.screen)
    reg = area_region(area)
    results["viewport_center"] = [reg.x + reg.width // 2, reg.y + reg.height // 2]
    tap(win, "ESC")  # close the splash screen
    simulate(win, "MOUSEMOVE", x=results["viewport_center"][0], y=results["viewport_center"][1])


def win():
    return bpy.context.window_manager.windows[0]


def move_by(results, dx, dy):
    cx, cy = results["viewport_center"]
    simulate(win(), "MOUSEMOVE", x=cx + dx, y=cy + dy)


def a_grab_confirm(results):
    move_by(results, 0, 0)
    tap(win(), "G")
    move_by(results, 60, 0)
    move_by(results, 120, 0)
    tap(win(), "LEFTMOUSE")


def a_grab_cancel(results):
    move_by(results, 0, 0)
    tap(win(), "G")
    move_by(results, 80, 40)
    tap(win(), "ESC")


def a_rotate_typed(results):
    for k in ("R", "Z", "FOUR", "FIVE", "RET"):
        tap(win(), k)


def a_scale_typed(results):
    for k in ("S", "TWO", "RET"):
        tap(win(), k)


def a_duplicate(results):
    move_by(results, 0, 0)
    tap(win(), "D", shift=True)
    move_by(results, 0, 100)
    tap(win(), "LEFTMOUSE")


def a_undo(results):
    tap(win(), "Z", ctrl=True)


def a_redo(results):
    tap(win(), "Z", ctrl=True, shift=True)


def a_subdivision_hotkey(results):
    tap(win(), "TWO", ctrl=True)


def a_edit_extrude(results):
    move_by(results, 0, 0)
    tap(win(), "TAB")
    tap(win(), "E")
    move_by(results, 0, 60)
    tap(win(), "LEFTMOUSE")
    tap(win(), "TAB")


def a_python_operator(results):
    bpy.ops.mesh.primitive_uv_sphere_add(location=(3, 0, 0))


def a_teardown(results):
    bpy.app.timers.unregister(poll_reports)
    bpy.app.handlers.undo_post.remove(on_undo)
    bpy.app.handlers.redo_post.remove(on_redo)
    bpy.app.handlers.depsgraph_update_post.remove(on_depsgraph)
    results["all_reports"] = report_log


D = 0.6  # seconds between steps so the event loop handles simulated input
steps = [(D, setup), (D, snapshot("baseline"))]
for action in (a_grab_confirm, a_grab_cancel, a_rotate_typed, a_scale_typed, a_duplicate,
               a_undo, a_redo, a_subdivision_hotkey, a_edit_extrude, a_python_operator):
    steps += [(D, action), (D, snapshot(action.__name__))]
steps.append((0.2, a_teardown))
run("s1_action_reports", steps)
