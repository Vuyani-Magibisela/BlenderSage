# SPDX-License-Identifier: GPL-3.0-or-later
"""Resolve a lesson's semantic target to one object in a scene state snapshot.

Order: objects tagged with the target id (custom property set by "Use selected"),
then objects matching the target's type and name prefix. Anything other than
exactly one match is reported as missing or ambiguous, never guessed.
"""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Resolution:
    status: str  # "found", "missing" or "ambiguous"
    name: str = None
    candidates: list = field(default_factory=list)


def resolve(target_id, target, state):
    objects = state["objects"]
    tagged = sorted(o["name"] for o in objects if o.get("tag") == target_id and o["type"] == target.type)
    if len(tagged) == 1:
        return Resolution("found", tagged[0], tagged)
    if len(tagged) > 1:
        return Resolution("ambiguous", None, tagged)
    matches = sorted(
        o["name"] for o in objects
        if o["type"] == target.type and o["name"].startswith(target.name_prefix)
    )
    if len(matches) == 1:
        return Resolution("found", matches[0], matches)
    return Resolution("ambiguous" if matches else "missing", None, matches)
