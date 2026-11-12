# SPDX-License-Identifier: GPL-3.0-or-later
import copy

from core.state_diff import apply_diff, diff_states
from lesson_fixtures import obj, state


def test_no_change_gives_empty_diff():
    s = state(obj("Cube"))
    assert diff_states(s, copy.deepcopy(s)) == {}


def test_changed_object_field():
    before = state(obj("Cube"))
    after = state(obj("Cube", dimensions=(0.3, 0.2, 0.1)))
    assert diff_states(before, after) == {"objects": {"changed": {"Cube": {"dimensions": [0.3, 0.2, 0.1]}}}}


def test_added_and_removed_objects():
    before = state(obj("Cube"), obj("Light", "LIGHT"))
    after = state(obj("Cube"), obj("Sphere"))
    d = diff_states(before, after)
    assert d["objects"]["added"] == [obj("Sphere")]
    assert d["objects"]["removed"] == ["Light"]


def test_top_level_fields():
    d = diff_states(state(obj("Cube"), mode="OBJECT", active="Cube"),
                    state(obj("Cube"), mode="EDIT_MESH", active="Cube"))
    assert d == {"mode": "EDIT_MESH"}


def test_apply_rebuilds_the_later_state():
    before = state(obj("Cube"), obj("Light", "LIGHT"), active="Cube", selected=["Cube"])
    after = state(
        obj("Cube", dimensions=(0.3, 0.2, 0.1),
            modifiers=[{"type": "BEVEL", "name": "Bevel", "settings": {"width": 0.005}}]),
        obj("Sphere"), mode="EDIT_MESH", active="Sphere", selected=["Sphere"],
    )
    rebuilt = apply_diff(before, diff_states(before, after))
    assert rebuilt == after
    assert before["mode"] == "OBJECT"  # input not modified
