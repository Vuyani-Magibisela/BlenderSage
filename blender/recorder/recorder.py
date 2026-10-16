# SPDX-License-Identifier: GPL-3.0-or-later
"""Records a teacher's modelling session into two append-only journals.

actions.jsonl: OPERATOR and PROPERTY reports from WindowManager.reports (polled by a
  persistent timer, de-duplicated by session_uid), plus start, pause, resume, undo,
  redo, file_loaded, recovered and stop entries.
state.jsonl: a full snapshot at start/resume/recovery, then diffs of the scene state
  (blender/state.py), taken by an idle timer at most once per throttle interval.

Handlers only collect reports already in Blender and queue entries; the timer writes
them in order (CLAUDE.md rule 3). Report text is stored as evidence and never run.
Recording happens only after the teacher clicks Start (CLAUDE.md rule 7).
"""
import os
import time
import uuid
from datetime import datetime, timezone

import bpy
from bpy.app.handlers import persistent

from ...core.journal import JournalWriter, read_journal
from ...core.state_diff import diff_states
from .. import lifecycle, state

RECORDED_TYPES = {"OPERATOR", "PROPERTY"}
POLL_SECONDS = 0.1
TICK_SECONDS = 0.25
DEFAULT_THROTTLE_SECONDS = 1.0
BLENDER_SESSION = uuid.uuid4().hex[:12]  # identifies this Blender process in report entries

_rec = None  # state of the active recording, or None


def _default_reports():
    return bpy.context.window_manager.reports


def recordings_dir(directory=None):
    """Where recordings are stored: the extension's user data folder by default."""
    if directory:
        return directory
    package = __name__.rsplit(".blender.", 1)[0]
    return bpy.utils.extension_path_user(package, path="recordings", create=True)


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def is_recording():
    return _rec is not None


def is_paused():
    return _rec is not None and _rec["paused"]


def status():
    if _rec is None:
        return None
    timings = _rec["snapshot_ms"]
    return {
        "recording_id": _rec["id"],
        "folder": _rec["folder"],
        "paused": _rec["paused"],
        "elapsed": time.monotonic() - _rec["t0"],
        "actions": _rec["action_count"],
        "snapshots": _rec["diff_count"],
        "snapshot_ms_mean": sum(timings) / len(timings) if timings else None,
        "snapshot_ms_max": max(timings) if timings else None,
    }


def _t():
    return round(time.monotonic() - _rec["t0"], 3)


def _collect():
    """Queue new reports (read-only access to Blender). Safe inside handlers."""
    for r in _rec["source"]():
        uid = r.session_uid
        if uid <= _rec["last_uid"]:
            continue
        _rec["last_uid"] = uid
        if _rec["paused"] or r.type not in RECORDED_TYPES:
            continue
        _rec["queue"].append({"kind": "report", "t": _t(), "bs": BLENDER_SESSION,
                              "uid": uid, "type": r.type, "message": r.message})


def _flush():
    for entry in _rec["queue"]:
        _rec["actions"].append(entry)
        if entry["kind"] == "report":
            _rec["action_count"] += 1
    _rec["queue"].clear()


def mark_dirty(trigger):
    if _rec is not None and not _rec["paused"] and trigger not in _rec["triggers"]:
        _rec["triggers"].append(trigger)


def pending_triggers():
    return list(_rec["triggers"]) if _rec else []


def _full_snapshot(reason):
    snap = state.snapshot()
    _rec["states"].append({"kind": "snapshot", "reason": reason, "t": _t(), "full": snap})
    _rec["last_state"] = snap
    _rec["triggers"].clear()
    _rec["last_snapshot"] = time.monotonic()


# Timer callbacks -------------------------------------------------------------------

def poll_reports():
    if _rec is None:
        return None
    _collect()
    _flush()
    return POLL_SECONDS


def snapshot_tick(force=False):
    if _rec is None:
        return None
    if _rec["paused"] or not _rec["triggers"]:
        return TICK_SECONDS
    if not force and time.monotonic() - _rec["last_snapshot"] < _rec["throttle"]:
        return TICK_SECONDS
    t0 = time.perf_counter()
    snap = state.snapshot()
    changes = diff_states(_rec["last_state"], snap)
    _rec["snapshot_ms"].append((time.perf_counter() - t0) * 1000)
    if changes:
        _rec["states"].append({"kind": "diff", "t": _t(), "triggers": list(_rec["triggers"]), "changes": changes})
        _rec["diff_count"] += 1
        _rec["last_state"] = snap
    _rec["triggers"].clear()
    _rec["last_snapshot"] = time.monotonic()
    return TICK_SECONDS


# App handlers (persistent so recording continues across file loads) ----------------

@persistent
def on_undo_post(*_args):
    if _rec is not None:
        _collect()
        if not _rec["paused"]:
            _rec["queue"].append({"kind": "undo", "t": _t()})
        mark_dirty("undo")


@persistent
def on_redo_post(*_args):
    if _rec is not None:
        _collect()
        if not _rec["paused"]:
            _rec["queue"].append({"kind": "redo", "t": _t()})
        mark_dirty("redo")


@persistent
def on_load_pre(*_args):
    if _rec is not None:
        _collect()  # loading a file clears wm.reports


@persistent
def on_load_post(*_args):
    if _rec is not None:
        _rec["queue"].append({"kind": "file_loaded", "t": _t(), "file": os.path.basename(bpy.data.filepath)})
        mark_dirty("load")


@persistent
def on_depsgraph_update_post(*_args):
    mark_dirty("depsgraph")


# Control -----------------------------------------------------------------------------

def start(directory=None, continue_id=None, reports_source=None, throttle_seconds=DEFAULT_THROTTLE_SECONDS):
    """Start a new recording, or continue an unfinished one. Returns the recording id."""
    global _rec
    if _rec is not None:
        raise RuntimeError("already recording")
    base = recordings_dir(directory)
    rec_id = continue_id or datetime.now().strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:4]
    folder = os.path.join(base, rec_id)
    os.makedirs(folder, exist_ok=True)
    source = reports_source or _default_reports
    _rec = {
        "id": rec_id,
        "folder": folder,
        "source": source,
        "actions": JournalWriter(os.path.join(folder, "actions.jsonl"), "actions", rec_id),
        "states": JournalWriter(os.path.join(folder, "state.jsonl"), "state", rec_id),
        "t0": time.monotonic(),
        "last_uid": max((r.session_uid for r in source()), default=0),
        "paused": False,
        "queue": [],
        "triggers": [],
        "throttle": throttle_seconds,
        "action_count": 0,
        "diff_count": 0,
        "snapshot_ms": [],
    }
    kind = "recovered" if continue_id else "start"
    _rec["actions"].append({"kind": kind, "t": 0.0, "wall": _now(), "bs": BLENDER_SESSION,
                            "blender": bpy.app.version_string, "file": os.path.basename(bpy.data.filepath)})
    _full_snapshot(kind)
    _rec["tokens"] = [
        lifecycle.add_timer(poll_reports, first_interval=POLL_SECONDS, persistent=True),
        lifecycle.add_timer(snapshot_tick, first_interval=TICK_SECONDS, persistent=True),
        lifecycle.add_app_handler("undo_post", on_undo_post),
        lifecycle.add_app_handler("redo_post", on_redo_post),
        lifecycle.add_app_handler("load_pre", on_load_pre),
        lifecycle.add_app_handler("load_post", on_load_post),
        lifecycle.add_app_handler("depsgraph_update_post", on_depsgraph_update_post),
    ]
    return rec_id


def pause():
    _collect()
    _rec["queue"].append({"kind": "pause", "t": _t()})
    _flush()
    _rec["paused"] = True
    _rec["actions"].sync()
    _rec["states"].sync()


def resume():
    _collect()  # skips reports made while paused
    _rec["paused"] = False
    _rec["queue"].append({"kind": "resume", "t": _t()})
    _flush()
    _full_snapshot("resume")


def stop(reason="stopped"):
    global _rec
    if _rec is None:
        return
    _collect()
    if not _rec["paused"]:
        snapshot_tick(force=True)
    _rec["queue"].append({"kind": "stop", "reason": reason, "t": _t()})
    _flush()
    _close()


def _close():
    global _rec
    lifecycle.remove(*_rec["tokens"])
    _rec["actions"].close()
    _rec["states"].close()
    _rec = None


def _abandon():
    """Test helper: end the recording the way a crash would (no stop entry)."""
    _close()


def unfinished_recordings(directory=None):
    base = recordings_dir(directory)
    found = []
    for name in sorted(os.listdir(base)):
        path = os.path.join(base, name, "actions.jsonl")
        if not os.path.isfile(path) or (_rec is not None and _rec["id"] == name):
            continue
        try:
            _, entries, _ = read_journal(path)
        except (OSError, ValueError):
            continue
        if not any(e.get("kind") == "stop" for e in entries):
            found.append(name)
    return found
