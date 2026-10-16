# SPDX-License-Identifier: GPL-3.0-or-later
from core.targets import resolve
from core.tutorial_schema import parse_lesson
from lesson_fixtures import lesson_data, obj, state

BOX = parse_lesson(lesson_data()).targets["box"]


def test_single_match_by_type_and_prefix():
    r = resolve("box", BOX, state(obj("Cube"), obj("Camera", "CAMERA")))
    assert (r.status, r.name) == ("found", "Cube")


def test_missing_when_nothing_matches():
    r = resolve("box", BOX, state(obj("Camera", "CAMERA")))
    assert r.status == "missing" and r.name is None


def test_ambiguous_when_several_match():
    r = resolve("box", BOX, state(obj("Cube"), obj("Cube.001")))
    assert r.status == "ambiguous"
    assert r.candidates == ["Cube", "Cube.001"]


def test_wrong_type_does_not_match():
    r = resolve("box", BOX, state(obj("Cube", "CURVE")))
    assert r.status == "missing"


def test_tag_wins_over_name_rule():
    r = resolve("box", BOX, state(obj("Cube"), obj("Organiser", tag="box")))
    assert (r.status, r.name) == ("found", "Organiser")


def test_tag_resolves_ambiguity():
    r = resolve("box", BOX, state(obj("Cube"), obj("Cube.001", tag="box")))
    assert (r.status, r.name) == ("found", "Cube.001")


def test_two_tagged_objects_are_ambiguous():
    r = resolve("box", BOX, state(obj("A", tag="box"), obj("B", tag="box")))
    assert r.status == "ambiguous"
