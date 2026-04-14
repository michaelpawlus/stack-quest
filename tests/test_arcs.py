from pathlib import Path

import pytest

from stack_quest.arcs import ArcError, get_arc, list_arcs, load_arc


def test_list_arcs_includes_streaming():
    arcs = list_arcs()
    names = [a.name for a in arcs]
    assert "streaming-arc" in names


def test_streaming_arc_shape():
    arc = get_arc("streaming-arc")
    assert arc.closes_quests == ["kafka", "flink", "airflow"]
    assert len(arc.exercises) == 3
    assert arc.exercises[0].id == "01-ingest"
    assert arc.stack_path().exists()
    assert arc.check_path("01-ingest").exists()


def test_load_arc_validates(tmp_path: Path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("name: bad\n")
    with pytest.raises(ArcError):
        load_arc(bad)


def test_unknown_arc_raises():
    with pytest.raises(ArcError):
        get_arc("does-not-exist")
