#!/usr/bin/env python
from __future__ import annotations

from pathlib import Path
import runpy
import sys


def run_script(script_name: str) -> int:
    scripts_dir = Path(__file__).resolve().parent
    script_path = scripts_dir / script_name
    if not script_path.exists():
        raise FileNotFoundError(f"Cannot find legacy script: {script_path}")
    sys.argv[0] = str(script_path)
    runpy.run_path(str(script_path), run_name="__main__")
    return 0
