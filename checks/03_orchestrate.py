#!/usr/bin/env python3
"""Check exercise 03-orchestrate: Airflow DAG exists, unpaused, has a success run.

Hits the Airflow REST API at http://localhost:8081/api/v1/ with stdlib urllib +
Basic auth (`airflow:airflow`). The DAG id is read from `STACK_QUEST_DAG_ID`
(default `stack_quest_ingest`).

Pass conditions (all must hold):
  1. GET /dags/{dag_id} returns 200 and `is_paused == false`.
  2. GET /dags/{dag_id}/dagRuns?state=success&limit=1 returns >=1 run.

Exits 0 on pass, 1 on fail. Diagnostics go to stderr.
"""

from __future__ import annotations

import base64
import json
import os
import sys
import urllib.error
import urllib.request

AIRFLOW_BASE = "http://localhost:8081/api/v1"
AIRFLOW_USER = "airflow"
AIRFLOW_PASSWORD = "airflow"
DAG_ID = os.environ.get("STACK_QUEST_DAG_ID", "stack_quest_ingest")


def _auth_header() -> str:
    raw = f"{AIRFLOW_USER}:{AIRFLOW_PASSWORD}".encode("utf-8")
    return "Basic " + base64.b64encode(raw).decode("ascii")


def _http_get_json(url: str) -> tuple[int, object]:
    req = urllib.request.Request(
        url,
        headers={"Authorization": _auth_header(), "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        body = resp.read()
        return resp.getcode(), (json.loads(body) if body else None)


def _print_unreachable(e: Exception) -> None:
    print(f"could not reach Airflow at {AIRFLOW_BASE}: {e}", file=sys.stderr)
    print(
        "hint: is the streaming stack running? `stack-quest start streaming-arc` "
        "now boots Airflow standalone alongside Redpanda.",
        file=sys.stderr,
    )


def _print_auth_failure() -> None:
    print(
        "Airflow returned 401: auth wrong, expected airflow:airflow basic auth.",
        file=sys.stderr,
    )


def main() -> int:
    dag_url = f"{AIRFLOW_BASE}/dags/{DAG_ID}"
    runs_url = (
        f"{AIRFLOW_BASE}/dags/{DAG_ID}/dagRuns?state=success&limit=1"
    )

    try:
        status, dag = _http_get_json(dag_url)
    except urllib.error.HTTPError as e:
        if e.code == 401:
            _print_auth_failure()
            return 1
        if e.code == 404:
            print(
                f"condition 1 failed: DAG '{DAG_ID}' not found. "
                "Hint: `airflow dags list` to inspect; place the DAG in "
                "stacks/streaming/dags/. Override the id with STACK_QUEST_DAG_ID.",
                file=sys.stderr,
            )
            return 1
        print(f"condition 1 failed: GET {dag_url} -> {e.code} {e.reason}", file=sys.stderr)
        return 1
    except urllib.error.URLError as e:
        _print_unreachable(e)
        return 1

    if status != 200 or not isinstance(dag, dict):
        print(
            f"condition 1 failed: unexpected response from {dag_url}: status={status} "
            f"body={dag!r}",
            file=sys.stderr,
        )
        return 1

    if dag.get("is_paused", True):
        print(
            f"condition 1 failed: DAG '{DAG_ID}' is paused. "
            f"Hint: `airflow dags unpause {DAG_ID}` (or toggle in the UI).",
            file=sys.stderr,
        )
        return 1

    try:
        status, runs = _http_get_json(runs_url)
    except urllib.error.HTTPError as e:
        if e.code == 401:
            _print_auth_failure()
            return 1
        print(
            f"condition 2 failed: GET {runs_url} -> {e.code} {e.reason}",
            file=sys.stderr,
        )
        return 1
    except urllib.error.URLError as e:
        _print_unreachable(e)
        return 1

    dag_runs = runs.get("dag_runs") if isinstance(runs, dict) else None
    total = runs.get("total_entries") if isinstance(runs, dict) else None
    count = len(dag_runs) if isinstance(dag_runs, list) else 0
    if count < 1:
        print(
            f"condition 2 failed: no successful runs for DAG '{DAG_ID}' "
            f"(total_entries={total}). Hint: `airflow dags trigger {DAG_ID}`.",
            file=sys.stderr,
        )
        return 1

    print(f"OK: DAG '{DAG_ID}' is unpaused with at least 1 successful run")
    return 0


if __name__ == "__main__":
    sys.exit(main())
