# SPDX-License-Identifier: GPL-3.0-or-later
"""The running lesson: one active session, evaluated on a timer.

The timer only reads scene state and evaluates checks; it never calls bpy.ops
(CLAUDE.md rule 3). Navigation never changes the scene. The timer is persistent,
so the lesson keeps running when another file is loaded.
"""
from pathlib import Path

import bpy

from ...core.checks import evaluate_step
from ...core.session import LessonSession
from ...core.tutorial_schema import parse_lesson
from .. import lifecycle, state
from . import overlay

REFRESH_SECONDS = 0.5
EXAMPLE_LESSON = Path(__file__).resolve().parents[2] / "lessons" / "desk_organiser.json"

_state = {"session": None, "evaluation": None, "tokens": [], "card_collapsed": False}


def load_lesson(path):
    return parse_lesson(Path(path).read_text(encoding="utf-8"))


def load_example_lesson():
    return load_lesson(EXAMPLE_LESSON)


def active_session():
    return _state["session"]


def last_evaluation():
    return _state["evaluation"]


def card_collapsed():
    return _state["card_collapsed"]


def toggle_card():
    _state["card_collapsed"] = not _state["card_collapsed"]
    _redraw()


def start_lesson(lesson):
    stop_lesson()
    _state["session"] = LessonSession(lesson)
    _state["evaluation"] = None
    _state["tokens"] = [
        lifecycle.add_timer(refresh, first_interval=0.0, persistent=True),
        lifecycle.add_draw_handler(bpy.types.SpaceView3D, overlay.draw_card, (), "WINDOW", "POST_PIXEL"),
        lifecycle.add_draw_handler(bpy.types.SpaceView3D, overlay.draw_target, (), "WINDOW", "POST_VIEW"),
        lifecycle.add_draw_handler(bpy.types.SpaceProperties, overlay.draw_editor_outline, ("PROPERTIES",),
                                   "WINDOW", "POST_PIXEL"),
        lifecycle.add_draw_handler(bpy.types.SpaceOutliner, overlay.draw_editor_outline, ("OUTLINER",),
                                   "WINDOW", "POST_PIXEL"),
    ]
    _redraw()


def stop_lesson():
    lifecycle.remove(*_state["tokens"])
    _state.update(session=None, evaluation=None, tokens=[])
    _redraw()


def refresh():
    """Timer callback: evaluate the current step. Returns the next interval."""
    session = _state["session"]
    if session is None:
        return None
    if session.finished:
        _state["evaluation"] = None
    else:
        evaluation = evaluate_step(session.lesson, session.current, state.snapshot())
        _state["evaluation"] = evaluation
        if evaluation.complete:
            session.mark_complete(session.current.id)
    _redraw()
    return REFRESH_SECONDS


def _after_navigation():
    _state["evaluation"] = None
    refresh()


def go_next():
    _state["session"].next()
    _after_navigation()


def go_back():
    _state["session"].back()
    _after_navigation()


def skip():
    _state["session"].skip()
    _after_navigation()


def confirm():
    _state["session"].confirm()
    _after_navigation()


def use_selected(target_id):
    """Tag the active object as the lesson's target (semantic, survives renames)."""
    ob = bpy.context.view_layer.objects.active
    if ob is None:
        raise ValueError("no active object")
    for other in bpy.data.objects:
        if other is not ob and other.get(state.TAG_PROPERTY) == target_id:
            del other[state.TAG_PROPERTY]
    ob[state.TAG_PROPERTY] = target_id
    refresh()


def _redraw():
    wm = getattr(bpy.context, "window_manager", None)
    if wm is None:
        return
    for window in wm.windows:
        for area in window.screen.areas:
            if area.type in {"VIEW_3D", "PROPERTIES", "OUTLINER"}:
                area.tag_redraw()
