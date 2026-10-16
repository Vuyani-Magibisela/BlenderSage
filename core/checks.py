# SPDX-License-Identifier: GPL-3.0-or-later
"""Evaluate a step's completion checks against a scene state snapshot.

Checks look at results (what the scene is), not at the sequence of clicks.
The snapshot shape is produced by blender/state.py:
    {"mode", "active", "selected", "objects": [{"name", "type", "tag",
      "dimensions", "scale", "modifiers": [{"type", "name", "settings"}], "materials"}]}
"""
from dataclasses import dataclass, field

from .targets import resolve


@dataclass(frozen=True)
class CheckResult:
    passed: bool
    message: str


@dataclass(frozen=True)
class StepEvaluation:
    results: list
    resolutions: dict = field(default_factory=dict)

    @property
    def complete(self):
        return bool(self.results) and all(r.passed for r in self.results)


def evaluate_step(lesson, step, state):
    referenced = {c.target for c in step.checks if c.target}
    if step.target:
        referenced.add(step.target)
    resolutions = {tid: resolve(tid, lesson.targets[tid], state) for tid in sorted(referenced)}
    by_name = {o["name"]: o for o in state["objects"]}
    results = [_evaluate(check, lesson, state, resolutions, by_name) for check in step.checks]
    return StepEvaluation(results, resolutions)


def _fmt(values):
    return " × ".join(f"{v:.3f}" for v in values)


def _target_object(check, lesson, resolutions, by_name):
    r = resolutions[check.target]
    label = lesson.targets[check.target].label
    if r.status == "found":
        return by_name[r.name], None
    if r.status == "ambiguous":
        return None, CheckResult(False, f"Select the {label} and click 'Use selected'")
    return None, CheckResult(False, f"Waiting for the {label}")


def _evaluate(check, lesson, state, resolutions, by_name):
    if check.type == "mode":
        ok = state["mode"] == check.mode
        return CheckResult(ok, f"Mode is {state['mode']}" + ("" if ok else f"; switch to {check.mode}"))

    obj, waiting = _target_object(check, lesson, resolutions, by_name)
    if waiting:
        return waiting
    label = lesson.targets[check.target].label

    if check.type == "object_exists":
        return CheckResult(True, f"Found the {label} ({obj['name']})")

    if check.type in ("dimensions", "scale"):
        have = obj[check.type]
        ok = all(abs(h - w) <= check.tolerance for h, w in zip(have, check.value))
        unit = " m" if check.type == "dimensions" else ""
        message = f"{check.type.title()} {_fmt(have)}{unit}"
        if not ok:
            message += f"; need {_fmt(check.value)}{unit} (±{check.tolerance:g})"
        return CheckResult(ok, message)

    if check.type == "modifier":
        mods = [m for m in obj["modifiers"] if m["type"] == check.modifier]
        if not mods:
            return CheckResult(False, f"Add a {check.modifier.title()} modifier to the {label}")
        problems = []
        for key, want in check.settings.items():
            have = mods[0]["settings"].get(key)
            if not _same(have, want, check.tolerance):
                problems.append(f"{key} is {have!r}, need {want!r}")
        if problems:
            return CheckResult(False, f"{check.modifier.title()}: " + "; ".join(problems))
        return CheckResult(True, f"{check.modifier.title()} modifier set")

    if check.type == "material_assigned":
        assigned = [m for m in obj["materials"] if m]
        if check.name:
            ok = any(m.startswith(check.name) for m in assigned)
            wanted = f"a material named '{check.name}'"
        else:
            ok = bool(assigned)
            wanted = "a material"
        return CheckResult(ok, f"Material assigned ({', '.join(assigned)})" if ok
                           else f"Assign {wanted} to the {label}")

    return CheckResult(False, f"Unsupported check '{check.type}'")


def _same(have, want, tolerance):
    if isinstance(want, bool) or isinstance(want, str):
        return have == want
    if isinstance(have, bool) or not isinstance(have, (int, float)):
        return False
    return abs(have - want) <= tolerance
