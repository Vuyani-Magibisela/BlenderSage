# SPDX-License-Identifier: GPL-3.0-or-later
from core.checks import evaluate_step
from core.tutorial_schema import parse_lesson
from lesson_fixtures import lesson_data, obj, state


def lesson_with(checks, targets=None):
    data = lesson_data()
    if targets:
        data["targets"].update(targets)
    data["steps"] = [{"id": "s", "title": "S", "instruction": "Do it.", "checks": checks}]
    return parse_lesson(data)


def run(checks, scene, targets=None):
    lesson = lesson_with(checks, targets)
    return evaluate_step(lesson, lesson.steps[0], scene)


def test_object_exists_passes_and_fails():
    check = [{"type": "object_exists", "target": "box"}]
    assert run(check, state(obj("Cube"))).complete
    result = run(check, state())
    assert not result.complete
    assert "box" in result.results[0].message


def test_mode_check():
    check = [{"type": "mode", "mode": "EDIT_MESH"}]
    assert run(check, state(mode="EDIT_MESH")).complete
    assert not run(check, state(mode="OBJECT")).complete


def test_dimensions_within_tolerance():
    check = [{"type": "dimensions", "target": "box", "value": [0.3, 0.2, 0.1], "tolerance": 0.005}]
    assert run(check, state(obj("Cube", dimensions=(0.302, 0.199, 0.1)))).complete
    result = run(check, state(obj("Cube", dimensions=(0.3, 0.2, 0.2))))
    assert not result.complete
    assert "0.300 × 0.200 × 0.200" in result.results[0].message


def test_scale_check_for_applied_scale():
    check = [{"type": "scale", "target": "box", "value": [1, 1, 1], "tolerance": 0.0001}]
    assert run(check, state(obj("Cube", scale=(1, 1, 1)))).complete
    result = run(check, state(obj("Cube", scale=(0.15, 0.1, 0.05))))
    assert not result.complete
    assert "0.150 × 0.100 × 0.050" in result.results[0].message


def test_modifier_present_with_settings():
    check = [{"type": "modifier", "target": "box", "modifier": "BEVEL",
              "settings": {"width": 0.005, "segments": 3}, "tolerance": 0.0005}]
    good = obj("Cube", modifiers=[{"type": "BEVEL", "name": "Bevel", "settings": {"width": 0.0052, "segments": 3}}])
    assert run(check, state(good)).complete
    wrong = obj("Cube", modifiers=[{"type": "BEVEL", "name": "Bevel", "settings": {"width": 0.1, "segments": 3}}])
    result = run(check, state(wrong))
    assert not result.complete
    assert "width" in result.results[0].message
    assert not run(check, state(obj("Cube"))).complete


def test_modifier_present_without_settings():
    check = [{"type": "modifier", "target": "box", "modifier": "SOLIDIFY"}]
    solid = obj("Cube", modifiers=[{"type": "SOLIDIFY", "name": "Solidify", "settings": {}}])
    assert run(check, state(solid)).complete


def test_material_assigned():
    check = [{"type": "material_assigned", "target": "box"}]
    assert run(check, state(obj("Cube", materials=["Wood"]))).complete
    assert not run(check, state(obj("Cube", materials=[None]))).complete
    assert not run(check, state(obj("Cube"))).complete


def test_material_assigned_with_name_prefix():
    check = [{"type": "material_assigned", "target": "box", "name": "Wood"}]
    assert run(check, state(obj("Cube", materials=["Wood.001"]))).complete
    result = run(check, state(obj("Cube", materials=["Material"])))
    assert not result.complete
    assert "Wood" in result.results[0].message


def test_ambiguous_target_fails_with_selection_prompt():
    check = [{"type": "object_exists", "target": "box"}]
    result = run(check, state(obj("Cube"), obj("Cube.001")))
    assert not result.complete
    assert result.resolutions["box"].status == "ambiguous"


def test_step_without_checks_is_never_auto_complete():
    lesson = parse_lesson(lesson_data())
    manual = lesson.steps[2]
    assert not evaluate_step(lesson, manual, state(obj("Cube"))).complete
