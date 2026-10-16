# SPDX-License-Identifier: GPL-3.0-or-later
"""Lesson panel in the 3D Viewport sidebar (N-panel)."""
import textwrap

import bpy

from . import runtime


def _paragraph(layout, text, width=38):
    col = layout.column(align=True)
    for line in textwrap.wrap(text, width) or [""]:
        col.label(text=line)


class BLENDERSAGE_PT_lesson(bpy.types.Panel):
    bl_label = "Lesson"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "BlenderSage"

    def draw(self, context):
        layout = self.layout
        session = runtime.active_session()
        if session is None:
            layout.label(text="No lesson loaded")
            layout.operator("blendersage.start_example", icon="PLAY")
            layout.operator("blendersage.open_lesson", icon="FILE_FOLDER")
            return

        layout.label(text=session.lesson.title, icon="BOOKMARKS")
        if session.finished:
            layout.label(text=f"Finished: {len(session.completed)} of "
                              f"{len(session.lesson.steps)} steps completed")
            if session.skipped:
                layout.label(text=f"Skipped: {len(session.skipped)}")
            row = layout.row(align=True)
            row.operator("blendersage.back_step", icon="BACK")
            layout.operator("blendersage.stop_lesson", icon="CANCEL")
            return

        step = session.current
        status = "Done" if step.id in session.completed else (
            "Skipped earlier" if step.id in session.skipped else "In progress")
        box = layout.box()
        box.label(text=f"Step {session.index + 1} of {len(session.lesson.steps)} · {status}")
        box.label(text=step.title)
        _paragraph(box, step.instruction)
        if step.why:
            _paragraph(box.column(), "Why: " + step.why)
        if step.ui_hint:
            _paragraph(box, "Where: " + step.ui_hint.path)

        evaluation = runtime.last_evaluation()
        if evaluation is not None and evaluation.results:
            col = layout.column(align=True)
            for result in evaluation.results:
                text = ("Done: " if result.passed else "To do: ") + result.message
                lines = textwrap.wrap(text, 36) or [""]
                col.label(text=lines[0], icon="CHECKMARK" if result.passed else "DOT")
                for line in lines[1:]:
                    col.label(text=line, icon="BLANK1")
            resolution = evaluation.resolutions.get(step.target) if step.target else None
            if resolution is not None and resolution.status != "found":
                layout.operator("blendersage.use_selected", icon="RESTRICT_SELECT_OFF")

        if step.hints:
            hints = layout.column(align=True)
            hints.label(text="Hints:", icon="INFO")
            for hint in step.hints:
                _paragraph(hints, hint)

        row = layout.row(align=True)
        row.operator("blendersage.back_step", icon="BACK")
        if step.manual_confirm:
            row.operator("blendersage.confirm_step", icon="CHECKMARK")
        row.operator("blendersage.next_step", icon="FORWARD")
        row.operator("blendersage.skip_step")
        layout.operator("blendersage.toggle_card",
                        text="Show Card" if runtime.card_collapsed() else "Collapse Card",
                        icon="HIDE_ON" if runtime.card_collapsed() else "HIDE_OFF")
        layout.operator("blendersage.stop_lesson", icon="CANCEL")


classes = (BLENDERSAGE_PT_lesson,)
register, unregister = bpy.utils.register_classes_factory(classes)
