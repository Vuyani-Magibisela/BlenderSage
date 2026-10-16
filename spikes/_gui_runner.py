# SPDX-License-Identifier: GPL-3.0-or-later
"""Shared helper for GUI spikes: run a list of steps on timers, save JSON results, quit.

A spike script builds a list of (delay_seconds, callable) steps and calls run().
Each callable receives the shared `results` dict. Results are written to
spikes/out/<name>.json and Blender quits with exit code 0 (or 1 if a step raised).

Launch from the repo root (Windows):
    & $B --factory-startup --enable-event-simulate --python spikes/<spike>.py
"""
import json
import os
import time
import traceback

import bpy

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")


def view3d_area(screen=None):
    screen = screen or bpy.context.window_manager.windows[0].screen
    return next(a for a in screen.areas if a.type == "VIEW_3D")


def area_region(area, region_type="WINDOW"):
    return next(r for r in area.regions if r.type == region_type)


_mouse = {"x": 0, "y": 0}


def simulate(win, type_, value="PRESS", **kw):
    """Send one simulated event. Coordinates are window pixels.

    Every event carries the last mouse position: in Blender 5.2 a key event without
    x/y is handled at (0, 0), outside the 3D viewport, and the viewport keymap ignores it.
    """
    if type_ == "MOUSEMOVE":
        value = "NOTHING"  # Blender 5.2 rejects any other value for motion events
        _mouse["x"], _mouse["y"] = kw["x"], kw["y"]
    kw.setdefault("x", _mouse["x"])
    kw.setdefault("y", _mouse["y"])
    return win.event_simulate(type=type_, value=value, **kw)


def tap(win, type_, **kw):
    simulate(win, type_, "PRESS", **kw)
    simulate(win, type_, "RELEASE", **kw)


def run(name, steps):
    results = {"name": name, "blender": bpy.app.version_string, "steps": [], "errors": []}
    queue = list(steps)
    state = {"failed": False}

    def finish():
        os.makedirs(OUT_DIR, exist_ok=True)
        path = os.path.join(OUT_DIR, name + ".json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(results, fh, indent=1, default=repr)
        print("SPIKE-RESULT", path)
        # Quit without the save prompt; exit code signals step failures.
        os._exit(1 if state["failed"] else 0)

    def tick():
        if not queue:
            finish()
            return None
        delay, fn = queue.pop(0)
        label = getattr(fn, "__name__", repr(fn))
        t0 = time.perf_counter()
        try:
            fn(results)
            results["steps"].append({"step": label, "ms": round((time.perf_counter() - t0) * 1000, 2)})
        except Exception:
            state["failed"] = True
            results["errors"].append({"step": label, "trace": traceback.format_exc()})
        return delay if queue else 0.2

    # persistent=True: non-persistent timers are dropped when a .blend file is loaded.
    bpy.app.timers.register(tick, first_interval=1.5, persistent=True)
