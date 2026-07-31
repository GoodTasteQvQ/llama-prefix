#!/usr/bin/env python3
"""Run the active Stage 3 unit and golden test suite."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    suite = unittest.defaultTestLoader.discover(
        str(ROOT / "tests/stage3"), pattern="test_*.py", top_level_dir=str(ROOT)
    )
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if result.wasSuccessful():
        print("STAGE3_E0_PASS")
        return 0
    print("STAGE3_E0_FAIL")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
