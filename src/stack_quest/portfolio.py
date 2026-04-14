from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .arcs import Arc, REPO_ROOT


class PortfolioError(Exception):
    """Raised when portfolio emission fails."""


@dataclass
class EmitResult:
    arc_name: str
    emitted_to: Path
    files_written: list[str]

    def to_dict(self) -> dict:
        return {
            "arc_name": self.arc_name,
            "emitted_to": str(self.emitted_to),
            "files_written": self.files_written,
        }


def _render_tree(template_dir: Path, target: Path, context: dict) -> list[str]:
    env = Environment(
        loader=FileSystemLoader(str(template_dir)),
        autoescape=select_autoescape(disabled_extensions=("md", "txt", "yml", "yaml")),
        keep_trailing_newline=True,
    )
    written: list[str] = []
    for src in template_dir.rglob("*"):
        rel = src.relative_to(template_dir)
        dest = target / rel
        if src.is_dir():
            dest.mkdir(parents=True, exist_ok=True)
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        if src.suffix in {".md", ".yml", ".yaml", ".txt", ".j2"}:
            tmpl = env.get_template(str(rel))
            rendered = tmpl.render(**context)
            if dest.suffix == ".j2":
                dest = dest.with_suffix("")
            dest.write_text(rendered)
        else:
            shutil.copy2(src, dest)
        written.append(str(dest.relative_to(target)))
    return written


def emit(arc: Arc, override_path: Path | None = None) -> EmitResult:
    template_dir = (REPO_ROOT / arc.portfolio.template).resolve()
    if not template_dir.exists():
        raise PortfolioError(f"template directory not found: {template_dir}")

    if override_path is not None:
        target = override_path.resolve()
    else:
        target = (REPO_ROOT / arc.portfolio.emit_to).resolve()

    target.mkdir(parents=True, exist_ok=True)

    context = {
        "arc_name": arc.name,
        "closes_quests": arc.closes_quests,
        "exercises": [
            {"id": ex.id, "prompt": ex.prompt} for ex in arc.exercises
        ],
    }
    written = _render_tree(template_dir, target, context)
    return EmitResult(arc_name=arc.name, emitted_to=target, files_written=written)
