#!/usr/bin/env python3
"""Print a candidate host runtime profile for the running interpreter.

The output is a proposal for review, not an approval: a host becomes eligible
only after a reviewed commit adds the entry to acos-v2-host-runtime-profiles.json.
This tool reads local interpreter facts only and writes no files.
"""

from __future__ import annotations

import argparse
import json
import platform
import sys
import sysconfig
from pathlib import Path


def dependency_root() -> str:
    # -I ignores pyvenv.cfg, so locate a virtual environment's site-packages directly.
    venv = Path(sys.executable).parent.parent
    if (venv / "pyvenv.cfg").is_file():
        return str((venv / "lib" / ("python%d.%d" % sys.version_info[:2]) / "site-packages").resolve())
    return str(Path(sysconfig.get_path("purelib")).resolve())


def candidate() -> dict:
    interpreter = str(Path(sys.executable).resolve())
    return {"interpreter": interpreter,
            # The OS-reported process image. A macOS framework build reports its
            # Python.app binary instead; list that in runtime_files and here.
            "process_binary": interpreter,
            "runtime_files": [],
            "python_version": platform.python_version(),
            "architecture": platform.machine(),
            "dependency_root": dependency_root()}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("name", help="profile name, [A-Za-z0-9_-]{1,128}")
    args = parser.parse_args(argv)
    print(json.dumps({args.name: candidate()}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
