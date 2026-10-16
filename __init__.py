# SPDX-License-Identifier: GPL-3.0-or-later
"""BlenderSage: guided lessons inside Blender. Registration only."""
from .blender import lifecycle, state
from .blender.guidance import operators, runtime, sidebar
from .blender.recorder import recorder
from .blender.recorder import ui as recorder_ui


def register():
    operators.register()
    sidebar.register()
    recorder_ui.register()


def unregister():
    if recorder.is_recording():
        recorder.stop(reason="extension disabled")
    runtime.stop_lesson()
    lifecycle.remove_all()
    recorder_ui.unregister()
    sidebar.unregister()
    operators.unregister()
