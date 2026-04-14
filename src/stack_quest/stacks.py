from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


class StackError(Exception):
    """Raised when a docker-compose lifecycle action fails."""


@dataclass
class StackResult:
    returncode: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0


def _compose_base(compose_file: Path) -> list[str]:
    if shutil.which("docker") is None:
        raise StackError("docker not found on PATH")
    if not compose_file.exists():
        raise StackError(f"compose file not found: {compose_file}")
    return ["docker", "compose", "-f", str(compose_file)]


def _run(cmd: list[str]) -> StackResult:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    return StackResult(proc.returncode, proc.stdout, proc.stderr)


def up(compose_file: Path) -> StackResult:
    return _run(_compose_base(compose_file) + ["up", "-d"])


def down(compose_file: Path, volumes: bool = False) -> StackResult:
    cmd = _compose_base(compose_file) + ["down"]
    if volumes:
        cmd.append("-v")
    return _run(cmd)


def ps(compose_file: Path) -> StackResult:
    return _run(_compose_base(compose_file) + ["ps"])
