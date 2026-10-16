# SPDX-License-Identifier: GPL-3.0-or-later
import json

import pytest

from core.tutorial_schema import SchemaError, parse_lesson
from lesson_fixtures import lesson_data


def test_parses_valid_lesson():
    lesson = parse_lesson(lesson_data())
    assert lesson.id == "test-lesson"
    assert [s.id for s in lesson.steps] == ["exists", "size", "edit"]
    assert lesson.targets["box"].name_prefix == "Cube"
    assert lesson.steps[1].ui_hint.editor == "VIEW_3D"
    assert lesson.steps[2].manual_confirm is True


def test_parses_json_text():
    lesson = parse_lesson(json.dumps(lesson_data()))
    assert lesson.title == "Test lesson"


def test_rejects_unknown_schema_version():
    with pytest.raises(SchemaError, match="schema_version"):
        parse_lesson(lesson_data(schema_version=99))


def test_rejects_unknown_check_type_with_path():
    data = lesson_data()
    data["steps"][0]["checks"][0]["type"] = "run_python"
    with pytest.raises(SchemaError, match=r"steps\[0\]\.checks\[0\]\.type"):
        parse_lesson(data)


def test_rejects_reference_to_undefined_target():
    data = lesson_data()
    data["steps"][1]["checks"][0]["target"] = "lid"
    with pytest.raises(SchemaError, match="unknown target 'lid'"):
        parse_lesson(data)


def test_rejects_duplicate_step_ids():
    data = lesson_data()
    data["steps"][1]["id"] = "exists"
    with pytest.raises(SchemaError, match="duplicate step id"):
        parse_lesson(data)


def test_rejects_unknown_editor():
    data = lesson_data()
    data["steps"][1]["ui_hint"]["editor"] = "SEQUENCE_EDITOR"
    with pytest.raises(SchemaError, match="editor"):
        parse_lesson(data)


def test_rejects_non_finite_numbers():
    data = lesson_data()
    data["steps"][1]["checks"][0]["value"] = [0.3, float("nan"), 0.1]
    with pytest.raises(SchemaError, match="value"):
        parse_lesson(data)


def test_rejects_unexpected_keys():
    data = lesson_data()
    data["steps"][0]["script"] = "import os"
    with pytest.raises(SchemaError, match="unexpected key 'script'"):
        parse_lesson(data)


def test_step_without_checks_requires_manual_confirm():
    data = lesson_data()
    data["steps"][2]["manual_confirm"] = False
    with pytest.raises(SchemaError, match="no checks"):
        parse_lesson(data)


def test_reports_every_error_at_once():
    data = lesson_data()
    data["steps"][0]["checks"][0]["type"] = "nope"
    data["steps"][1]["ui_hint"]["editor"] = "NOPE"
    with pytest.raises(SchemaError) as info:
        parse_lesson(data)
    assert len(info.value.errors) == 2
