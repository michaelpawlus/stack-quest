# CLAUDE.md — {{ arc_name }} demo

This repo was emitted by `stack-quest` as the portfolio artifact for the
`{{ arc_name }}` learning arc.

## Closes quests

{% for q in closes_quests -%}
- {{ q }}
{% endfor %}

## How to run

`docker compose up -d` brings up the local stack. See README.md for exercise
scripts and the architecture diagram.

## Agent guidance

When asked to extend this demo, prefer extending an existing exercise script
over creating new ones — the README architecture diagram and walkthrough
script reference the original three-stage shape.
