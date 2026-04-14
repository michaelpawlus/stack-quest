from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any


def is_available() -> bool:
    return shutil.which("skillvault") is not None


def scan(path: Path) -> dict[str, Any] | None:
    if not is_available():
        return None
    proc = subprocess.run(
        ["skillvault", "scan", str(path), "--json"],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0 or not proc.stdout.strip():
        return None
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        return None
