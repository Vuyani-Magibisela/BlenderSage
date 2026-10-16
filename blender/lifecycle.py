# SPDX-License-Identifier: GPL-3.0-or-later
"""Single registry for everything the extension hooks into Blender.

Add app handlers, timers, draw handlers and msgbus subscriptions only through
these functions. Each returns a token; remove(*tokens) takes away those hooks
(e.g. when a lesson stops), and unregister() calls remove_all(), so disabling
the extension leaves Blender exactly as it was (CLAUDE.md rule 2).
"""
import bpy

_KINDS = ("app_handlers", "timers", "draw_handlers", "msgbus_owners")
_entries = []  # tokens in the order they were added


class _Token:
    __slots__ = ("kind", "data")

    def __init__(self, kind, data):
        self.kind = kind
        self.data = data


def _add(kind, data):
    token = _Token(kind, data)
    _entries.append(token)
    return token


def add_app_handler(name, function):
    """Append `function` to bpy.app.handlers.<name>, e.g. "load_post"."""
    getattr(bpy.app.handlers, name).append(function)
    return _add("app_handlers", (name, function))


def add_timer(function, first_interval=0.0, persistent=False):
    bpy.app.timers.register(function, first_interval=first_interval, persistent=persistent)
    return _add("timers", function)


def add_draw_handler(space_type, function, args, region_type, draw_type):
    handle = space_type.draw_handler_add(function, args, region_type, draw_type)
    return _add("draw_handlers", (space_type, handle, region_type))


def subscribe_rna(key, notify, options=frozenset()):
    owner = object()
    bpy.msgbus.subscribe_rna(key=key, owner=owner, args=(), notify=notify, options=set(options))
    return _add("msgbus_owners", owner)


def _undo(token):
    if token.kind == "app_handlers":
        name, function = token.data
        handlers = getattr(bpy.app.handlers, name)
        if function in handlers:
            handlers.remove(function)
    elif token.kind == "timers":
        if bpy.app.timers.is_registered(token.data):
            bpy.app.timers.unregister(token.data)
    elif token.kind == "draw_handlers":
        space_type, handle, region_type = token.data
        space_type.draw_handler_remove(handle, region_type)
    elif token.kind == "msgbus_owners":
        bpy.msgbus.clear_by_owner(token.data)


def remove(*tokens):
    """Remove the given hooks. Tokens already removed are ignored."""
    for token in tokens:
        if token in _entries:
            _entries.remove(token)
            _undo(token)


def remove_all():
    """Remove everything added through this module. Safe to call more than once."""
    while _entries:
        _undo(_entries.pop())


def active_counts():
    counts = dict.fromkeys(_KINDS, 0)
    for token in _entries:
        counts[token.kind] += 1
    return counts
