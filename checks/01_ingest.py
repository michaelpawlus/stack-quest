#!/usr/bin/env python3
"""Check exercise 01-ingest: at least one message exists on the `news` topic.

Uses the Redpanda Admin/Pandaproxy HTTP API so this script has no Python
client dependency. Exits 0 on pass, 1 on fail. Writes diagnostics to stderr.
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request

PANDAPROXY = "http://localhost:8082"
TOPIC = "news"
MIN_MESSAGES = 1


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


def main() -> int:
    try:
        topics = _http_get_json(f"{PANDAPROXY}/topics", "application/vnd.kafka.v2+json")
    except urllib.error.URLError as e:
        print(f"could not reach pandaproxy at {PANDAPROXY}: {e}", file=sys.stderr)
        print("hint: is the streaming stack running? `stack-quest start streaming-arc`", file=sys.stderr)
        return 1

    if not isinstance(topics, list) or TOPIC not in topics:
        print(f"topic '{TOPIC}' not found. existing topics: {topics}", file=sys.stderr)
        return 1

    consumer_group = "stack-quest-check"
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
            req = urllib.request.Request(instance_url, method="DELETE",
                                         headers={"Accept": "application/vnd.kafka.v2+json"})
            urllib.request.urlopen(req, timeout=5)
        except Exception:
            pass

    count = len(records) if isinstance(records, list) else 0
    if count < MIN_MESSAGES:
        print(f"found {count} messages on '{TOPIC}', need at least {MIN_MESSAGES}", file=sys.stderr)
        return 1

    print(f"OK: {count} message(s) on '{TOPIC}'")
    return 0


if __name__ == "__main__":
    sys.exit(main())
