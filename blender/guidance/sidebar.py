# SPDX-License-Identifier: GPL-3.0-or-later
"""Lesson panel in the 3D Viewport sidebar (N-panel)."""
import bpy


class BLENDERSAGE_PT_lesson(bpy.types.Panel):
    bl_label = "Lesson"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "BlenderSage"

    def draw(self, context):
        self.layout.label(text="No lesson loaded")


classes = (BLENDERSAGE_PT_lesson,)
register, unregister = bpy.utils.register_classes_factory(classes)
