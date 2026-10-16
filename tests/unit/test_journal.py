# SPDX-License-Identifier: GPL-3.0-or-later
import json

import pytest

from core.journal import JournalError, JournalWriter, read_journal


def test_new_journal_starts_with_header(tmp_path):
    path = tmp_path / "actions.jsonl"
    with JournalWriter(path, stream="actions", recording_id="rec-1") as w:
        w.append({"kind": "report", "uid": 1})
    header, entries, truncated = read_journal(path)
    assert header["format"] == "blendersage-journal"
    assert header["version"] == 1
    assert header["stream"] == "actions"
    assert header["recording_id"] == "rec-1"
    assert entries == [{"kind": "report", "uid": 1}]
    assert truncated is False


def test_entry_is_on_disk_before_close(tmp_path):
    path = tmp_path / "actions.jsonl"
    w = JournalWriter(path, stream="actions", recording_id="rec-1")
    w.append({"kind": "report", "uid": 7})
    # Read while the writer is still open: a crash right now must not lose the entry.
    _, entries, _ = read_journal(path)
    assert entries[-1]["uid"] == 7
    w.close()


def test_reopening_appends_without_second_header(tmp_path):
    path = tmp_path / "state.jsonl"
    with JournalWriter(path, stream="state", recording_id="rec-1") as w:
        w.append({"kind": "a"})
    with JournalWriter(path, stream="state", recording_id="rec-1") as w:
        w.append({"kind": "b"})
    lines = path.read_text(encoding="utf-8").splitlines()
    assert sum(1 for line in lines if '"format"' in line) == 1
    assert [e["kind"] for e in read_journal(path)[1]] == ["a", "b"]


def test_reopening_with_other_recording_id_is_refused(tmp_path):
    path = tmp_path / "state.jsonl"
    JournalWriter(path, stream="state", recording_id="rec-1").close()
    with pytest.raises(JournalError):
        JournalWriter(path, stream="state", recording_id="rec-2")


def test_truncated_last_line_is_tolerated(tmp_path):
    path = tmp_path / "actions.jsonl"
    with JournalWriter(path, stream="actions", recording_id="rec-1") as w:
        w.append({"kind": "report", "uid": 1})
    with open(path, "a", encoding="utf-8") as fh:
        fh.write('{"kind": "report", "ui')  # crash mid-write
    header, entries, truncated = read_journal(path)
    assert entries == [{"kind": "report", "uid": 1}]
    assert truncated is True


def test_appending_after_truncation_starts_on_a_new_line(tmp_path):
    path = tmp_path / "actions.jsonl"
    with JournalWriter(path, stream="actions", recording_id="rec-1") as w:
        w.append({"kind": "report", "uid": 1})
    with open(path, "a", encoding="utf-8") as fh:
        fh.write('{"kind": "rep')
    with JournalWriter(path, stream="actions", recording_id="rec-1") as w:
        w.append({"kind": "recovered"})
    header, entries, truncated = read_journal(path)
    assert [e["kind"] for e in entries] == ["report", "recovered"]
    assert truncated is True  # the broken line is still reported, not silently dropped


def test_entries_are_one_json_object_per_line(tmp_path):
    path = tmp_path / "actions.jsonl"
    with JournalWriter(path, stream="actions", recording_id="rec-1") as w:
        w.append({"kind": "report", "message": "line one\nline two"})
    for line in path.read_text(encoding="utf-8").splitlines():
        json.loads(line)
