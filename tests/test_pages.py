"""
tests/test_pages.py — Renders every ORRAS Streamlit page headlessly with
Streamlit's AppTest and reports any exception raised during rendering.

Run with:  python tests/test_pages.py [optional/page.py ...]
"""

from __future__ import annotations

import sys

from harness import Results, apptest_errors, apptest_run, page_files


def main() -> int:
    r = Results("Page render suite")

    targets = [p for p in page_files()]
    if len(sys.argv) > 1:
        wanted = set(sys.argv[1:])
        targets = [p for p in targets if p.name in wanted or str(p) in wanted]
        if not targets:
            print(f"No matching pages for {wanted}")
            return 2

    for path in targets:
        r.begin(path.name)
        at, hard_error = apptest_run(path)

        if hard_error:
            r.fail("script runs without raising", hard_error)
            continue

        errors = apptest_errors(at)
        if errors:
            for err in errors[:5]:
                r.fail("page renders without exceptions", err)
        else:
            body = len(getattr(at, "markdown", [])) + len(getattr(at, "dataframe", []))
            r.ok("page renders without exceptions", f"{body} elements")

        # Surface warnings that indicate degraded rendering.
        warnings = [w.value for w in getattr(at, "warning", [])]
        if warnings:
            print(f"  NOTE  {len(warnings)} warning(s):")
            for w in warnings[:5]:
                print(f"        - {w}")

    return r.summary()


if __name__ == "__main__":
    sys.exit(main())
