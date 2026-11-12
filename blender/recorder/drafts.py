# SPDX-License-Identifier: GPL-3.0-or-later
"""Turn a finished recording into draft steps (core/draft_generator.py) and save them
next to its journals as drafts.txt (to read) and drafts.json (for the future editor)."""
import json
import os

from ...core.draft_generator import generate_from_folder, render_text, to_json
from . import recorder


def latest_finished(directory=None):
    """Id of the newest recording that stopped normally, or None."""
    base = recorder.recordings_dir(directory)
    unfinished = set(recorder.unfinished_recordings(directory))
    current = (recorder.status() or {}).get("recording_id")
    names = [n for n in os.listdir(base)
             if os.path.isfile(os.path.join(base, n, "actions.jsonl")) and n not in unfinished and n != current]
    return max(names) if names else None   # ids start with the date and time


def make_drafts(recording_id, directory=None):
    """Generate drafts for one recording and write them beside it. Returns the result."""
    folder = os.path.join(recorder.recordings_dir(directory), recording_id)
    result = generate_from_folder(folder)
    with open(os.path.join(folder, "drafts.txt"), "w", encoding="utf-8") as fh:
        fh.write(render_text(result, f"Draft steps for recording {recording_id}"))
    with open(os.path.join(folder, "drafts.json"), "w", encoding="utf-8") as fh:
        json.dump({"recording_id": recording_id, **to_json(result)}, fh, indent=1)
    return result
