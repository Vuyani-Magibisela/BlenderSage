# SPDX-License-Identifier: GPL-3.0-or-later
"""Small lessons and scene states shared by the unit tests."""
import copy

MINIMAL = {
    "schema_version": 1,
    "id": "test-lesson",
    "title": "Test lesson",
    "targets": {
        "box": {"label": "box", "type": "MESH", "name_prefix": "Cube"},
    },
    "steps": [
        {
            "id": "exists",
            "title": "Have a box",
            "instruction": "Make sure the cube exists.",
            "target": "box",
            "checks": [{"type": "object_exists", "target": "box"}],
        },
        {
            "id": "size",
            "title": "Size the box",
            "instruction": "Scale it.",
            "target": "box",
            "ui_hint": {"editor": "VIEW_3D", "path": "Sidebar (N) > Item > Dimensions"},
            "checks": [{"type": "dimensions", "target": "box", "value": [0.3, 0.2, 0.1], "tolerance": 0.005}],
        },
        {
            "id": "edit",
            "title": "Delete the top face",
            "instruction": "In Edit Mode, delete the top face.",
            "manual_confirm": True,
            "checks": [],
        },
    ],
}


def lesson_data(**changes):
    data = copy.deepcopy(MINIMAL)
    data.update(changes)
    return data


def obj(name, type_="MESH", tag=None, dimensions=(2.0, 2.0, 2.0), modifiers=(), materials=(),
        scale=(1.0, 1.0, 1.0)):
    return {
        "name": name,
        "type": type_,
        "tag": tag,
        "dimensions": list(dimensions),
        "scale": list(scale),
        "modifiers": list(modifiers),
        "materials": list(materials),
    }


def state(*objects, mode="OBJECT", active=None, selected=()):
    return {"mode": mode, "active": active, "selected": list(selected), "objects": list(objects)}
