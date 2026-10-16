# SPDX-License-Identifier: GPL-3.0-or-later
import os
import sys

# Make `core` importable as a top-level package without importing the bpy-dependent root.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
