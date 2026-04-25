# CLAUDE.md — stack-quest

## What this is

stack-quest turns the beacon_gap backlog into *learning arcs* — curated
groupings of related skills that share a docker-compose sandbox and produce a
single portfolio artifact when completed. Each arc is weekend-sized and ends
with a GitHub repo you can point to in an interview.

## Personal-use pattern

Per the global CLI-by-default convention, stack-quest is a tool for the agent.
The CLI collects state and verifies exercise output; **Claude Code in-session
is the intelligence layer** that helps the user actually do the exercises.

There is intentionally no autonomous mode — this stays Claude-Code-in-the-loop.

## CLI surface

All read commands support `--json` and follow the global agent-friendly
interface standards (exit 0 success, 1 error, 2 not found).

```
stack-quest arcs list [--json]
stack-quest arcs show ARC_NAME [--json]
stack-quest arcs suggest [--json]      # cross-references beacon gaps with arcs

stack-quest start ARC_NAME             # docker compose up + first exercise
stack-quest status [--json]
stack-quest check [EXERCISE_ID] [--json]
stack-quest hint [--json]
stack-quest stop [--json]
stack-quest reset ARC_NAME [--json]

stack-quest complete ARC_NAME [--json] # emit portfolio + close beacon quests
stack-quest portfolio emit ARC_NAME [--path PATH] [--json]
```

## Layout

- `arcs/*.yaml` — arc definitions (closes_quests, stack path, exercises, portfolio)
- `stacks/<arc>/docker-compose.yml` — sandbox per arc
- `checks/<exercise>.py` — Python check scripts; exit 0 = pass, 1 = fail
- `templates/<arc>-portfolio/` — Jinja2 template tree for the portfolio repo
- `src/stack_quest/` — CLI, arc loader, state, integrations
- State lives at `~/.local/share/stack-quest/state.db` (override with `STACK_QUEST_STATE_DIR`)

## Integrations

- `beacon` — `beacon gaps list --json` for `arcs suggest`. Optional; degrades to static.
- `code-daily` — `code-daily quests complete <id> --json` from `complete`. Optional; dry-run otherwise.
- `skillvault` — `skillvault scan PATH --json` to verify the emitted portfolio repo. Optional.

If any of those CLIs aren't on PATH, stack-quest still works.

## MVP status

The streaming arc has three working exercises with real checks:
`01-ingest` and `02-transform` hit Redpanda's Pandaproxy HTTP API,
`03-orchestrate` hits the Airflow REST API at localhost:8081. The
portfolio template emits a README, CLAUDE.md, and WALKTHROUGH.md.

Exercise 03 reads its DAG id from `STACK_QUEST_DAG_ID`
(default: `stack_quest_ingest`).
