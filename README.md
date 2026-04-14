# stack-quest

Turn beacon skill-gap quests into weekend-sized learning arcs that emit
portfolio artifacts you can link in an interview.

## The gap this closes

Most "learn X" learning loops end with a vague feeling of competence and no
linkable demo. stack-quest enforces the *shape* of the learning so that every
arc you finish ends with:

- A working docker-compose sandbox you spun up yourself
- A handful of exercises with verifiable output
- A scaffolded portfolio repo (README + architecture diagram + walkthrough script)

## Install (dev)

```bash
pip install -e .
stack-quest --version
```

## Quick start

```bash
stack-quest arcs list
stack-quest arcs show streaming-arc

stack-quest start streaming-arc
stack-quest hint
# ...do the exercise...
stack-quest check 01-ingest
stack-quest status
stack-quest stop
```

When all exercises pass:

```bash
stack-quest complete streaming-arc
# emits ../stack-quest-streaming-demo and (if installed) closes beacon quests
```

## How it composes with the rest of the toolchain

- **beacon** — `arcs suggest` reads `beacon gaps list --json` to rank arcs by
  how many real job-listing-derived gaps they close.
- **code-daily** — `complete` calls `code-daily quests complete <id>` for each
  quest the arc closes.
- **skillvault** — `complete` runs `skillvault scan` against the emitted
  portfolio repo to verify it's agent-ready.

All three are optional. stack-quest degrades gracefully if they're not on PATH.

See [CLAUDE.md](./CLAUDE.md) for the full CLI surface and project conventions.
