# SPDX-License-Identifier: GPL-3.0-or-later
"""BlenderSage: guided lessons inside Blender. Registration only."""
from .blender import lifecycle
from .blender.guidance import sidebar


def register():
    sidebar.register()


def unregister():
    lifecycle.remove_all()
    sidebar.unregister()
