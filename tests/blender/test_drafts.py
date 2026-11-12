# SPDX-License-Identifier: GPL-3.0-or-later
"""Draft steps from a real (headless) recording: journals -> drafts.txt and drafts.json."""
import json
import os
import tempfile
from types import SimpleNamespace

import bpy

from extension_loader import load_extension

fake_reports = []


def _record(ext, directory, steps):
    rec = ext.blender.recorder.recorder
    fake_reports.clear()
    rec_id = rec.start(directory=directory, reports_source=lambda: fake_reports)
    for step in steps:
        step()
        rec.mark_dirty("depsgraph")
        rec.poll_reports()
        rec.snapshot_tick(force=True)
    rec.stop()
    return rec_id


def _report(message, type_="OPERATOR"):
    def step():
        fake_reports.append(SimpleNamespace(session_uid=len(fake_reports) + 1, type=type_, message=message))
    return step


def test_make_drafts_from_a_recording():
    ext = load_extension()
    ext.register()
    try:
        directory = tempfile.mkdtemp(prefix="blendersage-drafts-")
        cube = bpy.data.objects["Cube"]

        def move():
            cube.location.x = 1.0
            _report("bpy.ops.transform.translate(value=(1, 0, 0))")()

        def dimensions_edit():  # the N-panel Dimensions field leaves no report
            cube.dimensions = (3.0, 2.0, 2.0)
            bpy.context.view_layer.update()  # headless: re-evaluate so dimensions are current

        rec_id = _record(ext, directory, [move, dimensions_edit,
                                          _report("bpy.context.region.active_panel_category = 'Item'", "PROPERTY")])
        drafts = ext.blender.recorder.drafts
        assert drafts.latest_finished(directory) == rec_id
        result = drafts.make_drafts(rec_id, directory)
        assert [i.title for i in result.drafts] == ["Move by (1, 0, 0)", "Set Cube dimensions to (3, 2, 2)"]
        assert [i.reason for i in result.ignored] == ["interface only"]

        folder = os.path.join(directory, rec_id)
        with open(os.path.join(folder, "drafts.txt"), encoding="utf-8") as fh:
            assert "2 drafts, 0 to review, 1 not included" in fh.read()
        with open(os.path.join(folder, "drafts.json"), encoding="utf-8") as fh:
            data = json.load(fh)
        assert data["recording_id"] == rec_id and data["stats"]["drafts"] == 2
    finally:
        ext.unregister()


def test_unfinished_recordings_are_not_offered_for_drafts():
    ext = load_extension()
    ext.register()
    rec = ext.blender.recorder.recorder
    try:
        directory = tempfile.mkdtemp(prefix="blendersage-drafts-")
        rec.start(directory=directory, reports_source=lambda: [])
        rec._abandon()  # crashed: no stop entry
        assert ext.blender.recorder.drafts.latest_finished(directory) is None
    finally:
        ext.unregister()
