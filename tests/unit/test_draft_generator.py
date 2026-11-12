# SPDX-License-Identifier: GPL-3.0-or-later
import json
import os

import pytest

from core.draft_generator import (DRAFT, REVIEW, ReportParseError, generate, generate_from_folder, parse_report,
                                  render_text, to_json)
from core.state_diff import diff_states
from lesson_fixtures import obj, state

RECORDINGS = os.path.join(os.path.dirname(__file__), "fixtures", "recordings")
MOVE = "bpy.ops.transform.translate(value=(1, 0, 0), orient_type='GLOBAL')"


def cube(location=(0.0, 0.0, 0.0), **kwargs):
    return dict(obj("Cube", **kwargs), location=list(location))


def scene(*objects, **kwargs):
    kwargs.setdefault("active", "Cube")
    kwargs.setdefault("selected", ["Cube"])
    return state(*(objects or (cube(),)), **kwargs)


class Rec:
    """Builds a pair of journals the way the recorder writes them."""

    def __init__(self, start=None):
        self.cur = start or scene()
        self.uid = 0
        self.actions = [{"kind": "start", "t": 0.0, "bs": "s1", "blender": "5.2.2", "file": ""}]
        self.states = [{"kind": "snapshot", "reason": "start", "t": 0.0, "full": self.cur}]

    def report(self, t, message, type_="OPERATOR", bs="s1"):
        self.uid += 1
        self.actions.append({"kind": "report", "t": t, "bs": bs, "uid": self.uid, "type": type_, "message": message})

    def prop(self, t, message):
        self.report(t, message, "PROPERTY")

    def event(self, kind, t, **extra):
        self.actions.append({"kind": kind, "t": t, **extra})

    def diff(self, t, new, *triggers):
        self.states.append({"kind": "diff", "t": t, "triggers": list(triggers or ["depsgraph"]),
                            "changes": diff_states(self.cur, new)})
        self.cur = new

    def snapshot(self, t, reason, full):
        self.states.append({"kind": "snapshot", "reason": reason, "t": t, "full": full})
        self.cur = full

    def run(self):
        return generate(self.actions, self.states)


def titles(result, status=None):
    return [i.title for i in result.items if status is None or i.status == status]


# Parsing ------------------------------------------------------------------------------

def test_parse_operator_report():
    kind, op, args = parse_report("OPERATOR", "bpy.ops.mesh.bevel(offset=0.2, affect='EDGES', snap_elements={'INCREMENT'})")
    assert (kind, op) == ("operator", "mesh.bevel")
    assert args == {"offset": 0.2, "affect": "EDGES", "snap_elements": {"INCREMENT"}}


def test_parse_property_report_and_reference_value():
    assert parse_report("PROPERTY", "bpy.context.object.location[0] = 1.5") == \
        ("property", "bpy.context.object.location[0]", {"value": 1.5})
    _, _, args = parse_report("PROPERTY", 'bpy.context.object.modifiers["Boolean"].object = bpy.data.objects["Sphere"]')
    assert args == {"value": {"ref": "bpy.data.objects['Sphere']"}}


@pytest.mark.parametrize("message", [
    "bpy.ops.mesh.bevel(offset=__import__('os').getcwd())",
    "__import__('os').system('echo hi')",
    "bpy.ops.mesh.bevel(**kw)",
    "bpy.ops.mesh.bevel(",
])
def test_parse_rejects_anything_but_literals(message):
    with pytest.raises(ReportParseError):
        parse_report("OPERATOR", message)


# Rule 1: one report per action; repeated edits collapse ------------------------------

def test_supported_report_becomes_a_draft_with_its_state_change():
    r = Rec()
    r.report(1.0, MOVE)
    r.diff(1.2, scene(cube(location=(1, 0, 0))))
    result = r.run()
    assert titles(result) == ["Move by (1, 0, 0)"]
    item = result.items[0]
    assert item.objects == ["Cube"] and item.changes == {("Cube", "location"): [1, 0, 0]}


def test_repeated_property_edits_collapse_to_the_last_value():
    r = Rec()
    r.prop(1.0, "bpy.context.object.location[0] = 1")
    r.prop(2.0, "bpy.context.object.location[0] = 1.5")
    r.diff(2.1, scene(cube(location=(1.5, 0, 0))))
    result = r.run()
    assert titles(result) == ["Set Location X of Cube to 1.5"]
    assert len(result.items[0].evidence) == 2
    assert [i.reason for i in result.ignored] == ["replaced by a later value"]


def test_property_edits_with_an_action_between_stay_separate():
    r = Rec()
    r.prop(1.0, "bpy.context.object.location[0] = 1")
    r.report(2.0, MOVE)
    r.prop(3.0, "bpy.context.object.location[0] = 1.5")
    assert len(r.run().drafts) == 3


def test_duplicate_reports_are_counted_once():
    r = Rec()
    r.report(1.0, MOVE)
    r.actions.append(dict(r.actions[-1], t=1.1))  # same Blender session and uid
    assert len(r.run().items) == 1


# Rule 2: unexplained state changes ---------------------------------------------------

def test_dimensions_edit_without_report_becomes_a_state_draft():
    r = Rec()
    r.diff(5.0, scene(cube(dimensions=(3, 4, 4), scale=(1.5, 2, 2))))
    result = r.run()
    assert titles(result, DRAFT) == ["Set Cube dimensions to (3, 4, 4)"]
    assert result.items[0].kind == "state"
    assert {"type": "dimensions", "object": "Cube", "value": [3, 4, 4]} in result.items[0].check_hints


def test_diff_slightly_before_its_report_is_explained():
    r = Rec()
    r.diff(4.9, scene(cube(scale=(0.6, 0.6, 0.6), dimensions=(1.2, 1.2, 1.2))))
    r.report(5.0, "bpy.ops.transform.resize(value=(0.6, 0.6, 0.6))")
    result = r.run()
    assert titles(result) == ["Scale by 0.6"]


def test_diffs_during_a_long_interactive_tool_belong_to_its_report():
    r = Rec()
    r.diff(1.0, scene(cube(location=(0.3, 0, 0))))
    r.diff(2.0, scene(cube(location=(0.7, 0, 0))))
    r.report(4.0, MOVE)
    r.diff(4.1, scene(cube(location=(1, 0, 0))))
    result = r.run()
    assert titles(result) == ["Move by (1, 0, 0)"]
    assert result.items[0].changes == {("Cube", "location"): [1, 0, 0]}


def test_change_reverted_without_a_report_is_left_out():
    # e.g. a tool cancelled after the viewport had already updated
    r = Rec()
    r.diff(1.0, scene(cube(dimensions=(3, 2, 2))))
    r.diff(2.0, scene(cube()))
    result = r.run()
    assert result.items == []
    assert [i.reason for i in result.ignored] == ["changed and changed back"]


def test_unreported_selection_change_is_not_a_step():
    r = Rec(scene(cube(), obj("Light", "LIGHT")))
    r.diff(1.0, scene(cube(), obj("Light", "LIGHT"), active="Light", selected=["Light"]))
    assert r.run().items == []


def test_ui_reports_are_ignored_with_a_reason():
    r = Rec()
    r.prop(1.0, "bpy.context.region.active_panel_category = 'Item'")
    r.prop(2.0, 'bpy.context.space_data.params.directory = "C:\\\\Users\\\\teacher\\\\"')
    result = r.run()
    assert result.items == []
    assert [i.reason for i in result.ignored] == ["interface only", "interface only"]


# Rule 3: undo and redo ---------------------------------------------------------------

def test_confirmed_undo_removes_the_step():
    r = Rec()
    r.prop(1.0, "bpy.context.object.location[0] = 1.5")
    r.diff(1.1, scene(cube(location=(1.5, 0, 0))))
    r.event("undo", 3.0)
    r.diff(3.1, scene(cube()), "undo", "depsgraph")
    r.report(5.0, "bpy.ops.object.editmode_toggle()")
    result = r.run()
    assert titles(result) == ["Toggle Edit Mode"]
    assert [i.reason for i in result.ignored] == ["undone"]


def test_undo_then_redo_keeps_the_step():
    r = Rec()
    r.report(1.0, MOVE)
    r.diff(1.1, scene(cube(location=(1, 0, 0))))
    r.event("undo", 2.0)
    r.diff(2.1, scene(cube()), "undo")
    r.event("redo", 3.0)
    r.diff(3.1, scene(cube(location=(1, 0, 0))), "redo")
    result = r.run()
    assert titles(result, DRAFT) == ["Move by (1, 0, 0)"] and result.ignored == []


def test_undo_without_matching_state_change_becomes_review():
    r = Rec()
    r.report(1.0, MOVE)
    r.diff(1.1, scene(cube(location=(1, 0, 0))))
    r.event("undo", 2.0)  # no diff: something untracked was undone, or nothing
    result = r.run()
    assert [i.status for i in result.items] == [REVIEW]
    assert "undone" in result.items[0].reason


def test_undoing_a_selection_click_does_not_remove_the_previous_step():
    r = Rec(scene(cube(), obj("Light", "LIGHT")))
    r.report(1.0, MOVE)
    r.diff(1.1, scene(cube(location=(1, 0, 0)), obj("Light", "LIGHT")))
    r.diff(3.0, scene(cube(location=(1, 0, 0)), obj("Light", "LIGHT"), active="Light", selected=["Light"]))
    r.event("undo", 5.0)
    r.diff(5.1, scene(cube(location=(1, 0, 0)), obj("Light", "LIGHT")), "undo")
    result = r.run()
    assert titles(result, DRAFT) == ["Move by (1, 0, 0)"]


def test_report_after_redo_is_explained_in_the_same_diff():
    r = Rec()
    r.report(1.0, MOVE)
    r.diff(1.1, scene(cube(location=(1, 0, 0))))
    r.event("undo", 2.0)
    r.diff(2.1, scene(cube()), "undo")
    r.event("redo", 3.0)
    r.report(3.5, "bpy.ops.object.modifier_add(type='BEVEL')")
    bevel = {"type": "BEVEL", "name": "Bevel", "settings": {"width": 0.1}}
    r.diff(3.6, scene(cube(location=(1, 0, 0), modifiers=[bevel])), "redo", "depsgraph")
    result = r.run()
    assert titles(result) == ["Move by (1, 0, 0)", "Add Bevel modifier"]
    assert result.items[1].check_hints[-1] == {"type": "modifier", "object": "Cube", "modifier": "BEVEL",
                                               "settings": {"width": 0.1}}


# Rule 4: unsupported and unreadable reports ------------------------------------------

def test_unsupported_and_unreadable_reports_become_review_items():
    r = Rec()
    r.report(1.0, "bpy.ops.someaddon.do_magic(power=3)")
    r.report(2.0, "bpy.ops.mesh.bevel(offset=")
    r.prop(3.0, "bpy.context.scene.tool_settings.use_snap = True")
    result = r.run()
    assert [i.status for i in result.items] == [REVIEW, REVIEW, REVIEW]
    assert all(i.reason for i in result.items)


# Pause, file load and recovery --------------------------------------------------------

def test_changes_while_paused_are_noted_not_drafted():
    r = Rec()
    r.event("pause", 1.0)
    r.event("resume", 5.0)
    r.snapshot(5.0, "resume", scene(cube(location=(2, 0, 0))))
    result = r.run()
    assert result.items == []
    assert [i.reason for i in result.ignored] == ["changed while recording was paused"]


def test_file_load_is_a_review_item_and_its_state_is_not_a_draft():
    r = Rec()
    r.event("file_loaded", 2.0, file="model.blend")
    r.diff(2.2, scene(cube(location=(5, 5, 5))), "load", "depsgraph")
    result = r.run()
    assert titles(result) == ["Opened file model.blend"] and result.items[0].status == REVIEW


def test_recovered_recording_restarts_time_in_a_new_segment():
    r = Rec()
    r.report(5.0, MOVE)
    r.diff(5.1, scene(cube(location=(1, 0, 0))))
    r.event("recovered", 0.0, bs="s2", blender="5.2.2", file="")
    r.snapshot(0.0, "recovered", scene())
    r.report(0.5, MOVE, bs="s2")
    r.diff(0.6, scene(cube(location=(1, 0, 0))))
    result = r.run()
    assert [(i.segment, i.status) for i in result.items] == [(0, DRAFT), (1, REVIEW), (1, DRAFT)]
    assert result.items[2].changes == {("Cube", "location"): [1, 0, 0]}


# Real recordings ----------------------------------------------------------------------

def test_teacher_ten_minute_recording():
    result = generate_from_folder(os.path.join(RECORDINGS, "teacher-10min"))
    assert titles(result) == [
        "Enter Edit Mode", "Bevel (width 0.2)", "Switch to Face select mode", "Inset faces (thickness 0.3)",
        "Extrude by (0, 0, 1)", "Scale by 0.7", "Leave Edit Mode", "Opened file recorder_test_model.blend",
        "Enter Edit Mode", "Extrude by (0, 0, 0.5)", "Leave Edit Mode", "Add UV Sphere", "Move by (3, 0, 0)",
        "Shade Smooth", "Scale by 0.6", "Set Location Z of Sphere to 1.25",
    ]
    reasons = [i.reason for i in result.ignored]
    assert reasons.count("undone") == 2 and reasons.count("interface only") == 4


def test_gui_check_recording_with_crash_recovery():
    result = generate_from_folder(os.path.join(RECORDINGS, "gui-check-recovery"))
    assert "Duplicate" in titles(result, DRAFT)  # undone, then redone
    assert "Set Cube.001 dimensions to (3, 4, 4)" in titles(result, DRAFT)  # no report; from the state journal
    assert "Recording continued after Blender closed without stopping" in titles(result, REVIEW)
    assert [i.reason for i in result.ignored] == ["changed while recording was paused"]


def test_text_and_json_output():
    result = generate_from_folder(os.path.join(RECORDINGS, "teacher-10min"))
    text = render_text(result, "teacher-10min")
    assert "15 drafts, 1 to review, 6 not included" in text
    data = json.loads(json.dumps(to_json(result)))
    assert data["stats"]["drafts"] == 15 and len(data["items"]) == 16
