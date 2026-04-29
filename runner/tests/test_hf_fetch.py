import json
from pathlib import Path
import pytest

from runner.hf_fetch import fetch_case_to_scratch


@pytest.fixture
def fake_dataset(tmp_path):
    root = tmp_path / "ds"
    case_dir = root / "cases/financebench-1"
    docs = case_dir / "docs"
    docs.mkdir(parents=True)
    (case_dir / "task.json").write_text(json.dumps({
        "id": "financebench-1",
        "question": "test question",
        "gold": "42",
        "doc_files": ["doc_a.txt", "doc_b.txt"],
        "type": "test",
        "version": 1
    }))
    (docs / "doc_a.txt").write_text("alpha content")
    (docs / "doc_b.txt").write_text("beta content")
    return f"file://{root}"


def test_fetch_case_to_scratch_writes_all_files(fake_dataset, tmp_path):
    scratch = tmp_path / "scratch"
    task = fetch_case_to_scratch("financebench-1", fake_dataset, scratch)

    assert task["id"] == "financebench-1"
    assert task["gold"] == "42"
    assert (scratch / "docs/doc_a.txt").read_text() == "alpha content"
    assert (scratch / "docs/doc_b.txt").read_text() == "beta content"


def test_fetch_case_missing_raises(tmp_path):
    base = f"file://{tmp_path}"
    with pytest.raises(Exception):
        fetch_case_to_scratch("nope", base, tmp_path / "scratch")
