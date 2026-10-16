# SPDX-License-Identifier: GPL-3.0-or-later
"""Single registry for everything the extension hooks into Blender.

Add app handlers, timers, draw handlers and msgbus subscriptions only through
these functions. unregister() calls remove_all(), so disabling the extension
leaves Blender exactly as it was (CLAUDE.md rule 2).
"""
import bpy

_app_handlers = []   # (handler list name, function)
_timers = []         # functions registered with bpy.app.timers
_draw_handlers = []  # (space type, handle, region type)
_msgbus_owners = []  # owner objects passed to bpy.msgbus.subscribe_rna


def add_app_handler(name, function):
    """Append `function` to bpy.app.handlers.<name>, e.g. "load_post"."""
    getattr(bpy.app.handlers, name).append(function)
    _app_handlers.append((name, function))


def add_timer(function, first_interval=0.0, persistent=False):
    bpy.app.timers.register(function, first_interval=first_interval, persistent=persistent)
    _timers.append(function)


def add_draw_handler(space_type, function, args, region_type, draw_type):
    handle = space_type.draw_handler_add(function, args, region_type, draw_type)
    _draw_handlers.append((space_type, handle, region_type))
    return handle


def subscribe_rna(key, notify, options=frozenset()):
    owner = object()
    bpy.msgbus.subscribe_rna(key=key, owner=owner, args=(), notify=notify, options=set(options))
    _msgbus_owners.append(owner)
    return owner


def remove_all():
    """Remove everything added through this module. Safe to call more than once."""
    while _app_handlers:
        name, function = _app_handlers.pop()
        handlers = getattr(bpy.app.handlers, name)
        if function in handlers:
            handlers.remove(function)
    while _timers:
        function = _timers.pop()
        if bpy.app.timers.is_registered(function):
            bpy.app.timers.unregister(function)
    while _draw_handlers:
        space_type, handle, region_type = _draw_handlers.pop()
        space_type.draw_handler_remove(handle, region_type)
    while _msgbus_owners:
        bpy.msgbus.clear_by_owner(_msgbus_owners.pop())


def active_counts():
    return {
        "app_handlers": len(_app_handlers),
        "timers": len(_timers),
        "draw_handlers": len(_draw_handlers),
        "msgbus_owners": len(_msgbus_owners),
    }
