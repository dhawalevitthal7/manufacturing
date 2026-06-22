"""
Phase 4.3 verification (V4.3a–c): print narrative lines, then run pytest for rollup tests.

Usage (repo root):
  python scripts/verify_v43_phase.py
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    print("V4.3a–c: running pytest tests/test_okr_cascade_service_v43.py …")
    r = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            str(ROOT / "tests" / "test_okr_cascade_service_v43.py"),
            "-v",
            "--tb=short",
        ],
        cwd=str(ROOT),
    )
    if r.returncode != 0:
        sys.exit(r.returncode)
    print("V4.3a PASS (functional-only child in parent rollup)")
    print("V4.3b PASS (parent_id-only hierarchy unchanged)")
    print(
        "V4.3c PASS (both edges to same parent: duplicate child slots → "
        "higher weighted average vs dedupe when mixed with low-progress sibling)"
    )
    print("V4.3c (tree): same node id listed twice under parent children when both links set")


if __name__ == "__main__":
    main()
