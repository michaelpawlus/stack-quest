from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass


def is_available() -> bool:
    return shutil.which("code-daily") is not None


@dataclass
class CompleteResult:
    quest: str
    ok: bool
    dry_run: bool
    message: str

    def to_dict(self) -> dict:
        return {
            "quest": self.quest,
            "ok": self.ok,
            "dry_run": self.dry_run,
            "message": self.message,
        }


def complete_quest(quest_id: str) -> CompleteResult:
    if not is_available():
        return CompleteResult(
            quest=quest_id,
            ok=False,
            dry_run=True,
            message="code-daily not on PATH; would mark quest complete",
        )
    proc = subprocess.run(
        ["code-daily", "quests", "complete", quest_id, "--json"],
        capture_output=True,
        text=True,
    )
    return CompleteResult(
        quest=quest_id,
        ok=proc.returncode == 0,
        dry_run=False,
        message=(proc.stdout or proc.stderr).strip(),
    )
