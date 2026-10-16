# SPDX-License-Identifier: GPL-3.0-or-later
"""Run the in-Blender tests.

    blender -b --factory-startup --python-exit-code 1 --python tests/blender/run_all.py
    blender -b --factory-startup --python-exit-code 1 --python tests/blender/run_all.py -- test_register

Collects test_*.py files in this folder and runs their test_* functions in file
order. Arguments after `--` filter by substring of "<file>::<function>".
Exits with code 1 when any test fails.
"""
import importlib.util
import os
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))


def _filters():
    argv = sys.argv
    return argv[argv.index("--") + 1:] if "--" in argv else []


def _load(path):
    name = "blender_test_" + os.path.splitext(os.path.basename(path))[0]
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    sys.path.insert(0, HERE)
    filters = _filters()
    passed, failed = 0, []
    for filename in sorted(f for f in os.listdir(HERE) if f.startswith("test_") and f.endswith(".py")):
        module = _load(os.path.join(HERE, filename))
        for name in sorted(n for n in dir(module) if n.startswith("test_")):
            test_id = f"{filename}::{name}"
            if filters and not any(f in test_id for f in filters):
                continue
            try:
                getattr(module, name)()
            except Exception:
                failed.append(test_id)
                print(f"FAIL {test_id}\n{traceback.format_exc()}")
            else:
                passed += 1
                print(f"ok   {test_id}")
    print(f"\n{passed} passed, {len(failed)} failed")
    if failed:
        sys.exit(1)


main()
