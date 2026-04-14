from __future__ import annotations

from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
ARCS_DIR = REPO_ROOT / "arcs"


@dataclass
class Exercise:
    id: str
    prompt: str
    check: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PortfolioSpec:
    template: str
    emit_to: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Arc:
    name: str
    closes_quests: list[str]
    stack: str
    exercises: list[Exercise]
    portfolio: PortfolioSpec
    path: Path = field(default_factory=Path)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "closes_quests": list(self.closes_quests),
            "stack": self.stack,
            "exercises": [e.to_dict() for e in self.exercises],
            "portfolio": self.portfolio.to_dict(),
        }

    def exercise(self, exercise_id: str) -> Exercise | None:
        for ex in self.exercises:
            if ex.id == exercise_id:
                return ex
        return None

    def stack_path(self) -> Path:
        return (REPO_ROOT / self.stack).resolve()

    def check_path(self, exercise_id: str) -> Path | None:
        ex = self.exercise(exercise_id)
        if ex is None:
            return None
        return (REPO_ROOT / ex.check).resolve()


class ArcError(Exception):
    """Raised when an arc cannot be loaded or is invalid."""


def _validate(data: dict[str, Any], source: Path) -> None:
    required = {"name", "closes_quests", "stack", "exercises", "portfolio"}
    missing = required - set(data or {})
    if missing:
        raise ArcError(f"{source.name}: missing keys: {sorted(missing)}")
    if not isinstance(data["exercises"], list) or not data["exercises"]:
        raise ArcError(f"{source.name}: 'exercises' must be a non-empty list")
    for ex in data["exercises"]:
        for key in ("id", "prompt", "check"):
            if key not in ex:
                raise ArcError(f"{source.name}: exercise missing '{key}'")
    for key in ("template", "emit_to"):
        if key not in data["portfolio"]:
            raise ArcError(f"{source.name}: portfolio missing '{key}'")


def load_arc(path: Path) -> Arc:
    data = yaml.safe_load(path.read_text()) or {}
    _validate(data, path)
    arc = Arc(
        name=data["name"],
        closes_quests=list(data["closes_quests"]),
        stack=data["stack"],
        exercises=[Exercise(**ex) for ex in data["exercises"]],
        portfolio=PortfolioSpec(**data["portfolio"]),
        path=path,
    )
    return arc


def list_arcs(arcs_dir: Path | None = None) -> list[Arc]:
    directory = arcs_dir or ARCS_DIR
    if not directory.exists():
        return []
    arcs: list[Arc] = []
    for path in sorted(directory.glob("*.yaml")):
        arcs.append(load_arc(path))
    return arcs


def get_arc(name: str, arcs_dir: Path | None = None) -> Arc:
    for arc in list_arcs(arcs_dir):
        if arc.name == name:
            return arc
    raise ArcError(f"arc not found: {name}")
