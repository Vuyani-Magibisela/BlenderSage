# SPDX-License-Identifier: GPL-3.0-or-later
"""Install the built extension zip through Blender's extension system, enable,
disable and uninstall it, and check that Blender is left as it was.

Run with user files redirected to a temporary folder so the real Blender setup
is untouched (PowerShell):

    $env:BLENDER_USER_RESOURCES = "<empty temp dir>"
    & $B -b --factory-startup --python-exit-code 1 --python tests/blender/check_install.py -- <path to blendersage-x.y.z.zip>
"""
import os
import sys

import addon_utils
import bpy

MODULE = "bl_ext.user_default.blendersage"
PANEL = "BLENDERSAGE_PT_lesson"


def handler_counts():
    return {
        name: len(getattr(bpy.app.handlers, name))
        for name in dir(bpy.app.handlers)
        if isinstance(getattr(bpy.app.handlers, name), list)
    }


def main():
    zip_path = sys.argv[sys.argv.index("--") + 1]
    user_resources = os.environ.get("BLENDER_USER_RESOURCES")
    assert user_resources, "set BLENDER_USER_RESOURCES to a temporary folder first"

    before = handler_counts()
    bpy.ops.extensions.package_install_files(filepath=zip_path, repo="user_default", enable_on_install=True)
    enabled, loaded = addon_utils.check(MODULE)
    assert enabled and loaded, f"not enabled after install: enabled={enabled} loaded={loaded}"
    assert hasattr(bpy.types, PANEL), "panel missing after enable"
    print("ok   installed and enabled", MODULE)

    bpy.ops.preferences.addon_disable(module=MODULE)
    assert not addon_utils.check(MODULE)[0], "still enabled after disable"
    assert not hasattr(bpy.types, PANEL), "panel left after disable"
    assert handler_counts() == before, "app handlers changed after disable"
    print("ok   disabled; no panel or handlers left")

    repos = bpy.context.preferences.extensions.repos
    repo_index = next(i for i, r in enumerate(repos) if r.module == "user_default")
    package_dir = os.path.join(repos[repo_index].directory, "blendersage")
    assert os.path.isdir(package_dir), f"installed files not found at {package_dir}"
    bpy.ops.extensions.package_uninstall(repo_index=repo_index, pkg_id="blendersage")
    assert not os.path.exists(package_dir), "files left after uninstall"
    print("ok   uninstalled; files removed")


main()
