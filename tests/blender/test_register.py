# SPDX-License-Identifier: GPL-3.0-or-later
"""Enabling then disabling the extension must leave Blender as it was."""
import bpy

from extension_loader import load_extension

PANEL = "BLENDERSAGE_PT_lesson"


def _handler_counts():
    return {
        name: len(getattr(bpy.app.handlers, name))
        for name in dir(bpy.app.handlers)
        if isinstance(getattr(bpy.app.handlers, name), list)
    }


def test_register_adds_sidebar_panel():
    ext = load_extension()
    ext.register()
    try:
        panel = getattr(bpy.types, PANEL)
        assert panel.bl_space_type == "VIEW_3D"
        assert panel.bl_region_type == "UI"
        assert panel.bl_category == "BlenderSage"
    finally:
        ext.unregister()


def test_unregister_removes_panel():
    ext = load_extension()
    ext.register()
    ext.unregister()
    assert not hasattr(bpy.types, PANEL)


def test_enable_disable_leaves_no_handlers_timers_or_subscriptions():
    before = _handler_counts()
    ext = load_extension()
    ext.register()
    ext.unregister()
    assert _handler_counts() == before
    assert ext.blender.lifecycle.active_counts() == {
        "app_handlers": 0, "timers": 0, "draw_handlers": 0, "msgbus_owners": 0,
    }


def test_enable_disable_twice():
    before = _handler_counts()
    for _ in range(2):
        ext = load_extension()
        ext.register()
        ext.unregister()
    assert _handler_counts() == before
    assert not hasattr(bpy.types, PANEL)
