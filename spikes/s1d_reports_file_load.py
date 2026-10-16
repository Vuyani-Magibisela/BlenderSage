# SPDX-License-Identifier: GPL-3.0-or-later
"""Spike 1d: do WindowManager.reports survive saving and loading a .blend file?

Background mode (-b) stores no reports at all, so this needs a GUI session.

    & $B --factory-startup --python spikes/s1d_reports_file_load.py
Output: spikes/out/s1d_reports_file_load.json
"""
import os
import sys
import tempfile

import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _gui_runner import run  # noqa: E402

PATH = os.path.join(tempfile.mkdtemp(), "s1d.blend")


def reports():
    return [[r.session_uid, r.type, r.message[:50]] for r in bpy.context.window_manager.reports]


def ops(results):
    for _ in range(3):
        bpy.ops.mesh.primitive_cube_add()
    results["after_ops"] = reports()


def save(results):
    bpy.ops.wm.save_as_mainfile(filepath=PATH)
    results["after_save"] = reports()


def load(results):
    bpy.ops.wm.open_mainfile(filepath=PATH)


def after_load(results):
    results["after_load"] = reports()
    bpy.ops.mesh.primitive_cube_add()
    results["after_load_then_op"] = reports()


run("s1d_reports_file_load", [(0.5, ops), (0.5, save), (1.0, load), (0.5, after_load)])
