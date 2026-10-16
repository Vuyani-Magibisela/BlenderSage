# SPDX-License-Identifier: GPL-3.0-or-later
"""Scene state snapshots used by completion checks."""
import bpy

from extension_loader import load_extension


def _cube(snapshot):
    return next(o for o in snapshot["objects"] if o["name"] == "Cube")


def test_snapshot_of_factory_scene():
    snap = load_extension().blender.state.snapshot()
    assert snap["mode"] == "OBJECT"
    assert snap["active"] == "Cube"
    cube = _cube(snap)
    assert cube["type"] == "MESH"
    assert [round(v, 4) for v in cube["dimensions"]] == [2.0, 2.0, 2.0]
    assert [round(v, 4) for v in cube["scale"]] == [1.0, 1.0, 1.0]
    assert cube["materials"] == ["Material"]
    assert cube["tag"] is None


def test_snapshot_includes_modifier_settings():
    ext = load_extension()
    cube = bpy.data.objects["Cube"]
    mod = cube.modifiers.new("Bevel", "BEVEL")
    try:
        settings = _cube(ext.blender.state.snapshot())["modifiers"][0]["settings"]
        assert abs(settings["width"] - 0.1) < 1e-6
        assert settings["segments"] == 1
    finally:
        cube.modifiers.remove(mod)


def test_snapshot_reads_target_tag():
    ext = load_extension()
    cube = bpy.data.objects["Cube"]
    cube[ext.blender.state.TAG_PROPERTY] = "organiser"
    try:
        assert _cube(ext.blender.state.snapshot())["tag"] == "organiser"
    finally:
        del cube[ext.blender.state.TAG_PROPERTY]
