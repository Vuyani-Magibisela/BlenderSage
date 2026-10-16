# SPDX-License-Identifier: GPL-3.0-or-later
"""Spike 0: list the Blender 5.2 API surface Milestone 1 depends on.

Run headless:
    blender -b --factory-startup --python-exit-code 1 --python spikes/s0_api_inventory.py
Prints one JSON document to stdout between INVENTORY-BEGIN / INVENTORY-END markers.
"""
import json
import sys

import bpy


def rna_props(struct):
    out = {}
    for p in struct.bl_rna.properties:
        if p.identifier == "rna_type":
            continue
        entry = {"type": p.type, "readonly": p.is_readonly}
        if p.type in {"POINTER", "COLLECTION"}:
            entry["fixed_type"] = p.fixed_type.identifier if p.fixed_type else None
        out[p.identifier] = entry
    return out


def rna_funcs(struct):
    out = {}
    for f in struct.bl_rna.functions:
        out[f.identifier] = {
            "description": f.description,
            "params": [
                {
                    "name": p.identifier,
                    "type": p.type,
                    "output": p.is_output,
                    "required": p.is_required,
                }
                for p in f.parameters
            ],
        }
    return out


inv = {
    "blender": bpy.app.version_string,
    "python": sys.version.split()[0],
    "background": bpy.app.background,
    "online_access": bpy.app.online_access,
    "window_manager_props": rna_props(bpy.types.WindowManager),
    "window_funcs": rna_funcs(bpy.types.Window),
    "operator_props": rna_props(bpy.types.Operator),
    "app_handlers": sorted(h for h in dir(bpy.app.handlers) if not h.startswith("_")),
    "msgbus": sorted(n for n in dir(bpy.msgbus) if not n.startswith("_")),
}

# Report struct: find the pointer type of any collection on WindowManager named like "report".
for name, entry in inv["window_manager_props"].items():
    if "report" in name.lower() and entry.get("fixed_type"):
        inv["report_struct_name"] = entry["fixed_type"]
        inv["report_struct_props"] = rna_props(getattr(bpy.types, entry["fixed_type"]))

try:
    import gpu
    inv["gpu_has_init"] = hasattr(gpu, "init")
except Exception as exc:  # gpu may be unavailable in background mode
    inv["gpu_import_error"] = repr(exc)

print("INVENTORY-BEGIN")
print(json.dumps(inv, indent=1, sort_keys=True))
print("INVENTORY-END")
