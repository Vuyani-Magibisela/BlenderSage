# SPDX-License-Identifier: GPL-3.0-or-later
"""Every handler, timer, draw handler and msgbus subscription added through
lifecycle must be gone after remove_all()."""
import bpy

from extension_loader import load_extension


def _noop(*_args):
    return None


def test_remove_all_removes_app_handler():
    lifecycle = load_extension().blender.lifecycle
    lifecycle.add_app_handler("load_post", _noop)
    assert _noop in bpy.app.handlers.load_post
    lifecycle.remove_all()
    assert _noop not in bpy.app.handlers.load_post


def test_remove_all_removes_timer():
    lifecycle = load_extension().blender.lifecycle

    def tick():
        return 1.0

    lifecycle.add_timer(tick, first_interval=10.0)
    assert bpy.app.timers.is_registered(tick)
    lifecycle.remove_all()
    assert not bpy.app.timers.is_registered(tick)


def test_remove_all_removes_draw_handler():
    lifecycle = load_extension().blender.lifecycle
    lifecycle.add_draw_handler(bpy.types.SpaceView3D, _noop, (), "WINDOW", "POST_PIXEL")
    assert lifecycle.active_counts()["draw_handlers"] == 1
    lifecycle.remove_all()
    assert lifecycle.active_counts()["draw_handlers"] == 0


def test_remove_all_clears_msgbus_subscriptions():
    lifecycle = load_extension().blender.lifecycle
    calls = []
    lifecycle.subscribe_rna((bpy.types.Object, "location"), lambda: calls.append(1))
    lifecycle.remove_all()
    bpy.msgbus.publish_rna(key=(bpy.types.Object, "location"))
    # Notifications are delivered on the next event-loop pass; in background mode
    # none is delivered either way, so the registry state is the check here.
    assert lifecycle.active_counts()["msgbus_owners"] == 0


def test_remove_takes_away_only_the_given_hooks():
    lifecycle = load_extension().blender.lifecycle

    def keep(*_args):
        return None

    def tick():
        return 1.0

    kept = lifecycle.add_app_handler("load_post", keep)
    removed = [
        lifecycle.add_app_handler("load_post", _noop),
        lifecycle.add_timer(tick, first_interval=10.0),
        lifecycle.add_draw_handler(bpy.types.SpaceView3D, _noop, (), "WINDOW", "POST_PIXEL"),
        lifecycle.subscribe_rna((bpy.types.Object, "location"), _noop),
    ]
    lifecycle.remove(*removed)
    assert _noop not in bpy.app.handlers.load_post
    assert keep in bpy.app.handlers.load_post
    assert not bpy.app.timers.is_registered(tick)
    assert lifecycle.active_counts() == {"app_handlers": 1, "timers": 0, "draw_handlers": 0, "msgbus_owners": 0}
    lifecycle.remove(kept)
    assert keep not in bpy.app.handlers.load_post


def test_remove_all_is_safe_to_call_twice():
    lifecycle = load_extension().blender.lifecycle
    lifecycle.add_app_handler("load_post", _noop)
    lifecycle.remove_all()
    lifecycle.remove_all()
    assert _noop not in bpy.app.handlers.load_post
