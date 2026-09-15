"""
tests/harness.py — Shared helpers for the ORRAS headless test suite.

Provides a small, dependency-free assertion toolkit plus helpers for
running the data pipeline and Streamlit pages without a browser.
"""

from __future__ import annotations

import importlib
import io
import os
import sys
import traceback
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.chdir(ROOT)

# Silence Streamlit's "missing ScriptRunContext" noise during headless runs.
os.environ.setdefault("STREAMLIT_BROWSER_GATHER_USAGE_STATS", "false")


class Results:
    """Collects pass/fail results and prints a readable summary."""

    def __init__(self, title: str) -> None:
        self.title = title
        self.passed: list[str] = []
        self.failed: list[tuple[str, str]] = []
        self.section = ""

    def begin(self, section: str) -> None:
        self.section = section
        print(f"\n── {section} {'─' * max(0, 58 - len(section))}")

    def ok(self, name: str, detail: str = "") -> None:
        self.passed.append(f"{self.section}::{name}")
        suffix = f"  ({detail})" if detail else ""
        print(f"  PASS  {name}{suffix}")

    def fail(self, name: str, detail: str) -> None:
        self.failed.append((f"{self.section}::{name}", detail))
        first = detail.strip().splitlines()[0] if detail.strip() else ""
        print(f"  FAIL  {name}  ->  {first}")

    def check(self, name: str, condition: bool, detail: str = "") -> bool:
        if condition:
            self.ok(name, detail)
        else:
            self.fail(name, detail or "condition was False")
        return bool(condition)

    def check_no_raise(self, name: str, fn, detail: str = ""):
        """Run fn(); pass if it does not raise, fail with the traceback."""
        try:
            value = fn()
        except Exception:  # noqa: BLE001 - test harness surfaces everything
            self.fail(name, traceback.format_exc())
            return None
        self.ok(name, detail)
        return value

    @property
    def total(self) -> int:
        return len(self.passed) + len(self.failed)

    def summary(self) -> int:
        print("\n" + "=" * 70)
        print(f"{self.title}: {len(self.passed)}/{self.total} checks passed")
        if self.failed:
            print(f"\n{len(self.failed)} FAILURE(S):")
            for name, detail in self.failed:
                print(f"\n### {name}\n{detail}")
        else:
            print("All checks passed.")
        print("=" * 70)
        return 1 if self.failed else 0


def quiet(fn, *args, **kwargs):
    """Run fn while swallowing stdout/stderr (Streamlit logs are noisy)."""
    buf = io.StringIO()
    with redirect_stdout(buf), redirect_stderr(buf):
        return fn(*args, **kwargs)


def fresh_modules(names: list[str]) -> None:
    """Force-reimport modules so config/env changes take effect."""
    for name in names:
        sys.modules.pop(name, None)
    for name in names:
        importlib.import_module(name)


def run_pipeline():
    """Execute the ORRAS pipeline defined in app.run_pipeline."""
    from app import run_pipeline as _run

    return quiet(_run)


def page_files() -> list[Path]:
    """Return app.py plus every Streamlit page script, in display order."""
    files = [ROOT / "app.py"]
    files.extend(sorted((ROOT / "pages").glob("*.py")))
    return [f for f in files if f.name != "__init__.py"]


def apptest_run(path: Path):
    """
    Run a Streamlit script headlessly with AppTest.

    Returns:
        Tuple: (AppTest instance, error_message or None)
    """
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(str(path), default_timeout=300)
    try:
        quiet(at.run)
    except Exception as exc:  # noqa: BLE001
        return at, f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}"
    return at, None


def apptest_errors(at) -> list[str]:
    """Collect every exception element Streamlit rendered on the page."""
    errors = []
    for exc in getattr(at, "exception", []):
        errors.append(f"[{exc.type}] {exc.value}")
    for err in getattr(at, "error", []):
        errors.append(f"[st.error] {err.value}")
    return errors
