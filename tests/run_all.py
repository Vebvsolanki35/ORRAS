"""
tests/run_all.py — Run the complete ORRAS test suite and exit non-zero on
any failure, so it can be wired straight into CI or a pre-commit hook.

Usage:
    python tests/run_all.py            # run everything
    python tests/run_all.py --quick    # skip the slower page-render suite
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent

SUITES: list[tuple[str, str]] = [
    ("Engine unit tests", "test_engines.py"),
    ("Pipeline contract suite", "test_pipeline.py"),
    ("Page render suite", "test_pages.py"),
]

QUICK_SUITES = {"Engine unit tests", "Pipeline contract suite"}


def main() -> int:
    quick = "--quick" in sys.argv

    print("=" * 70)
    print("ORRAS TEST SUITE")
    print("=" * 70)

    results: list[tuple[str, int]] = []
    failed = 0

    for name, script in SUITES:
        if quick and name not in QUICK_SUITES:
            print(f"\n>> {name}: SKIPPED (--quick)")
            continue

        print(f"\n>> {name}")
        print("-" * 70)
        started = time.time()
        proc = subprocess.run(
            [sys.executable, str(HERE / script)],
            cwd=str(HERE),
            capture_output=True,
            text=True,
        )
        elapsed = time.time() - started

        output = proc.stdout + proc.stderr
        # Print only the summary block to keep the top-level output readable.
        lines = output.splitlines()
        tail = lines[-25:] if len(lines) > 25 else lines
        for line in tail:
            print(line)

        results.append((name, proc.returncode))
        if proc.returncode != 0:
            failed += 1
        print(f"   ({elapsed:.1f}s, exit={proc.returncode})")

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    for name, code in results:
        status = "PASS" if code == 0 else "FAIL"
        print(f"  [{status}] {name}")
    skipped = len(SUITES) - len(results)
    if skipped:
        print(f"  [SKIP] {skipped} suite(s) skipped")

    if failed:
        print(f"\n❌ {failed} suite(s) failed.")
        return 1

    print(f"\n✅ All {len(results)} suite(s) passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
