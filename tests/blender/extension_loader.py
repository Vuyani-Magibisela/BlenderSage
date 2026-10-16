# SPDX-License-Identifier: GPL-3.0-or-later
"""Import the extension package from the repository root under a fixed name.

Tests call register()/unregister() on the returned module directly, the same
entry points Blender uses when the extension is enabled or disabled.
"""
import importlib.util
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PACKAGE = "blendersage"


def load_extension():
    for name in [n for n in sys.modules if n == PACKAGE or n.startswith(PACKAGE + ".")]:
        del sys.modules[name]
    spec = importlib.util.spec_from_file_location(
        PACKAGE, os.path.join(REPO_ROOT, "__init__.py"), submodule_search_locations=[REPO_ROOT]
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[PACKAGE] = module
    spec.loader.exec_module(module)
    return module
