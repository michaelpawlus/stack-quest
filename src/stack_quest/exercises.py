from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from .arcs import Arc, Exercise


@dataclass
class CheckResult:
    exercise_id: str
    passed: bool
    stdout: str
    stderr: str
    returncode: int

    def to_dict(self) -> dict:
        return {
            "exercise_id": self.exercise_id,
            "passed": self.passed,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "returncode": self.returncode,
        }


class ExerciseError(Exception):
    """Raised when an exercise or check is misconfigured."""


def next_exercise(arc: Arc, passed: list[str]) -> Exercise | None:
    passed_set = set(passed)
    for ex in arc.exercises:
        if ex.id not in passed_set:
            return ex
    return None


def run_check(arc: Arc, exercise_id: str) -> CheckResult:
    check_path = arc.check_path(exercise_id)
    if check_path is None:
        raise ExerciseError(f"exercise not found: {exercise_id}")
    if not check_path.exists():
        raise ExerciseError(f"check script not found: {check_path}")
    proc = subprocess.run(
        [sys.executable, str(check_path)],
        capture_output=True,
        text=True,
    )
    return CheckResult(
        exercise_id=exercise_id,
        passed=proc.returncode == 0,
        stdout=proc.stdout,
        stderr=proc.stderr,
        returncode=proc.returncode,
    )
