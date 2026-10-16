# SPDX-License-Identifier: GPL-3.0-or-later
"""Append-only journal files (JSON Lines).

The first line is a header; every later line is one entry. Each append is
flushed to the operating system immediately, so entries survive Blender
crashing. sync() also forces them to disk (call it on pause and stop).
A half-written last line, as left by a crash, is skipped and reported.
"""
import json
import os
from datetime import datetime, timezone

FORMAT = "blendersage-journal"
VERSION = 1


class JournalError(ValueError):
    pass


def _read_header(path):
    with open(path, encoding="utf-8") as fh:
        first = fh.readline()
    try:
        header = json.loads(first)
    except json.JSONDecodeError:
        raise JournalError(f"{path}: first line is not a journal header") from None
    if header.get("format") != FORMAT:
        raise JournalError(f"{path}: not a {FORMAT} file")
    if header.get("version") != VERSION:
        raise JournalError(f"{path}: unsupported journal version {header.get('version')!r}")
    return header


class JournalWriter:
    def __init__(self, path, stream, recording_id):
        self.path = os.fspath(path)
        exists = os.path.exists(self.path) and os.path.getsize(self.path) > 0
        if exists:
            header = _read_header(self.path)
            if header.get("recording_id") != recording_id or header.get("stream") != stream:
                raise JournalError(f"{self.path}: belongs to another recording or stream")
            with open(self.path, "rb") as fh:
                fh.seek(-1, os.SEEK_END)
                needs_newline = fh.read(1) != b"\n"
        self._fh = open(self.path, "a", encoding="utf-8", newline="\n")
        if exists:
            if needs_newline:
                self._fh.write("\n")  # end the line a crash left half-written
                self._fh.flush()
        else:
            self._write({
                "format": FORMAT,
                "version": VERSION,
                "stream": stream,
                "recording_id": recording_id,
                "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            })

    def _write(self, obj):
        self._fh.write(json.dumps(obj, ensure_ascii=False, separators=(",", ":")) + "\n")
        self._fh.flush()

    def append(self, entry):
        self._write(entry)

    def sync(self):
        self._fh.flush()
        os.fsync(self._fh.fileno())

    def close(self):
        if not self._fh.closed:
            self.sync()
            self._fh.close()

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        self.close()


def read_journal(path):
    """Return (header, entries, truncated). Unreadable lines are skipped and flagged."""
    header = _read_header(path)
    entries, truncated = [], False
    with open(path, encoding="utf-8") as fh:
        fh.readline()
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                truncated = True
    return header, entries, truncated
