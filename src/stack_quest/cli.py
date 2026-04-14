from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Optional

import typer
from rich.console import Console
from rich.table import Table

from . import __version__
from .arcs import ArcError, get_arc, list_arcs
from .exercises import ExerciseError, next_exercise, run_check
from .integrations import beacon, code_daily, skillvault
from .portfolio import PortfolioError, emit
from .stacks import StackError, down, ps, up
from . import state as state_mod


app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="Turn beacon skill-gap quests into weekend-sized learning arcs.",
)
arcs_app = typer.Typer(no_args_is_help=True, help="List, show, and suggest arcs.")
portfolio_app = typer.Typer(no_args_is_help=True, help="Emit portfolio artifacts.")
app.add_typer(arcs_app, name="arcs")
app.add_typer(portfolio_app, name="portfolio")


stdout = Console()
stderr = Console(stderr=True)


def _emit(payload: Any, json_mode: bool, render_human) -> None:
    if json_mode:
        stdout.print_json(data=payload)
    else:
        render_human()


def _error(message: str, code: int = 1, json_mode: bool = False) -> "typer.Exit":
    if json_mode:
        stdout.print_json(data={"error": message, "code": code})
    else:
        stderr.print(f"[red]error:[/red] {message}")
    return typer.Exit(code=code)


@app.callback(invoke_without_command=True)
def _root(
    ctx: typer.Context,
    version: bool = typer.Option(False, "--version", help="Print version and exit."),
) -> None:
    if version:
        typer.echo(__version__)
        raise typer.Exit()
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())
        raise typer.Exit()


# ---------- arcs ----------


@arcs_app.command("list")
def arcs_list(json_: bool = typer.Option(False, "--json", help="Emit JSON.")) -> None:
    try:
        arcs = list_arcs()
    except ArcError as e:
        raise _error(str(e), json_mode=json_)

    payload = [
        {
            "name": a.name,
            "closes_quests": a.closes_quests,
            "exercises": len(a.exercises),
        }
        for a in arcs
    ]

    def render() -> None:
        if not arcs:
            stderr.print("[yellow]no arcs found[/yellow]")
            return
        table = Table(title="stack-quest arcs")
        table.add_column("name", style="bold")
        table.add_column("closes")
        table.add_column("exercises", justify="right")
        for a in arcs:
            table.add_row(a.name, ", ".join(a.closes_quests), str(len(a.exercises)))
        stdout.print(table)

    _emit(payload, json_, render)


@arcs_app.command("show")
def arcs_show(
    arc_name: str = typer.Argument(..., metavar="ARC_NAME"),
    json_: bool = typer.Option(False, "--json"),
) -> None:
    try:
        arc = get_arc(arc_name)
    except ArcError as e:
        raise _error(str(e), code=2, json_mode=json_)

    payload = arc.to_dict()

    def render() -> None:
        stdout.print(f"[bold]{arc.name}[/bold]")
        stdout.print(f"  stack: {arc.stack}")
        stdout.print(f"  closes quests: {', '.join(arc.closes_quests)}")
        stdout.print("  exercises:")
        for ex in arc.exercises:
            stdout.print(f"    - {ex.id}: {ex.prompt}")
        stdout.print(f"  portfolio template: {arc.portfolio.template}")
        stdout.print(f"  portfolio emit_to: {arc.portfolio.emit_to}")

    _emit(payload, json_, render)


@arcs_app.command("suggest")
def arcs_suggest(json_: bool = typer.Option(False, "--json")) -> None:
    """Cross-reference beacon gaps against arcs and suggest the best one."""
    try:
        arcs = list_arcs()
    except ArcError as e:
        raise _error(str(e), json_mode=json_)

    gaps = beacon.list_gaps()
    gap_skills = {g.get("skill", "").lower() for g in gaps if isinstance(g, dict)}

    suggestions: list[dict[str, Any]] = []
    for arc in arcs:
        overlap = sorted(set(arc.closes_quests) & gap_skills)
        suggestions.append(
            {"arc": arc.name, "matched_gaps": overlap, "score": len(overlap)}
        )
    suggestions.sort(key=lambda s: s["score"], reverse=True)

    payload = {"beacon_available": beacon.is_available(), "suggestions": suggestions}

    def render() -> None:
        if not beacon.is_available():
            stderr.print("[yellow]beacon not on PATH; showing static arcs[/yellow]")
        for s in suggestions:
            matched = ", ".join(s["matched_gaps"]) if s["matched_gaps"] else "-"
            stdout.print(f"  {s['arc']}: score={s['score']} matched=[{matched}]")

    _emit(payload, json_, render)


# ---------- arc lifecycle ----------


@app.command()
def start(
    arc_name: str = typer.Argument(..., metavar="ARC_NAME"),
    json_: bool = typer.Option(False, "--json"),
) -> None:
    """Start an arc: bring up its stack and mark the first exercise current."""
    try:
        arc = get_arc(arc_name)
    except ArcError as e:
        raise _error(str(e), code=2, json_mode=json_)

    try:
        result = up(arc.stack_path())
    except StackError as e:
        raise _error(str(e), json_mode=json_)

    if not result.ok:
        raise _error(
            f"docker compose up failed: {result.stderr.strip() or result.stdout.strip()}",
            json_mode=json_,
        )

    existing = state_mod.get_state(arc.name)
    passed = existing.passed if existing else []
    nxt = next_exercise(arc, passed)
    state_mod.set_active(arc.name, nxt.id if nxt else None)

    payload = {
        "arc": arc.name,
        "stack": str(arc.stack_path()),
        "current_exercise": nxt.id if nxt else None,
        "prompt": nxt.prompt if nxt else None,
    }

    def render() -> None:
        stdout.print(f"[green]started[/green] {arc.name}")
        stdout.print(f"  stack: {arc.stack_path()}")
        if nxt:
            stdout.print(f"  current: [bold]{nxt.id}[/bold]")
            stdout.print(f"  prompt:  {nxt.prompt}")
        else:
            stdout.print("  no exercises remaining (all passed)")

    _emit(payload, json_, render)


@app.command()
def status(json_: bool = typer.Option(False, "--json")) -> None:
    active = state_mod.active_arc()
    if active is None:
        payload = {"active": None}
        if json_:
            stdout.print_json(data=payload)
        else:
            stderr.print("[yellow]no active arc[/yellow]")
        raise typer.Exit(code=2)

    try:
        arc = get_arc(active.arc_name)
    except ArcError as e:
        raise _error(str(e), json_mode=json_)

    nxt = next_exercise(arc, active.passed)

    payload = {
        "active": active.arc_name,
        "passed": active.passed,
        "current_exercise": nxt.id if nxt else None,
        "prompt": nxt.prompt if nxt else None,
        "remaining": [e.id for e in arc.exercises if e.id not in set(active.passed)],
        "total": len(arc.exercises),
    }

    def render() -> None:
        stdout.print(f"[bold]{arc.name}[/bold] — {len(active.passed)}/{len(arc.exercises)} passed")
        if nxt:
            stdout.print(f"  next: [bold]{nxt.id}[/bold]")
            stdout.print(f"  prompt: {nxt.prompt}")
        else:
            stdout.print("  [green]all exercises passed — run `stack-quest complete`[/green]")

    _emit(payload, json_, render)


@app.command()
def check(
    exercise_id: Optional[str] = typer.Argument(None, metavar="[EXERCISE_ID]"),
    json_: bool = typer.Option(False, "--json"),
) -> None:
    active = state_mod.active_arc()
    if active is None:
        raise _error("no active arc; run `stack-quest start ARC_NAME` first", code=2, json_mode=json_)

    try:
        arc = get_arc(active.arc_name)
    except ArcError as e:
        raise _error(str(e), json_mode=json_)

    if exercise_id is None:
        nxt = next_exercise(arc, active.passed)
        if nxt is None:
            raise _error("no exercises remain", code=2, json_mode=json_)
        exercise_id = nxt.id

    try:
        result = run_check(arc, exercise_id)
    except ExerciseError as e:
        raise _error(str(e), code=2, json_mode=json_)

    if result.passed:
        state_mod.record_pass(arc.name, exercise_id)
        nxt = next_exercise(arc, active.passed + [exercise_id])
        state_mod.set_current_exercise(arc.name, nxt.id if nxt else None)

    payload = result.to_dict()
    payload["arc"] = arc.name

    def render() -> None:
        if result.passed:
            stdout.print(f"[green]PASS[/green] {exercise_id}")
            if result.stdout.strip():
                stdout.print(result.stdout.strip())
        else:
            stderr.print(f"[red]FAIL[/red] {exercise_id}")
            if result.stderr.strip():
                stderr.print(result.stderr.strip())

    _emit(payload, json_, render)
    if not result.passed:
        raise typer.Exit(code=1)


@app.command()
def hint(json_: bool = typer.Option(False, "--json")) -> None:
    active = state_mod.active_arc()
    if active is None:
        raise _error("no active arc", code=2, json_mode=json_)
    arc = get_arc(active.arc_name)
    nxt = next_exercise(arc, active.passed)
    if nxt is None:
        raise _error("no exercises remain", code=2, json_mode=json_)
    payload = {"exercise_id": nxt.id, "prompt": nxt.prompt}

    def render() -> None:
        stdout.print(f"[bold]{nxt.id}[/bold]")
        stdout.print(nxt.prompt)

    _emit(payload, json_, render)


@app.command()
def stop(json_: bool = typer.Option(False, "--json")) -> None:
    active = state_mod.active_arc()
    if active is None:
        raise _error("no active arc", code=2, json_mode=json_)
    arc = get_arc(active.arc_name)
    try:
        result = down(arc.stack_path())
    except StackError as e:
        raise _error(str(e), json_mode=json_)
    state_mod.set_inactive(arc.name)
    payload = {"arc": arc.name, "stopped": result.ok}

    def render() -> None:
        if result.ok:
            stdout.print(f"[green]stopped[/green] {arc.name}")
        else:
            stderr.print(f"[red]stop failed:[/red] {result.stderr.strip()}")

    _emit(payload, json_, render)
    if not result.ok:
        raise typer.Exit(code=1)


@app.command()
def reset(
    arc_name: str = typer.Argument(..., metavar="ARC_NAME"),
    json_: bool = typer.Option(False, "--json"),
) -> None:
    try:
        arc = get_arc(arc_name)
    except ArcError as e:
        raise _error(str(e), code=2, json_mode=json_)
    try:
        down(arc.stack_path(), volumes=True)
    except StackError:
        pass
    state_mod.reset_arc(arc.name)
    payload = {"arc": arc.name, "reset": True}

    def render() -> None:
        stdout.print(f"[green]reset[/green] {arc.name}")

    _emit(payload, json_, render)


# ---------- complete + portfolio ----------


@app.command()
def complete(
    arc_name: str = typer.Argument(..., metavar="ARC_NAME"),
    json_: bool = typer.Option(False, "--json"),
) -> None:
    """Emit the portfolio artifact and close beacon-tracked quests in code-daily."""
    try:
        arc = get_arc(arc_name)
    except ArcError as e:
        raise _error(str(e), code=2, json_mode=json_)

    st = state_mod.get_state(arc.name)
    passed = set(st.passed) if st else set()
    remaining = [e.id for e in arc.exercises if e.id not in passed]
    if remaining:
        raise _error(
            f"cannot complete: exercises remaining: {remaining}",
            code=1,
            json_mode=json_,
        )

    try:
        emit_result = emit(arc)
    except PortfolioError as e:
        raise _error(str(e), json_mode=json_)

    quest_results = [code_daily.complete_quest(q).to_dict() for q in arc.closes_quests]
    sv_scan = skillvault.scan(emit_result.emitted_to)

    payload = {
        "arc": arc.name,
        "portfolio": emit_result.to_dict(),
        "quests": quest_results,
        "skillvault": sv_scan,
    }

    def render() -> None:
        stdout.print(f"[green]complete[/green] {arc.name}")
        stdout.print(f"  portfolio: {emit_result.emitted_to}")
        for qr in quest_results:
            tag = "[green]ok[/green]" if qr["ok"] else "[yellow]dry-run[/yellow]"
            stdout.print(f"  quest {qr['quest']}: {tag} — {qr['message']}")
        if sv_scan is not None:
            stdout.print(f"  skillvault: {sv_scan}")

    _emit(payload, json_, render)


@portfolio_app.command("emit")
def portfolio_emit(
    arc_name: str = typer.Argument(..., metavar="ARC_NAME"),
    path: Optional[Path] = typer.Option(None, "--path", help="Override emit destination."),
    json_: bool = typer.Option(False, "--json"),
) -> None:
    try:
        arc = get_arc(arc_name)
    except ArcError as e:
        raise _error(str(e), code=2, json_mode=json_)
    try:
        result = emit(arc, override_path=path)
    except PortfolioError as e:
        raise _error(str(e), json_mode=json_)

    payload = result.to_dict()

    def render() -> None:
        stdout.print(f"[green]emitted[/green] {arc.name} → {result.emitted_to}")
        for f in result.files_written:
            stdout.print(f"  + {f}")

    _emit(payload, json_, render)


if __name__ == "__main__":  # pragma: no cover
    app()
