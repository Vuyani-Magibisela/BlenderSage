# SPDX-License-Identifier: GPL-3.0-or-later
"""Differences between two scene state snapshots (shape: see core/checks.py).

diff_states(before, after) -> diff; apply_diff(before, diff) == after.
The state journal stores diffs, so a recording replays by applying them in order.
"""
import copy

_TOP_LEVEL = ("mode", "active", "selected")


def diff_states(before, after):
    diff = {key: copy.deepcopy(after[key]) for key in _TOP_LEVEL if before.get(key) != after.get(key)}
    old = {o["name"]: o for o in before["objects"]}
    new = {o["name"]: o for o in after["objects"]}
    objects = {}
    added = [copy.deepcopy(new[name]) for name in new if name not in old]
    removed = [name for name in old if name not in new]
    changed = {}
    for name in new:
        if name in old and new[name] != old[name]:
            changed[name] = {k: copy.deepcopy(v) for k, v in new[name].items() if old[name].get(k) != v}
    if added:
        objects["added"] = added
    if removed:
        objects["removed"] = removed
    if changed:
        objects["changed"] = changed
    if objects:
        diff["objects"] = objects
    return diff


def apply_diff(before, diff):
    state = copy.deepcopy(before)
    for key in _TOP_LEVEL:
        if key in diff:
            state[key] = copy.deepcopy(diff[key])
    objects = diff.get("objects", {})
    removed = set(objects.get("removed", []))
    rows = [o for o in state["objects"] if o["name"] not in removed]
    for row in rows:
        row.update(copy.deepcopy(objects.get("changed", {}).get(row["name"], {})))
    rows.extend(copy.deepcopy(objects.get("added", [])))
    state["objects"] = sorted(rows, key=lambda o: o["name"])
    return state
