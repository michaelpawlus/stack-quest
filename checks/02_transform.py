#!/usr/bin/env python3
"""Check exercise 02-transform: per-source counts on `news_counts` topic.

Verifies that:
1. Topic `news_counts` exists in Pandaproxy.
2. At least one message can be consumed from it.
3. Each consumed message parses as JSON with a `source` field plus a numeric
   count field — accepted under any of `count`, `n`, or `value`.

Pure stdlib + urllib (mirrors `01_ingest.py`) — no Kafka client deps.
Exits 0 on pass, 1 on fail. Diagnostics go to stderr.
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request

PANDAPROXY = "http://localhost:8082"
TOPIC = "news_counts"
MIN_MESSAGES = 1
COUNT_FIELDS = ("count", "n", "value")
COMPOSE_HINT = "stacks/streaming/docker-compose.yml"


def _http_get_json(url: str, accept: str) -> object:
    req = urllib.request.Request(url, headers={"Accept": accept})
    with urllib.request.urlopen(req, timeout=5) as resp:
        body = resp.read()
    return json.loads(body) if body else None


def _http_post_json(url: str, payload: dict, content_type: str, accept: str) -> object:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": content_type, "Accept": accept},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        return json.loads(resp.read())


def _find_count_field(record: dict) -> tuple[str, float | int] | None:
    for field in COUNT_FIELDS:
        if field in record and isinstance(record[field], (int, float)) and not isinstance(
            record[field], bool
        ):
            return field, record[field]
    return None


def main() -> int:
    try:
        topics = _http_get_json(f"{PANDAPROXY}/topics", "application/vnd.kafka.v2+json")
    except urllib.error.URLError as e:
        print(f"could not reach pandaproxy at {PANDAPROXY}: {e}", file=sys.stderr)
        print(
            f"hint: is the streaming stack running? see {COMPOSE_HINT} or run "
            "`stack-quest start streaming-arc`",
            file=sys.stderr,
        )
        return 1

    if not isinstance(topics, list) or TOPIC not in topics:
        print(f"topic '{TOPIC}' not found. existing topics: {topics}", file=sys.stderr)
        print(
            "condition 1 failed: produce per-source counts to a `news_counts` topic.",
            file=sys.stderr,
        )
        return 1

    consumer_group = "stack-quest-check-02"
    consumer_name = "checker"
    consumer_url = f"{PANDAPROXY}/consumers/{consumer_group}"
    instance_url = f"{consumer_url}/instances/{consumer_name}"

    try:
        _http_post_json(
            consumer_url,
            {
                "name": consumer_name,
                "format": "json",
                "auto.offset.reset": "earliest",
                "auto.commit.enable": "false",
            },
            content_type="application/vnd.kafka.v2+json",
            accept="application/vnd.kafka.v2+json",
        )
    except urllib.error.HTTPError as e:
        if e.code != 409:
            print(f"failed to create consumer: {e}", file=sys.stderr)
            return 1

    try:
        _http_post_json(
            f"{instance_url}/subscription",
            {"topics": [TOPIC]},
            content_type="application/vnd.kafka.v2+json",
            accept="application/vnd.kafka.v2+json",
        )

        records_url = f"{instance_url}/records?timeout=2000&max_bytes=10000"
        req = urllib.request.Request(
            records_url, headers={"Accept": "application/vnd.kafka.json.v2+json"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            records = json.loads(resp.read())
    finally:
        try:
            req = urllib.request.Request(
                instance_url,
                method="DELETE",
                headers={"Accept": "application/vnd.kafka.v2+json"},
            )
            urllib.request.urlopen(req, timeout=5)
        except Exception:
            pass

    if not isinstance(records, list) or len(records) < MIN_MESSAGES:
        observed = len(records) if isinstance(records, list) else 0
        print(
            f"condition 2 failed: found {observed} message(s) on '{TOPIC}', "
            f"need at least {MIN_MESSAGES}",
            file=sys.stderr,
        )
        return 1

    # Pandaproxy json format puts the deserialized message under `value`.
    found_field: str | None = None
    for rec in records:
        value = rec.get("value") if isinstance(rec, dict) else None
        if not isinstance(value, dict):
            print(
                f"condition 3 failed: message value is not a JSON object: {value!r}",
                file=sys.stderr,
            )
            return 1
        if "source" not in value:
            print(
                f"condition 3 failed: message missing `source` field: {value!r}",
                file=sys.stderr,
            )
            return 1
        match = _find_count_field(value)
        if match is None:
            print(
                "condition 3 failed: message has no numeric count field. "
                f"Expected one of {COUNT_FIELDS}, got keys: {sorted(value.keys())}",
                file=sys.stderr,
            )
            return 1
        if found_field is None:
            found_field = match[0]

    print(f"OK: {len(records)} message(s) on '{TOPIC}'; count field: '{found_field}'")
    return 0


if __name__ == "__main__":
    sys.exit(main())
