from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path


def _state_dir() -> Path:
    base = os.environ.get("STACK_QUEST_STATE_DIR")
    if base:
        return Path(base)
    return Path.home() / ".local" / "share" / "stack-quest"


def state_db_path() -> Path:
    d = _state_dir()
    d.mkdir(parents=True, exist_ok=True)
    return d / "state.db"


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(state_db_path())
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS arc_state (
            arc_name TEXT PRIMARY KEY,
            active INTEGER NOT NULL DEFAULT 0,
            current_exercise TEXT,
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS exercise_progress (
            arc_name TEXT NOT NULL,
            exercise_id TEXT NOT NULL,
            passed_at TEXT NOT NULL DEFAULT (datetime('now')),
            PRIMARY KEY (arc_name, exercise_id)
        )
        """
    )
    conn.commit()
    return conn


@dataclass
class ArcState:
    arc_name: str
    active: bool
    current_exercise: str | None
    passed: list[str]


def get_state(arc_name: str) -> ArcState | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT arc_name, active, current_exercise FROM arc_state WHERE arc_name = ?",
            (arc_name,),
        ).fetchone()
        if row is None:
            return None
        passed = [
            r["exercise_id"]
            for r in conn.execute(
                "SELECT exercise_id FROM exercise_progress WHERE arc_name = ? ORDER BY passed_at",
                (arc_name,),
            ).fetchall()
        ]
    return ArcState(
        arc_name=row["arc_name"],
        active=bool(row["active"]),
        current_exercise=row["current_exercise"],
        passed=passed,
    )


def active_arc() -> ArcState | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT arc_name FROM arc_state WHERE active = 1 LIMIT 1"
        ).fetchone()
    if row is None:
        return None
    return get_state(row["arc_name"])


def set_active(arc_name: str, current_exercise: str | None) -> None:
    with _connect() as conn:
        conn.execute("UPDATE arc_state SET active = 0")
        conn.execute(
            """
            INSERT INTO arc_state (arc_name, active, current_exercise)
            VALUES (?, 1, ?)
            ON CONFLICT(arc_name) DO UPDATE SET
                active = 1,
                current_exercise = excluded.current_exercise,
                updated_at = datetime('now')
            """,
            (arc_name, current_exercise),
        )
        conn.commit()


def set_inactive(arc_name: str) -> None:
    with _connect() as conn:
        conn.execute(
            "UPDATE arc_state SET active = 0, updated_at = datetime('now') WHERE arc_name = ?",
            (arc_name,),
        )
        conn.commit()


def record_pass(arc_name: str, exercise_id: str) -> None:
    with _connect() as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO exercise_progress (arc_name, exercise_id)
            VALUES (?, ?)
            """,
            (arc_name, exercise_id),
        )
        conn.commit()


def set_current_exercise(arc_name: str, exercise_id: str | None) -> None:
    with _connect() as conn:
        conn.execute(
            "UPDATE arc_state SET current_exercise = ?, updated_at = datetime('now') WHERE arc_name = ?",
            (exercise_id, arc_name),
        )
        conn.commit()


def reset_arc(arc_name: str) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM exercise_progress WHERE arc_name = ?", (arc_name,))
        conn.execute("DELETE FROM arc_state WHERE arc_name = ?", (arc_name,))
        conn.commit()
