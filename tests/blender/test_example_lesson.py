# SPDX-License-Identifier: GPL-3.0-or-later
"""Walk the bundled desk-organiser lesson on a real scene.

Each scene change is made through the data API (as a stand-in for the learner)
and the step's checks are evaluated against a real snapshot.
"""
import bpy
from mathutils import Matrix

from extension_loader import load_extension


def _evaluate(ext, lesson, step_id):
    step = next(s for s in lesson.steps if s.id == step_id)
    return ext.core.checks.evaluate_step(lesson, step, ext.blender.state.snapshot())


def test_desk_organiser_walkthrough():
    ext = load_extension()
    lesson = ext.blender.guidance.runtime.load_example_lesson()
    assert len(lesson.steps) == 8
    cube = bpy.data.objects["Cube"]

    assert _evaluate(ext, lesson, "find-cube").complete

    assert not _evaluate(ext, lesson, "size").complete
    cube.dimensions = (0.3, 0.2, 0.1)
    bpy.context.view_layer.update()
    assert _evaluate(ext, lesson, "size").complete

    assert not _evaluate(ext, lesson, "apply-scale").complete
    cube.data.transform(Matrix.Diagonal(cube.scale.to_4d()))  # what Apply > Scale does
    cube.scale = (1, 1, 1)
    bpy.context.view_layer.update()
    assert _evaluate(ext, lesson, "apply-scale").complete
    assert _evaluate(ext, lesson, "size").complete  # dimensions unchanged by applying

    assert not _evaluate(ext, lesson, "add-bevel").complete
    bevel = cube.modifiers.new("Bevel", "BEVEL")
    assert _evaluate(ext, lesson, "add-bevel").complete

    assert not _evaluate(ext, lesson, "bevel-settings").complete
    bevel.width = 0.005
    bevel.segments = 3
    assert _evaluate(ext, lesson, "bevel-settings").complete

    bpy.ops.object.mode_set(mode="EDIT")
    assert not _evaluate(ext, lesson, "open-top").complete  # manual confirmation only

    solidify_eval = _evaluate(ext, lesson, "solidify")
    assert not solidify_eval.complete
    bpy.ops.object.mode_set(mode="OBJECT")
    solid = cube.modifiers.new("Solidify", "SOLIDIFY")
    solid.thickness = 0.005
    assert _evaluate(ext, lesson, "solidify").complete

    assert not _evaluate(ext, lesson, "material").complete  # factory cube has "Material"
    cube.data.materials[0] = bpy.data.materials.new("Wood")
    assert _evaluate(ext, lesson, "material").complete
