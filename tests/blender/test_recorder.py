# SPDX-License-Identifier: GPL-3.0-or-later
"""Recorder: journals, throttled snapshots, pause/resume, recovery, clean shutdown.

Background mode stores no WindowManager.reports, so these tests feed the recorder
stand-in reports. tests/blender/gui_check_recorder.py checks the real stream.
"""
import os
import tempfile
from types import SimpleNamespace

import bpy

from extension_loader import load_extension

fake_reports = []


def report(uid, message, type_="OPERATOR"):
    fake_reports.append(SimpleNamespace(session_uid=uid, type=type_, message=message))


def _start(**kwargs):
    fake_reports.clear()
    ext = load_extension()
    ext.register()
    rec = ext.blender.recorder.recorder
    directory = tempfile.mkdtemp(prefix="blendersage-rec-")
    rec_id = rec.start(directory=directory, reports_source=lambda: fake_reports, **kwargs)
    return ext, rec, directory, rec_id


def _journal(ext, directory, rec_id, stream):
    return ext.core.journal.read_journal(os.path.join(directory, rec_id, f"{stream}.jsonl"))


def _kinds(entries):
    return [e["kind"] for e in entries]


def test_start_writes_headers_and_initial_snapshot():
    ext, rec, directory, rec_id = _start()
    try:
        header, actions, _ = _journal(ext, directory, rec_id, "actions")
        assert header["stream"] == "actions" and header["recording_id"] == rec_id
        assert _kinds(actions) == ["start"]
        _, states, _ = _journal(ext, directory, rec_id, "state")
        assert states[0]["kind"] == "snapshot" and states[0]["full"]["active"] == "Cube"
    finally:
        ext.unregister()


def test_reports_are_journaled_once_and_only_supported_types():
    ext, rec, directory, rec_id = _start()
    try:
        report(1, "bpy.ops.transform.translate(value=(1, 0, 0))")
        report(2, "Saved \"x.blend\"", "INFO")
        report(3, 'bpy.context.object.modifiers["Bevel"].width = 0.65', "PROPERTY")
        rec.poll_reports()
        rec.poll_reports()  # second poll must not duplicate
        _, actions, _ = _journal(ext, directory, rec_id, "actions")
        got = [(e["uid"], e["type"]) for e in actions if e["kind"] == "report"]
        assert got == [(1, "OPERATOR"), (3, "PROPERTY")]
        assert all("t" in e and "bs" in e for e in actions if e["kind"] == "report")
    finally:
        ext.unregister()


def test_reports_before_start_are_not_recorded():
    fake_reports.clear()
    ext = load_extension()
    ext.register()
    rec = ext.blender.recorder.recorder
    report(1, "bpy.ops.mesh.primitive_cube_add()")
    directory = tempfile.mkdtemp(prefix="blendersage-rec-")
    rec_id = rec.start(directory=directory, reports_source=lambda: fake_reports)
    try:
        report(2, "bpy.ops.mesh.primitive_uv_sphere_add()")
        rec.poll_reports()
        _, actions, _ = _journal(ext, directory, rec_id, "actions")
        assert [e["uid"] for e in actions if e["kind"] == "report"] == [2]
    finally:
        ext.unregister()


def test_snapshots_are_throttled_and_stored_as_diffs():
    ext, rec, directory, rec_id = _start(throttle_seconds=60.0)
    try:
        bpy.data.objects["Cube"].location.x = 2.0
        rec.mark_dirty("depsgraph")
        rec.mark_dirty("depsgraph")
        rec.snapshot_tick(force=True)  # first change: written
        bpy.data.objects["Cube"].location.x = 3.0
        rec.mark_dirty("depsgraph")
        rec.snapshot_tick()  # within the throttle interval: not written yet
        _, states, _ = _journal(ext, directory, rec_id, "state")
        diffs = [e for e in states if e["kind"] == "diff"]
        assert len(diffs) == 1
        assert diffs[0]["changes"]["objects"]["changed"]["Cube"]["location"][0] == 2.0
        assert diffs[0]["triggers"] == ["depsgraph"]
    finally:
        ext.unregister()


def test_snapshot_without_change_writes_nothing():
    ext, rec, directory, rec_id = _start(throttle_seconds=0.0)
    try:
        rec.mark_dirty("depsgraph")
        rec.snapshot_tick()
        _, states, _ = _journal(ext, directory, rec_id, "state")
        assert [e["kind"] for e in states] == ["snapshot"]
    finally:
        ext.unregister()


def test_pause_skips_actions_and_resume_takes_full_snapshot():
    ext, rec, directory, rec_id = _start()
    try:
        rec.pause()
        report(1, "bpy.ops.object.delete()")
        rec.poll_reports()
        rec.resume()
        report(2, "bpy.ops.mesh.primitive_cube_add()")
        rec.poll_reports()
        _, actions, _ = _journal(ext, directory, rec_id, "actions")
        assert _kinds(actions) == ["start", "pause", "resume", "report"]
        assert actions[-1]["uid"] == 2
        _, states, _ = _journal(ext, directory, rec_id, "state")
        assert [e.get("reason") for e in states if e["kind"] == "snapshot"] == ["start", "resume"]
    finally:
        ext.unregister()


def test_undo_and_redo_are_journaled_and_trigger_snapshots():
    ext, rec, directory, rec_id = _start(throttle_seconds=0.0)
    try:
        rec.on_undo_post()
        rec.on_redo_post()
        rec.poll_reports()
        _, actions, _ = _journal(ext, directory, rec_id, "actions")
        assert [e["kind"] for e in actions][-2:] == ["undo", "redo"]
        assert rec.pending_triggers() == ["undo", "redo"]
    finally:
        ext.unregister()


def test_reports_are_captured_before_a_file_load_clears_them():
    ext, rec, directory, rec_id = _start()
    try:
        report(5, "bpy.ops.object.shade_smooth()")
        rec.on_load_pre()
        fake_reports.clear()  # what loading a file does to wm.reports
        bpy.ops.wm.read_homefile(use_empty=True)
        rec.on_load_post()
        rec.poll_reports()
        _, actions, _ = _journal(ext, directory, rec_id, "actions")
        assert [e["uid"] for e in actions if e["kind"] == "report"] == [5]
        assert "file_loaded" in _kinds(actions)
        assert rec.is_recording()
    finally:
        ext.unregister()


def test_hooks_are_persistent_and_removed_on_stop():
    ext, rec, directory, rec_id = _start()
    counts = ext.blender.lifecycle.active_counts()
    assert counts["timers"] == 2
    assert counts["app_handlers"] == 5
    bpy.ops.wm.read_homefile(use_empty=True)
    assert all(bpy.app.timers.is_registered(f) for f in (rec.poll_reports, rec.snapshot_tick))
    rec.stop()
    assert ext.blender.lifecycle.active_counts() == dict.fromkeys(counts, 0)
    _, actions, _ = _journal(ext, directory, rec_id, "actions")
    assert actions[-1] == {"kind": "stop", "reason": "stopped", "t": actions[-1]["t"]}
    ext.unregister()


def test_disable_mid_recording_stops_cleanly():
    ext, rec, directory, rec_id = _start()
    ext.unregister()
    _, actions, _ = _journal(ext, directory, rec_id, "actions")
    assert actions[-1]["kind"] == "stop" and actions[-1]["reason"] == "extension disabled"
    assert not rec.is_recording()
    assert ext.blender.lifecycle.active_counts()["timers"] == 0


def test_crashed_recording_can_be_continued():
    ext, rec, directory, rec_id = _start()
    try:
        report(1, "bpy.ops.mesh.primitive_cube_add()")
        rec.poll_reports()
        rec._abandon()  # what a crash leaves: open journal, no stop entry
        assert rec.unfinished_recordings(directory) == [rec_id]
        again = rec.start(directory=directory, continue_id=rec_id, reports_source=lambda: fake_reports)
        assert again == rec_id
        report(2, "bpy.ops.object.delete()")
        rec.poll_reports()
        rec.stop()
        _, actions, _ = _journal(ext, directory, rec_id, "actions")
        assert _kinds(actions) == ["start", "report", "recovered", "report", "stop"]
        assert rec.unfinished_recordings(directory) == []
    finally:
        ext.unregister()
