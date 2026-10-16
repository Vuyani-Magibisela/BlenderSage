# SPDX-License-Identifier: GPL-3.0-or-later
"""Lesson data model and validation (schema version 1, Milestone 1 prototype).

Lessons are declarative JSON data (CLAUDE.md rule 1). Validation is strict:
unknown keys, unknown check types and dangling target references are errors,
and every error is reported with its path in one SchemaError.
"""
import json
import math
from dataclasses import dataclass, field

SCHEMA_VERSION = 1
EDITORS = ("VIEW_3D", "PROPERTIES", "OUTLINER")
OBJECT_TYPES = ("MESH", "CURVE", "EMPTY", "LIGHT", "CAMERA")
MODES = ("OBJECT", "EDIT_MESH", "SCULPT")


class SchemaError(ValueError):
    def __init__(self, errors):
        self.errors = list(errors)
        super().__init__("Invalid lesson:\n" + "\n".join(f"- {e}" for e in self.errors))


@dataclass(frozen=True)
class Target:
    id: str
    label: str
    type: str
    name_prefix: str = ""


@dataclass(frozen=True)
class UiHint:
    editor: str
    path: str


@dataclass(frozen=True)
class Check:
    type: str
    target: str = ""
    mode: str = ""
    value: tuple = ()
    tolerance: float = 0.0
    modifier: str = ""
    settings: dict = field(default_factory=dict)
    name: str = ""  # material_assigned: required material name prefix (optional)


@dataclass(frozen=True)
class Step:
    id: str
    title: str
    instruction: str
    why: str = ""
    target: str = ""
    ui_hint: UiHint = None
    checks: tuple = ()
    hints: tuple = ()
    manual_confirm: bool = False


@dataclass(frozen=True)
class Lesson:
    id: str
    title: str
    targets: dict
    steps: tuple


# Allowed keys per check type (besides "type").
_CHECK_KEYS = {
    "object_exists": {"target"},
    "mode": {"mode"},
    "dimensions": {"target", "value", "tolerance"},
    "scale": {"target", "value", "tolerance"},
    "modifier": {"target", "modifier", "settings", "tolerance"},
    "material_assigned": {"target", "name"},
}
_REQUIRED_CHECK_KEYS = {
    "object_exists": {"target"},
    "mode": {"mode"},
    "dimensions": {"target", "value"},
    "scale": {"target", "value"},
    "modifier": {"target", "modifier"},
    "material_assigned": {"target"},
}


class _Validator:
    def __init__(self):
        self.errors = []

    def err(self, path, message):
        self.errors.append(f"{path}: {message}")

    def keys(self, data, path, allowed, required):
        if not isinstance(data, dict):
            self.err(path, "must be an object")
            return False
        for key in data:
            if key not in allowed:
                self.err(path, f"unexpected key '{key}'")
        for key in sorted(required - set(data)):
            self.err(path, f"missing key '{key}'")
        return True

    def text(self, data, key, path, required=True):
        value = data.get(key, "")
        if not isinstance(value, str) or (required and not value.strip()):
            self.err(f"{path}.{key}", "must be a non-empty string" if required else "must be a string")
            return ""
        return value

    def number(self, value, path):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            self.err(path, "must be a finite number")
            return 0.0
        return float(value)


def parse_lesson(source):
    """Parse a lesson from a JSON string or an already-decoded dict."""
    if isinstance(source, str):
        try:
            source = json.loads(source)
        except json.JSONDecodeError as exc:
            raise SchemaError([f"not valid JSON: {exc}"]) from None
    v = _Validator()
    if not v.keys(source, "lesson", {"schema_version", "id", "title", "targets", "steps"},
                  {"schema_version", "id", "title", "targets", "steps"}):
        raise SchemaError(v.errors)
    if source.get("schema_version") != SCHEMA_VERSION:
        v.err("lesson.schema_version", f"must be {SCHEMA_VERSION}")
    lesson_id = v.text(source, "id", "lesson")
    title = v.text(source, "title", "lesson")

    targets = {}
    raw_targets = source.get("targets", {})
    if not isinstance(raw_targets, dict):
        v.err("targets", "must be an object")
        raw_targets = {}
    for tid, raw in raw_targets.items():
        path = f"targets.{tid}"
        if not v.keys(raw, path, {"label", "type", "name_prefix"}, {"label", "type"}):
            continue
        if raw.get("type") not in OBJECT_TYPES:
            v.err(f"{path}.type", f"must be one of {', '.join(OBJECT_TYPES)}")
        targets[tid] = Target(tid, v.text(raw, "label", path), raw.get("type", ""),
                              v.text(raw, "name_prefix", path, required=False))

    steps, seen = [], set()
    raw_steps = source.get("steps", [])
    if not isinstance(raw_steps, list) or not raw_steps:
        v.err("steps", "must be a non-empty list")
        raw_steps = []
    for i, raw in enumerate(raw_steps):
        step = _parse_step(v, raw, f"steps[{i}]", targets)
        if step is None:
            continue
        if step.id in seen:
            v.err(f"steps[{i}].id", f"duplicate step id '{step.id}'")
        seen.add(step.id)
        steps.append(step)

    if v.errors:
        raise SchemaError(v.errors)
    return Lesson(lesson_id, title, targets, tuple(steps))


def _target_ref(v, data, key, path, targets, required):
    ref = data.get(key, "")
    if not ref and not required:
        return ""
    if ref not in targets:
        v.err(f"{path}.{key}", f"unknown target '{ref}'")
    return ref


def _parse_step(v, raw, path, targets):
    allowed = {"id", "title", "instruction", "why", "target", "ui_hint", "checks", "hints", "manual_confirm"}
    if not v.keys(raw, path, allowed, {"id", "title", "instruction", "checks"}):
        return None
    ui_hint = None
    if "ui_hint" in raw:
        hint = raw["ui_hint"]
        if v.keys(hint, f"{path}.ui_hint", {"editor", "path"}, {"editor", "path"}):
            if hint.get("editor") not in EDITORS:
                v.err(f"{path}.ui_hint.editor", f"must be one of {', '.join(EDITORS)}")
            ui_hint = UiHint(hint.get("editor", ""), v.text(hint, "path", f"{path}.ui_hint"))
    checks = []
    raw_checks = raw.get("checks", [])
    if not isinstance(raw_checks, list):
        v.err(f"{path}.checks", "must be a list")
        raw_checks = []
    for j, rc in enumerate(raw_checks):
        check = _parse_check(v, rc, f"{path}.checks[{j}]", targets)
        if check is not None:
            checks.append(check)
    manual = raw.get("manual_confirm", False)
    if not isinstance(manual, bool):
        v.err(f"{path}.manual_confirm", "must be true or false")
        manual = False
    if not raw_checks and not manual:
        v.err(path, "has no checks, so manual_confirm must be true")
    hints = raw.get("hints", [])
    if not isinstance(hints, list) or not all(isinstance(h, str) for h in hints):
        v.err(f"{path}.hints", "must be a list of strings")
        hints = []
    return Step(
        id=v.text(raw, "id", path),
        title=v.text(raw, "title", path),
        instruction=v.text(raw, "instruction", path),
        why=v.text(raw, "why", path, required=False),
        target=_target_ref(v, raw, "target", path, targets, required=False),
        ui_hint=ui_hint,
        checks=tuple(checks),
        hints=tuple(hints),
        manual_confirm=manual,
    )


def _parse_check(v, raw, path, targets):
    if not isinstance(raw, dict):
        v.err(path, "must be an object")
        return None
    ctype = raw.get("type")
    if ctype not in _CHECK_KEYS:
        v.err(f"{path}.type", f"unknown check type '{ctype}'")
        return None
    if not v.keys(raw, path, _CHECK_KEYS[ctype] | {"type"}, _REQUIRED_CHECK_KEYS[ctype] | {"type"}):
        return None
    kwargs = {"type": ctype}
    if "target" in _CHECK_KEYS[ctype]:
        kwargs["target"] = _target_ref(v, raw, "target", path, targets, required=True)
    if ctype == "mode":
        if raw["mode"] not in MODES:
            v.err(f"{path}.mode", f"must be one of {', '.join(MODES)}")
        kwargs["mode"] = raw["mode"]
    if ctype in ("dimensions", "scale"):
        value = raw["value"]
        if not isinstance(value, list) or len(value) != 3:
            v.err(f"{path}.value", "must be a list of 3 numbers")
            value = [0, 0, 0]
        kwargs["value"] = tuple(v.number(x, f"{path}.value[{k}]") for k, x in enumerate(value))
    if "tolerance" in raw:
        kwargs["tolerance"] = v.number(raw["tolerance"], f"{path}.tolerance")
        if kwargs["tolerance"] < 0:
            v.err(f"{path}.tolerance", "must not be negative")
    if ctype == "modifier":
        kwargs["modifier"] = v.text(raw, "modifier", path)
        settings = raw.get("settings", {})
        if not isinstance(settings, dict):
            v.err(f"{path}.settings", "must be an object")
            settings = {}
        for key, value in settings.items():
            if not isinstance(value, (bool, int, float, str)):
                v.err(f"{path}.settings.{key}", "must be a number, string or boolean")
            elif isinstance(value, float) and not math.isfinite(value):
                v.err(f"{path}.settings.{key}", "must be a finite number")
        kwargs["settings"] = dict(settings)
    if ctype == "material_assigned" and "name" in raw:
        kwargs["name"] = v.text(raw, "name", path)
    return Check(**kwargs)
