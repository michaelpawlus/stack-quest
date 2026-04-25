"""Unit tests for checks/02_transform.py.

Mocks at the urllib.request.urlopen boundary so no broker is required.
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

CHECK_PATH = Path(__file__).resolve().parents[1] / "checks" / "02_transform.py"


def _load_check_module():
    spec = importlib.util.spec_from_file_location("check_02_transform", CHECK_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def check_mod():
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


def _route(records: list[dict] | None = None,
           topics: list[str] | None = None,
           consumer_create_status: int | None = None,
           records_error: Exception | None = None,
           topics_error: Exception | None = None) -> Callable:
    """Return a fake urlopen that dispatches by URL path."""
    if topics is None:
        topics = ["news", "news_counts"]

    deletions = []

    def fake_urlopen(req, timeout=None):
        url = req.full_url if hasattr(req, "full_url") else req
        method = req.get_method() if hasattr(req, "get_method") else "GET"

        if url.endswith("/topics"):
            if topics_error is not None:
                raise topics_error
            return _FakeResp(json.dumps(topics).encode())

        if "/consumers/" in url and "/instances/" not in url and method == "POST":
            if consumer_create_status == 409:
                raise urllib.error.HTTPError(
                    url, 409, "Conflict", hdrs=None, fp=io.BytesIO(b"")
                )
            return _FakeResp(json.dumps({"instance_id": "checker"}).encode())

        if url.endswith("/subscription") and method == "POST":
            return _FakeResp(b"{}")

        if "/records" in url and method == "GET":
            if records_error is not None:
                raise records_error
            return _FakeResp(json.dumps(records or []).encode())

        if method == "DELETE":
            deletions.append(url)
            return _FakeResp(b"")

        raise AssertionError(f"unexpected request: {method} {url}")

    fake_urlopen.deletions = deletions
    return fake_urlopen


def test_success_with_count_field(check_mod, monkeypatch, capsys):
    records = [
        {"topic": "news_counts", "key": None,
         "value": {"source": "hn", "count": 7}, "partition": 0, "offset": 0},
        {"topic": "news_counts", "key": None,
         "value": {"source": "lobsters", "count": 3}, "partition": 0, "offset": 1},
    ]
    monkeypatch.setattr("urllib.request.urlopen", _route(records=records))
    assert check_mod.main() == 0
    out = capsys.readouterr().out
    assert "OK: 2 message(s) on 'news_counts'" in out
    assert "count field: 'count'" in out


def test_success_with_n_field(check_mod, monkeypatch, capsys):
    records = [
        {"value": {"source": "hn", "n": 12}},
    ]
    monkeypatch.setattr("urllib.request.urlopen", _route(records=records))
    assert check_mod.main() == 0
    assert "count field: 'n'" in capsys.readouterr().out


def test_success_with_value_field(check_mod, monkeypatch, capsys):
    records = [
        {"value": {"source": "hn", "value": 42}},
    ]
    monkeypatch.setattr("urllib.request.urlopen", _route(records=records))
    assert check_mod.main() == 0
    assert "count field: 'value'" in capsys.readouterr().out


def test_topic_missing(check_mod, monkeypatch, capsys):
    monkeypatch.setattr(
        "urllib.request.urlopen", _route(topics=["news"], records=[])
    )
    assert check_mod.main() == 1
    err = capsys.readouterr().err
    assert "topic 'news_counts' not found" in err
    assert "condition 1" in err


def test_no_messages(check_mod, monkeypatch, capsys):
    monkeypatch.setattr("urllib.request.urlopen", _route(records=[]))
    assert check_mod.main() == 1
    err = capsys.readouterr().err
    assert "condition 2 failed" in err
    assert "found 0 message(s)" in err


def test_message_missing_source(check_mod, monkeypatch, capsys):
    records = [{"value": {"count": 5}}]
    monkeypatch.setattr("urllib.request.urlopen", _route(records=records))
    assert check_mod.main() == 1
    err = capsys.readouterr().err
    assert "condition 3 failed" in err
    assert "source" in err


def test_message_missing_count_field(check_mod, monkeypatch, capsys):
    records = [{"value": {"source": "hn", "qty": 1}}]
    monkeypatch.setattr("urllib.request.urlopen", _route(records=records))
    assert check_mod.main() == 1
    err = capsys.readouterr().err
    assert "condition 3 failed" in err
    assert "numeric count field" in err


def test_broker_unreachable(check_mod, monkeypatch, capsys):
    err = urllib.error.URLError("connection refused")
    monkeypatch.setattr(
        "urllib.request.urlopen", _route(topics_error=err)
    )
    assert check_mod.main() == 1
    captured = capsys.readouterr().err
    assert "could not reach pandaproxy" in captured
    assert "stacks/streaming/docker-compose.yml" in captured


def test_consumer_already_exists_is_ok(check_mod, monkeypatch, capsys):
    records = [{"value": {"source": "hn", "count": 1}}]
    monkeypatch.setattr(
        "urllib.request.urlopen",
        _route(records=records, consumer_create_status=409),
    )
    assert check_mod.main() == 0


def test_smoke_clean_failure_when_nothing_running():
    """Run as subprocess with no broker; must exit 1 cleanly with stderr."""
    import subprocess

    proc = subprocess.run(
        [sys.executable, str(CHECK_PATH)],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert proc.returncode == 1
    assert "could not reach pandaproxy" in proc.stderr or "topic" in proc.stderr
    assert "Traceback" not in proc.stderr
