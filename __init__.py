# SPDX-License-Identifier: GPL-3.0-or-later
"""BlenderSage: guided lessons inside Blender. Registration only."""
from .blender import lifecycle, state
from .blender.guidance import operators, runtime, sidebar


def register():
    operators.register()
    sidebar.register()


def unregister():
    runtime.stop_lesson()
    lifecycle.remove_all()
    sidebar.unregister()
    operators.unregister()
