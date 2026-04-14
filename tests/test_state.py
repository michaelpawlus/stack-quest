import os

import pytest

from stack_quest import state as state_mod


@pytest.fixture(autouse=True)
def _isolated_state(tmp_path, monkeypatch):
    monkeypatch.setenv("STACK_QUEST_STATE_DIR", str(tmp_path))
    yield


def test_no_active_arc_initially():
    assert state_mod.active_arc() is None


def test_set_and_get_active():
    state_mod.set_active("streaming-arc", "01-ingest")
    s = state_mod.active_arc()
    assert s is not None
    assert s.arc_name == "streaming-arc"
    assert s.current_exercise == "01-ingest"
    assert s.passed == []


def test_record_pass_advances():
    state_mod.set_active("streaming-arc", "01-ingest")
    state_mod.record_pass("streaming-arc", "01-ingest")
    s = state_mod.get_state("streaming-arc")
    assert s.passed == ["01-ingest"]


def test_set_active_deactivates_others():
    state_mod.set_active("a", None)
    state_mod.set_active("b", None)
    s = state_mod.active_arc()
    assert s.arc_name == "b"


def test_reset_arc_clears_state():
    state_mod.set_active("streaming-arc", "01-ingest")
    state_mod.record_pass("streaming-arc", "01-ingest")
    state_mod.reset_arc("streaming-arc")
    assert state_mod.get_state("streaming-arc") is None
