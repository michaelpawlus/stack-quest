"""Unit tests for checks/03_orchestrate.py.

Mocks at the urllib.request.urlopen boundary so no Airflow is required.
"""

from __future__ import annotations

import importlib.util
import io
import json
import sys
import urllib.error
from pathlib import Path
from typing import Callable

import pytest

CHECK_PATH = Path(__file__).resolve().parents[1] / "checks" / "03_orchestrate.py"


def _load_check_module():
    spec = importlib.util.spec_from_file_location("check_03_orchestrate", CHECK_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def check_mod(monkeypatch):
    monkeypatch.delenv("STACK_QUEST_DAG_ID", raising=False)
    return _load_check_module()


class _FakeResp:
    def __init__(self, body: bytes, status: int = 200):
        self._body = body
        self._status = status

    def read(self):
        return self._body

    def getcode(self):
        return self._status

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def _http_error(url: str, code: int, reason: str) -> urllib.error.HTTPError:
    return urllib.error.HTTPError(url, code, reason, hdrs=None, fp=io.BytesIO(b""))


def _route(*, dag: dict | Exception | None = None,
           runs: dict | Exception | None = None) -> Callable:
    """Return a fake urlopen that dispatches by URL path."""
    def fake_urlopen(req, timeout=None):
        url = req.full_url
        if "/dagRuns" in url:
            if isinstance(runs, Exception):
                raise runs
            return _FakeResp(json.dumps(runs or {}).encode())
        if "/dags/" in url:
            if isinstance(dag, Exception):
                raise dag
            return _FakeResp(json.dumps(dag or {}).encode())
        raise AssertionError(f"unexpected request: {url}")

    return fake_urlopen


def test_success(check_mod, monkeypatch, capsys):
    monkeypatch.setattr(
        "urllib.request.urlopen",
        _route(
            dag={"dag_id": "stack_quest_ingest", "is_paused": False},
            runs={"dag_runs": [{"dag_run_id": "r1", "state": "success"}],
                  "total_entries": 1},
        ),
    )
    assert check_mod.main() == 0
    out = capsys.readouterr().out
    assert "OK" in out
    assert "stack_quest_ingest" in out


def test_custom_dag_id_via_env(monkeypatch, capsys):
    monkeypatch.setenv("STACK_QUEST_DAG_ID", "my_custom_dag")
    mod = _load_check_module()

    captured_urls = []

    def fake_urlopen(req, timeout=None):
        captured_urls.append(req.full_url)
        if "/dagRuns" in req.full_url:
            return _FakeResp(
                json.dumps({"dag_runs": [{"state": "success"}],
                            "total_entries": 1}).encode()
            )
        return _FakeResp(json.dumps({"is_paused": False}).encode())

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    assert mod.main() == 0
    assert any("/dags/my_custom_dag" in u for u in captured_urls)


def test_missing_dag(check_mod, monkeypatch, capsys):
    monkeypatch.setattr(
        "urllib.request.urlopen",
        _route(dag=_http_error("http://x/dags/stack_quest_ingest", 404, "Not Found")),
    )
    assert check_mod.main() == 1
    err = capsys.readouterr().err
    assert "condition 1 failed" in err
    assert "not found" in err
    assert "STACK_QUEST_DAG_ID" in err


def test_paused_dag(check_mod, monkeypatch, capsys):
    monkeypatch.setattr(
        "urllib.request.urlopen",
        _route(dag={"dag_id": "stack_quest_ingest", "is_paused": True}),
    )
    assert check_mod.main() == 1
    err = capsys.readouterr().err
    assert "condition 1 failed" in err
    assert "paused" in err
    assert "airflow dags unpause" in err


def test_no_successful_runs(check_mod, monkeypatch, capsys):
    monkeypatch.setattr(
        "urllib.request.urlopen",
        _route(
            dag={"dag_id": "stack_quest_ingest", "is_paused": False},
            runs={"dag_runs": [], "total_entries": 0},
        ),
    )
    assert check_mod.main() == 1
    err = capsys.readouterr().err
    assert "condition 2 failed" in err
    assert "no successful runs" in err
    assert "airflow dags trigger" in err


def test_auth_failure(check_mod, monkeypatch, capsys):
    monkeypatch.setattr(
        "urllib.request.urlopen",
        _route(dag=_http_error("http://x/dags/stack_quest_ingest", 401, "Unauthorized")),
    )
    assert check_mod.main() == 1
    err = capsys.readouterr().err
    assert "401" in err
    assert "airflow:airflow" in err
    assert "Traceback" not in err


def test_broker_down(check_mod, monkeypatch, capsys):
    monkeypatch.setattr(
        "urllib.request.urlopen",
        _route(dag=urllib.error.URLError("connection refused")),
    )
    assert check_mod.main() == 1
    err = capsys.readouterr().err
    assert "could not reach Airflow" in err
    assert "stack-quest start streaming-arc" in err


def test_smoke_clean_failure_when_nothing_running():
    """Run as subprocess with no Airflow; must exit 1 cleanly with stderr."""
    import subprocess

    proc = subprocess.run(
        [sys.executable, str(CHECK_PATH)],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert proc.returncode == 1
    assert "could not reach Airflow" in proc.stderr or "condition" in proc.stderr
    assert "Traceback" not in proc.stderr
