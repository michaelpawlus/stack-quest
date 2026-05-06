from __future__ import annotations

import json
import shutil
import subprocess
from typing import Any


def is_available() -> bool:
    return shutil.which("beacon") is not None


def list_gaps() -> list[dict[str, Any]]:
    """Return beacon gaps as a list of dicts, or [] if beacon isn't installed.

    Accepts both the v1 envelope (`{"schema_version": 1, "gaps": [...]}`) and
    the legacy bare-array format. See beacon/CLAUDE.md "Gaps subcommand
    contract" for the field schema.
    """
    if not is_available():
        return []
    try:
        proc = subprocess.run(
            ["beacon", "gaps", "list", "--json"],
            capture_output=True,
            text=True,
            timeout=20,
        )
    except (subprocess.TimeoutExpired, OSError):
        return []
    if proc.returncode != 0 or not proc.stdout.strip():
        return []
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return []
    if isinstance(data, dict) and isinstance(data.get("gaps"), list):
        return data["gaps"]
    return data if isinstance(data, list) else []
