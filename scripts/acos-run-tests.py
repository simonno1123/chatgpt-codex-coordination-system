#!/usr/bin/env python3
"""Run each ACOS test file in its own process.

The test files load scripts under fixed canonical module identities, and some
scripts reject a second identity in the same interpreter. A single pytest
process over tests/ therefore stops at collection by design. This runner gives
every file a fresh interpreter and prints one summary line per file.

The live-runtime harness files run as their own __main__ under the isolated
flags (-I -S -B) that RuntimeBinding requires, with their acceptance checks.
All other files run under pytest.

It changes no repository files and uses no network or external services.
"""

from __future__ import annotations

import argparse
import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TESTS = ROOT / "tests"
ISOLATED = {
    "test_acos_v2_remote_context_live_adapter.py",
    "test_acos_v2_production_host_control_producer.py",
    "test_acos_v2_core_snapshot_host_preflight.py",
    "test_acos_v2_core_snapshot_d04_revocation_preflight.py",
}


def summary_line(output: str) -> str:
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    return lines[-1] if lines else "(no output)"


def command(path: Path) -> list[str]:
    if path.name in ISOLATED:
        return [sys.executable, "-I", "-S", "-B", str(path)]
    return [sys.executable, "-m", "pytest", str(path), "-q", "-p", "no:cacheprovider"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("files", nargs="*", help="test files (default: tests/test_*.py)")
    parser.add_argument("-v", "--verbose", action="store_true", help="print full output of failing files")
    args = parser.parse_args(argv)

    files = [Path(f).resolve() for f in args.files] or sorted(TESTS.glob("test_*.py"))
    if any(f.name not in ISOLATED for f in files) and importlib.util.find_spec("pytest") is None:
        print("pytest is required: python3 -m pip install -r requirements-test.txt", file=sys.stderr)
        return 2

    failed: list[str] = []
    for path in files:
        proc = subprocess.run(command(path), cwd=ROOT, capture_output=True, text=True)
        ok = proc.returncode == 0
        print(f"{'ok  ' if ok else 'FAIL'} {path.name:<58} {summary_line(proc.stdout)}")
        if not ok:
            failed.append(path.name)
            if args.verbose:
                print(proc.stdout + proc.stderr)

    print(f"\n{len(files) - len(failed)}/{len(files)} files ok")
    for name in failed:
        print(f"  failed: {name}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
