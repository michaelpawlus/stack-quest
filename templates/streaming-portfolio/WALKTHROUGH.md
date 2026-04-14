# 5-minute walkthrough script — {{ arc_name }}

Aim: 5 minutes. Camera on the editor + a terminal pane.

1. **Why this exists (30s)** — "I had skill gaps in {{ closes_quests | join(", ") }}.
   Instead of running tutorials, I built a sandbox arc and emitted this repo."
2. **Architecture (60s)** — Walk through the Mermaid diagram in the README.
3. **Spin it up (60s)** — `docker compose up -d`, show the Redpanda console.
4. **Run the producer (60s)** — Show a message landing on `news`.
5. **Run the transform (60s)** — Show counts landing on `news_counts`.
6. **Wrap (30s)** — Link back to stack-quest, mention what's next.
