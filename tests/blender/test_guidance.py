# SPDX-License-Identifier: GPL-3.0-or-later
"""Running a lesson: hooks, navigation and targets."""
import bpy

from extension_loader import load_extension


def _handler_counts():
    return {
        name: len(getattr(bpy.app.handlers, name))
        for name in dir(bpy.app.handlers)
        if isinstance(getattr(bpy.app.handlers, name), list)
    }


def _start():
    ext = load_extension()
    ext.register()
    runtime = ext.blender.guidance.runtime
    runtime.start_lesson(runtime.load_example_lesson())
    return ext, runtime


def test_start_adds_timer_and_draw_handlers_and_stop_removes_them():
    ext, runtime = _start()
    try:
        counts = ext.blender.lifecycle.active_counts()
        assert counts["timers"] == 1
        assert counts["draw_handlers"] >= 2
        runtime.stop_lesson()
        assert ext.blender.lifecycle.active_counts() == dict.fromkeys(counts, 0)
        assert runtime.active_session() is None
    finally:
        ext.unregister()


def test_disable_mid_lesson_leaves_nothing_behind():
    before = _handler_counts()
    ext, runtime = _start()
    ext.unregister()
    assert _handler_counts() == before
    assert ext.blender.lifecycle.active_counts() == dict.fromkeys(
        ("app_handlers", "timers", "draw_handlers", "msgbus_owners"), 0)
    assert runtime.active_session() is None


def test_refresh_marks_completed_step():
    ext, runtime = _start()
    try:
        runtime.refresh()
        assert "find-cube" in runtime.active_session().completed
        assert runtime.last_evaluation().complete
    finally:
        ext.unregister()


def test_navigation_does_not_change_the_scene():
    ext, runtime = _start()
    try:
        before = ext.blender.state.snapshot()
        runtime.refresh()
        runtime.go_next()
        runtime.skip()
        runtime.go_back()
        runtime.go_back()
        assert runtime.active_session().current.id == "find-cube"
        assert ext.blender.state.snapshot() == before
    finally:
        ext.unregister()


def test_lesson_survives_loading_another_file():
    ext, runtime = _start()
    try:
        timer = runtime.refresh
        bpy.ops.wm.read_homefile(use_empty=True)
        assert runtime.active_session() is not None
        assert bpy.app.timers.is_registered(timer)
        runtime.refresh()  # no organiser in an empty file: must not raise
        assert runtime.last_evaluation().resolutions["organiser"].status == "missing"
    finally:
        ext.unregister()


def test_use_selected_tags_the_active_object():
    ext, runtime = _start()
    try:
        bpy.data.objects["Cube"].name = "Box"  # name rule no longer matches
        runtime.refresh()
        assert runtime.last_evaluation().resolutions["organiser"].status == "missing"
        bpy.context.view_layer.objects.active = bpy.data.objects["Box"]
        runtime.use_selected("organiser")
        runtime.refresh()
        assert runtime.last_evaluation().resolutions["organiser"].name == "Box"
    finally:
        ext.unregister()
