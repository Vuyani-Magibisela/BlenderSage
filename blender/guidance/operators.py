# SPDX-License-Identifier: GPL-3.0-or-later
"""Sidebar buttons for running a lesson.

Navigation operators have no UNDO flag: they push no undo step, so Ctrl+Z after
pressing Next still undoes the learner's modelling, never the navigation.
"""
import bpy
from bpy_extras.io_utils import ImportHelper

from ...core.tutorial_schema import SchemaError
from . import runtime


def _session():
    return runtime.active_session()


class BLENDERSAGE_OT_start_example(bpy.types.Operator):
    bl_idname = "blendersage.start_example"
    bl_label = "Start Example Lesson"
    bl_description = "Start the bundled desk organiser lesson"

    def execute(self, context):
        runtime.start_lesson(runtime.load_example_lesson())
        return {"FINISHED"}


class BLENDERSAGE_OT_open_lesson(bpy.types.Operator, ImportHelper):
    bl_idname = "blendersage.open_lesson"
    bl_label = "Open Lesson"
    bl_description = "Start a lesson from a lesson JSON file"
    filename_ext = ".json"
    filter_glob: bpy.props.StringProperty(default="*.json", options={"HIDDEN"})

    def execute(self, context):
        try:
            lesson = runtime.load_lesson(self.filepath)
        except (OSError, SchemaError) as exc:
            self.report({"ERROR"}, f"Could not open lesson: {exc}")
            return {"CANCELLED"}
        runtime.start_lesson(lesson)
        return {"FINISHED"}


class BLENDERSAGE_OT_next_step(bpy.types.Operator):
    bl_idname = "blendersage.next_step"
    bl_label = "Next"
    bl_description = "Go to the next step (available when this step is complete)"

    @classmethod
    def poll(cls, context):
        s = _session()
        return s is not None and s.can_go_next

    def execute(self, context):
        runtime.go_next()
        return {"FINISHED"}


class BLENDERSAGE_OT_back_step(bpy.types.Operator):
    bl_idname = "blendersage.back_step"
    bl_label = "Back"
    bl_description = "Show the previous step. Your model is not changed"

    @classmethod
    def poll(cls, context):
        s = _session()
        return s is not None and s.can_go_back

    def execute(self, context):
        runtime.go_back()
        return {"FINISHED"}


class BLENDERSAGE_OT_skip_step(bpy.types.Operator):
    bl_idname = "blendersage.skip_step"
    bl_label = "Skip"
    bl_description = "Move on and leave this step incomplete"

    @classmethod
    def poll(cls, context):
        s = _session()
        return s is not None and not s.finished

    def execute(self, context):
        runtime.skip()
        return {"FINISHED"}


class BLENDERSAGE_OT_confirm_step(bpy.types.Operator):
    bl_idname = "blendersage.confirm_step"
    bl_label = "Confirm"
    bl_description = "Mark this step as done (only where the teacher allows it)"

    @classmethod
    def poll(cls, context):
        s = _session()
        return s is not None and not s.finished and s.current.manual_confirm

    def execute(self, context):
        runtime.confirm()
        return {"FINISHED"}


class BLENDERSAGE_OT_toggle_card(bpy.types.Operator):
    bl_idname = "blendersage.toggle_card"
    bl_label = "Toggle Instruction Card"
    bl_description = "Collapse or expand the instruction card in the 3D Viewport"

    def execute(self, context):
        runtime.toggle_card()
        return {"FINISHED"}


class BLENDERSAGE_OT_use_selected(bpy.types.Operator):
    bl_idname = "blendersage.use_selected"
    bl_label = "Use Selected"
    bl_description = "Use the active object as this step's target"
    bl_options = {"REGISTER", "UNDO"}  # writes a custom property to the object

    @classmethod
    def poll(cls, context):
        s = _session()
        return (s is not None and not s.finished and bool(s.current.target)
                and context.view_layer.objects.active is not None)

    def execute(self, context):
        runtime.use_selected(_session().current.target)
        return {"FINISHED"}


class BLENDERSAGE_OT_stop_lesson(bpy.types.Operator):
    bl_idname = "blendersage.stop_lesson"
    bl_label = "Stop Lesson"
    bl_description = "Stop the lesson. Your model is not changed"

    @classmethod
    def poll(cls, context):
        return _session() is not None

    def execute(self, context):
        runtime.stop_lesson()
        return {"FINISHED"}


classes = (
    BLENDERSAGE_OT_start_example,
    BLENDERSAGE_OT_open_lesson,
    BLENDERSAGE_OT_next_step,
    BLENDERSAGE_OT_back_step,
    BLENDERSAGE_OT_skip_step,
    BLENDERSAGE_OT_confirm_step,
    BLENDERSAGE_OT_toggle_card,
    BLENDERSAGE_OT_use_selected,
    BLENDERSAGE_OT_stop_lesson,
)
register, unregister = bpy.utils.register_classes_factory(classes)
