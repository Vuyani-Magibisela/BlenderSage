# SPDX-License-Identifier: GPL-3.0-or-later
"""Read-only snapshot of the scene properties lessons check.

Produces plain data (see core/checks.py for the shape). Never calls bpy.ops, so
it is safe from timers. The recorder's state journal will reuse this.
"""
import bpy

TAG_PROPERTY = "blendersage_target"
_SIMPLE = {"BOOLEAN", "INT", "FLOAT", "ENUM", "STRING"}


def _mode():
    ob = bpy.context.view_layer.objects.active
    if ob is None:
        return "OBJECT"
    if ob.mode == "EDIT":
        return "EDIT_" + ob.type  # e.g. EDIT_MESH, matching bpy.context.mode
    return ob.mode


def _modifier_settings(mod):
    out = {}
    for prop in mod.bl_rna.properties:
        if prop.type not in _SIMPLE or prop.identifier in {"rna_type", "name"}:
            continue
        if getattr(prop, "is_array", False) or getattr(prop, "array_length", 0):
            continue
        if prop.type == "ENUM" and prop.is_enum_flag:
            continue
        out[prop.identifier] = getattr(mod, prop.identifier)
    return out


def _object(ob):
    tag = ob.get(TAG_PROPERTY)
    return {
        "name": ob.name,
        "type": ob.type,
        "tag": tag if isinstance(tag, str) else None,
        "dimensions": list(ob.dimensions),
        "scale": list(ob.scale),
        "modifiers": [
            {"type": m.type, "name": m.name, "settings": _modifier_settings(m)} for m in ob.modifiers
        ],
        "materials": [slot.material.name if slot.material else None for slot in ob.material_slots],
    }


def snapshot():
    view_layer = bpy.context.view_layer
    active = view_layer.objects.active
    return {
        "mode": _mode(),
        "active": active.name if active else None,
        "selected": sorted(o.name for o in view_layer.objects if o.select_get()),
        "objects": [_object(o) for o in sorted(view_layer.objects, key=lambda o: o.name)],
    }
