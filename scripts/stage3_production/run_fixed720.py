#!/usr/bin/env python3
"""Validate or allocate the fixed720 candidate frame."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from stage3_pipeline.fixed720_runner import main


if __name__ == "__main__":
    raise SystemExit(main())
