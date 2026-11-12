# SPDX-License-Identifier: GPL-3.0-or-later
"""Recorder panel and buttons in the BlenderSage sidebar tab (teacher authoring)."""
import bpy

from . import recorder

_unfinished = {"ids": None}  # cached so panel redraws do not read journal files


def unfinished():
    if _unfinished["ids"] is None:
        try:
            _unfinished["ids"] = recorder.unfinished_recordings()
        except Exception:  # no extension user folder (e.g. not installed as an extension)
            _unfinished["ids"] = []
    return _unfinished["ids"]


def _forget_unfinished():
    _unfinished["ids"] = None


class BLENDERSAGE_OT_record_start(bpy.types.Operator):
    bl_idname = "blendersage.record_start"
    bl_label = "Start Recording"
    bl_description = "Record your modelling actions and scene changes into a journal on this computer"

    @classmethod
    def poll(cls, context):
        return not recorder.is_recording()

    def execute(self, context):
        rec_id = recorder.start()
        _forget_unfinished()
        self.report({"INFO"}, f"Recording {rec_id}")
        return {"FINISHED"}


class BLENDERSAGE_OT_record_continue(bpy.types.Operator):
    bl_idname = "blendersage.record_continue"
    bl_label = "Continue Unfinished Recording"
    bl_description = "Continue the most recent recording that did not stop normally (for example after a crash)"

    @classmethod
    def poll(cls, context):
        return not recorder.is_recording() and bool(unfinished())

    def execute(self, context):
        rec_id = recorder.start(continue_id=unfinished()[-1])
        _forget_unfinished()
        self.report({"INFO"}, f"Continuing recording {rec_id}")
        return {"FINISHED"}


class BLENDERSAGE_OT_record_pause(bpy.types.Operator):
    bl_idname = "blendersage.record_pause"
    bl_label = "Pause"
    bl_description = "Pause recording; nothing you do is recorded until you resume"

    @classmethod
    def poll(cls, context):
        return recorder.is_recording() and not recorder.is_paused()

    def execute(self, context):
        recorder.pause()
        return {"FINISHED"}


class BLENDERSAGE_OT_record_resume(bpy.types.Operator):
    bl_idname = "blendersage.record_resume"
    bl_label = "Resume"
    bl_description = "Resume recording"

    @classmethod
    def poll(cls, context):
        return recorder.is_paused()

    def execute(self, context):
        recorder.resume()
        return {"FINISHED"}


class BLENDERSAGE_OT_record_stop(bpy.types.Operator):
    bl_idname = "blendersage.record_stop"
    bl_label = "Stop Recording"
    bl_description = "Stop recording and close the journal files"

    @classmethod
    def poll(cls, context):
        return recorder.is_recording()

    def execute(self, context):
        folder = recorder.status()["folder"]
        recorder.stop()
        _forget_unfinished()
        self.report({"INFO"}, f"Recording saved in {folder}")
        return {"FINISHED"}


class BLENDERSAGE_OT_record_open_folder(bpy.types.Operator):
    bl_idname = "blendersage.record_open_folder"
    bl_label = "Open Recordings Folder"
    bl_description = "Open the folder that holds recordings"

    def execute(self, context):
        bpy.ops.wm.path_open(filepath=recorder.recordings_dir())
        return {"FINISHED"}


class BLENDERSAGE_PT_recorder(bpy.types.Panel):
    bl_label = "Recorder"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "BlenderSage"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        info = recorder.status()
        if info is None:
            layout.operator("blendersage.record_start", icon="REC")
            if unfinished():
                layout.label(text="An earlier recording did not stop normally.", icon="ERROR")
                layout.operator("blendersage.record_continue", icon="RECOVER_LAST")
            layout.operator("blendersage.record_open_folder", icon="FILE_FOLDER")
            return
        state = "Paused" if info["paused"] else "Recording"
        layout.label(text=f"{state}: {info['recording_id']}", icon="PAUSE" if info["paused"] else "REC")
        layout.label(text=f"Actions: {info['actions']}   Snapshots: {info['snapshots']}")
        row = layout.row(align=True)
        if info["paused"]:
            row.operator("blendersage.record_resume", icon="PLAY")
        else:
            row.operator("blendersage.record_pause", icon="PAUSE")
        row.operator("blendersage.record_stop", icon="SNAP_FACE")


classes = (
    BLENDERSAGE_OT_record_start,
    BLENDERSAGE_OT_record_continue,
    BLENDERSAGE_OT_record_pause,
    BLENDERSAGE_OT_record_resume,
    BLENDERSAGE_OT_record_stop,
    BLENDERSAGE_OT_record_open_folder,
    BLENDERSAGE_PT_recorder,
)
_register, _unregister = bpy.utils.register_classes_factory(classes)


def register():
    _forget_unfinished()
    _register()


def unregister():
    _unregister()
