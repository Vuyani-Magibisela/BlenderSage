# SPDX-License-Identifier: GPL-3.0-or-later
"""Spike 2b: which signals fire when a user edits a property in the UI?

Simulates real UI edits (type a value into N-panel Dimensions X; drag the Bevel
Amount slider) and, for comparison, a Python assignment and a viewport grab.
For each edit it records msgbus callbacks, depsgraph updates, new reports and the
operator history.

Field positions come from the 1920x1009 factory layout screenshot made by
s2a_layout_shot.py (window coordinates, origin bottom-left). Spike-only.

    & $B --factory-startup --enable-event-simulate --python spikes/s2b_property_edits.py
"""
import os
import sys

import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _gui_runner import area_region, run, simulate, tap, view3d_area  # noqa: E402

DIM_X_FIELD = (1425, 1009 - 410)
BEVEL_AMOUNT_FIELD = (1806, 1009 - 395)
LOCATION_X_FIELD = (1400, 1009 - 142)
OWNER = object()
log = {"msgbus": [], "depsgraph": []}
seen_reports = set()


def win():
    return bpy.context.window_manager.windows[0]


def on_msg(key):
    def cb(*_):
        log["msgbus"].append(key)
    return cb


def on_depsgraph(scene, depsgraph):
    log["depsgraph"].append(sorted(
        f"{u.id.name}{'[T]' if u.is_updated_transform else ''}{'[G]' if u.is_updated_geometry else ''}"
        for u in depsgraph.updates
    ))


def setup(results):
    w = win()
    reg = area_region(view3d_area(w.screen))
    tap(w, "ESC")
    simulate(w, "MOUSEMOVE", x=reg.x + reg.width // 2, y=reg.y + reg.height // 2)
    tap(w, "N")
    cube = bpy.data.objects["Cube"]
    bevel = cube.modifiers.new("Bevel", "BEVEL")
    next(a for a in w.screen.areas if a.type == "PROPERTIES").spaces.active.context = "MODIFIER"
    bpy.msgbus.subscribe_rna(key=bevel.path_resolve("width", False), owner=OWNER, args=(), notify=on_msg("bevel.width"))
    bpy.msgbus.subscribe_rna(key=cube.path_resolve("scale", False), owner=OWNER, args=(), notify=on_msg("cube.scale"))
    bpy.msgbus.subscribe_rna(key=cube.path_resolve("location", False), owner=OWNER, args=(), notify=on_msg("cube.location"))
    bpy.msgbus.subscribe_rna(key=(bpy.types.Object, "scale"), owner=OWNER, args=(), notify=on_msg("Object.scale(any)"))
    bpy.app.handlers.depsgraph_update_post.append(on_depsgraph)


def record(label):
    def step(results):
        cube = bpy.data.objects["Cube"]
        wm = bpy.context.window_manager
        new = [f"{r.type}: {r.message[:100]}" for r in wm.reports if r.session_uid not in seen_reports]
        seen_reports.update(r.session_uid for r in wm.reports)
        results.setdefault("edits", []).append({
            "edit": label,
            "msgbus": list(log["msgbus"]),
            "depsgraph_calls": len(log["depsgraph"]),
            "depsgraph_ids": sorted({i for call in log["depsgraph"] for i in call}),
            "new_reports": new,
            "operators": [o.bl_idname for o in wm.operators],
            "dimensions_x": round(cube.dimensions.x, 4),
            "scale": [round(v, 4) for v in cube.scale],
            "location": [round(v, 4) for v in cube.location],
            "bevel_width": round(cube.modifiers["Bevel"].width, 4),
        })
        log["msgbus"].clear()
        log["depsgraph"].clear()
    step.__name__ = "record_" + label
    return step


def ui_type_dimension(results):
    w = win()
    x, y = DIM_X_FIELD
    simulate(w, "MOUSEMOVE", x=x, y=y)
    tap(w, "LEFTMOUSE")  # click (no drag) on a number field enters text editing
    tap(w, "A", ctrl=True)
    simulate(w, "THREE", "PRESS", unicode="3")
    simulate(w, "THREE", "RELEASE")
    tap(w, "RET")


def hover(field):
    def step(results):
        simulate(win(), "MOUSEMOVE", x=field[0], y=field[1])
    step.__name__ = f"hover_{field[0]}_{field[1]}"
    return step


def click_type(key, char):
    """Click a hovered number field to enter text editing, replace the text, confirm."""
    def step(results):
        w = win()
        tap(w, "LEFTMOUSE")
        tap(w, "A", ctrl=True)
        simulate(w, key, "PRESS", unicode=char)
        simulate(w, key, "RELEASE")
        tap(w, "RET")
    step.__name__ = f"click_type_{char}"
    return step


def ui_drag_bevel(results):
    w = win()
    x, y = BEVEL_AMOUNT_FIELD
    simulate(w, "MOUSEMOVE", x=x, y=y)
    simulate(w, "LEFTMOUSE", "PRESS")
    for dx in (5, 15, 30, 45, 60):
        simulate(w, "MOUSEMOVE", x=x + dx, y=y)
    simulate(w, "LEFTMOUSE", "RELEASE")


def python_set_width(results):
    bpy.data.objects["Cube"].modifiers["Bevel"].width = 0.25


def viewport_grab(results):
    w = win()
    reg = area_region(view3d_area(w.screen))
    x, y = reg.x + reg.width // 3, reg.y + reg.height // 2
    simulate(w, "MOUSEMOVE", x=x, y=y)
    tap(w, "G")
    simulate(w, "MOUSEMOVE", x=x + 80, y=y)
    simulate(w, "MOUSEMOVE", x=x + 160, y=y)
    tap(w, "LEFTMOUSE")


def teardown(results):
    bpy.msgbus.clear_by_owner(OWNER)
    bpy.app.handlers.depsgraph_update_post.remove(on_depsgraph)


D = 0.8
run("s2b_property_edits", [
    (D, setup), (D, record("setup")),
    (D, ui_type_dimension), (D, record("ui_type_dimension_x")),
    (D, hover(LOCATION_X_FIELD)), (D, click_type("ONE", "1")), (D, record("ui_type_location_x")),
    (D, hover(BEVEL_AMOUNT_FIELD)), (D, click_type("TWO", "2")), (D, record("ui_type_bevel_amount")),
    (D, ui_drag_bevel), (D, record("ui_drag_bevel_amount")),
    (D, python_set_width), (D, record("python_set_bevel_width")),
    (D, viewport_grab), (D, record("viewport_grab")),
    (0.2, teardown),
])
