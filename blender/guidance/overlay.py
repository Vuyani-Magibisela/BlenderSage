# SPDX-License-Identifier: GPL-3.0-or-later
"""Viewport and editor drawing for the running lesson. Draw code only draws.

- draw_card: instruction card in the 3D Viewport (POST_PIXEL), clear of the
  toolbar when region overlap is on, scaled by the UI scale.
- draw_target: world-space box around the resolved target (POST_VIEW);
  amber boxes around candidates when the target is ambiguous.
- draw_editor_outline: outline of the editor the step points to.
Status is always spelled out in text ("Done", "To do"), not only by colour.
"""
import blf
import bpy
import gpu
from gpu_extras.batch import batch_for_shader
from mathutils import Vector

ACCENT = (1.0, 0.62, 0.15, 1.0)
DONE = (0.35, 0.85, 0.45, 1.0)
CANDIDATE = (1.0, 0.8, 0.2, 0.9)
CARD_BG = (0.07, 0.07, 0.09, 0.88)
TEXT = (0.95, 0.95, 0.95, 1.0)
MUTED = (0.75, 0.76, 0.8, 1.0)
FONT = 0
BOX_EDGES = ((0, 1), (1, 2), (2, 3), (3, 0), (4, 5), (5, 6), (6, 7), (7, 4), (0, 4), (1, 5), (2, 6), (3, 7))


def _runtime():
    from . import runtime  # runtime imports this module; import lazily to avoid a cycle
    return runtime


def _scale():
    return bpy.context.preferences.system.ui_scale


def _wrap(text, size, width):
    blf.size(FONT, size)
    lines, line = [], ""
    for word in text.split():
        trial = f"{line} {word}".strip()
        if line and blf.dimensions(FONT, trial)[0] > width:
            lines.append(line)
            line = word
        else:
            line = trial
    if line:
        lines.append(line)
    return lines


def _rect(shader, x, y, w, h, color):
    batch = batch_for_shader(shader, "TRIS", {"pos": [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]},
                             indices=[(0, 1, 2), (0, 2, 3)])
    shader.uniform_float("color", color)
    batch.draw(shader)


def _outline(x, y, w, h, color, width):
    shader = gpu.shader.from_builtin("POLYLINE_UNIFORM_COLOR")
    region = bpy.context.region
    shader.uniform_float("viewportSize", (region.width, region.height))
    shader.uniform_float("lineWidth", width)
    shader.uniform_float("color", color)
    pts = [(x, y), (x + w, y), (x + w, y + h), (x, y + h), (x, y)]
    batch_for_shader(shader, "LINE_STRIP", {"pos": pts}).draw(shader)


def _card_lines(session, evaluation, collapsed, s, width):
    """Return [(text, size, color)] for the card."""
    big, small = 15 * s, 12 * s
    if session.finished:
        done = len(session.completed)
        return [("Lesson finished", big, TEXT),
                (f"{done} of {len(session.lesson.steps)} steps completed. Stop the lesson in the sidebar.", small, MUTED)]
    step = session.current
    lines = [(f"Step {session.index + 1} of {len(session.lesson.steps)}: {step.title}", big, TEXT)]
    if collapsed:
        return lines
    for text in _wrap(step.instruction, small, width):
        lines.append((text, small, TEXT))
    if step.ui_hint:
        for text in _wrap(f"Where: {step.ui_hint.path}", small, width):
            lines.append((text, small, ACCENT))
    if evaluation is not None:
        for result in evaluation.results:
            prefix, color = ("Done", DONE) if result.passed else ("To do", MUTED)
            for text in _wrap(f"{prefix}: {result.message}", small, width):
                lines.append((text, small, color))
    if step.manual_confirm:
        lines.append(("When finished, click Confirm in the sidebar.", small, MUTED))
    elif step.id in session.completed:
        lines.append(("Step complete. Click Next in the sidebar.", small, DONE))
    return lines


def draw_card():
    runtime = _runtime()
    session = runtime.active_session()
    if session is None:
        return
    s = _scale()
    region, area = bpy.context.region, bpy.context.area
    margin, pad, gap = 12 * s, 10 * s, 6 * s
    left = margin
    if bpy.context.preferences.system.use_region_overlap:
        tools = next((r for r in area.regions if r.type == "TOOLS"), None)
        if tools is not None and tools.width > 1:
            left += tools.width
    width = min(440 * s, region.width - left - 2 * margin)
    if width < 120 * s:
        return  # viewport too narrow for a readable card
    lines = _card_lines(session, runtime.last_evaluation(), runtime.card_collapsed(), s, width - 2 * pad)
    height = 2 * pad + sum(size for _, size, _ in lines) + gap * (len(lines) - 1)
    bottom = margin
    complete = not session.finished and session.current.id in session.completed

    gpu.state.blend_set("ALPHA")
    shader = gpu.shader.from_builtin("UNIFORM_COLOR")
    _rect(shader, left, bottom, width, height, CARD_BG)
    _outline(left, bottom, width, height, DONE if complete else ACCENT, 2 * s)
    y = bottom + height - pad
    for text, size, color in lines:
        y -= size
        blf.size(FONT, size)
        blf.color(FONT, *color)
        blf.position(FONT, left + pad, y + size * 0.2, 0)
        blf.draw(FONT, text)
        y -= gap
    gpu.state.blend_set("NONE")


def _box(ob, color, width):
    corners = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
    pts = [corners[i] for edge in BOX_EDGES for i in edge]
    shader = gpu.shader.from_builtin("POLYLINE_UNIFORM_COLOR")
    region = bpy.context.region
    shader.uniform_float("viewportSize", (region.width, region.height))
    shader.uniform_float("lineWidth", width)
    shader.uniform_float("color", color)
    batch_for_shader(shader, "LINES", {"pos": pts}).draw(shader)


def draw_target():
    runtime = _runtime()
    session, evaluation = runtime.active_session(), runtime.last_evaluation()
    if session is None or session.finished or evaluation is None or not session.current.target:
        return
    resolution = evaluation.resolutions.get(session.current.target)
    if resolution is None:
        return
    s = _scale()
    gpu.state.blend_set("ALPHA")
    if resolution.status == "found":
        ob = bpy.data.objects.get(resolution.name)
        if ob is not None:
            _box(ob, ACCENT, 3 * s)
    elif resolution.status == "ambiguous":
        for name in resolution.candidates:
            ob = bpy.data.objects.get(name)
            if ob is not None:
                _box(ob, CANDIDATE, 2 * s)
    gpu.state.blend_set("NONE")


def draw_editor_outline(editor):
    session = _runtime().active_session()
    if session is None or session.finished:
        return
    hint = session.current.ui_hint
    if hint is None or hint.editor != editor:
        return
    region = bpy.context.region
    s = _scale()
    gpu.state.blend_set("ALPHA")
    _outline(2 * s, 2 * s, region.width - 4 * s, region.height - 4 * s, ACCENT, 3 * s)
    gpu.state.blend_set("NONE")
