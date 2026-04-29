import json
import subprocess
import sys
from pathlib import Path

WORKSPACE = Path(__file__).parent.parent.parent
RUNNER = WORKSPACE / "runner/trapstreet_eval.py"
ECHO_AGENT = WORKSPACE / "runner/echo_agent.py"


def setup_local_dataset_v2(tmp_path: Path) -> str:
    """Multi-question v2 schema."""
    root = tmp_path / "ds"
    case_dir = root / "cases/financebench-1"
    docs = case_dir / "docs"
    docs.mkdir(parents=True)
    (case_dir / "task.json").write_text(json.dumps({
        "id": "financebench-1",
        "type": "financebench-multi-v0",
        "version": 2,
        "doc_files": ["doc_a.txt"],
        "questions": [
            {"id": "q1", "question": "Q1?", "gold": "$5466.00"},
            {"id": "q2", "question": "Q2?", "gold": "100"},
        ],
    }))
    (docs / "doc_a.txt").write_text("dummy doc")
    return f"file://{root}"


def setup_local_dataset_v1(tmp_path: Path) -> str:
    """Single-question v1 schema (back-compat)."""
    root = tmp_path / "ds"
    case_dir = root / "cases/financebench-1"
    docs = case_dir / "docs"
    docs.mkdir(parents=True)
    (case_dir / "task.json").write_text(json.dumps({
        "id": "financebench-1",
        "question": "What is the answer?",
        "gold": "$5466.00",
        "doc_files": ["doc_a.txt"],
        "type": "test",
        "version": 1,
    }))
    (docs / "doc_a.txt").write_text("dummy doc")
    return f"file://{root}"


def test_runner_v2_partial_score(tmp_path):
    """Echo agent always says $5466.31, so it gets q1 right and q2 wrong → 1/2."""
    base = setup_local_dataset_v2(tmp_path)
    r = subprocess.run(
        [sys.executable, str(RUNNER), "financebench-1",
         "--agent", str(ECHO_AGENT),
         "--no-submit",
         "--hf-base", base],
        capture_output=True, text=True, timeout=60,
        cwd=WORKSPACE,
    )
    assert r.returncode == 0, r.stderr
    assert "Score:   1/2" in r.stdout
    assert "✅" in r.stdout and "❌" in r.stdout


def test_runner_v1_back_compat(tmp_path):
    """Old single-question schema still works."""
    base = setup_local_dataset_v1(tmp_path)
    r = subprocess.run(
        [sys.executable, str(RUNNER), "financebench-1",
         "--agent", str(ECHO_AGENT),
         "--no-submit",
         "--hf-base", base],
        capture_output=True, text=True, timeout=60,
        cwd=WORKSPACE,
    )
    assert r.returncode == 0, r.stderr
    assert "Score:   1/1" in r.stdout


def test_runner_with_failing_agent(tmp_path):
    base = setup_local_dataset_v2(tmp_path)
    bad_agent = tmp_path / "bad.py"
    bad_agent.write_text("import sys; sys.exit(7)")
    r = subprocess.run(
        [sys.executable, str(RUNNER), "financebench-1",
         "--agent", f"{sys.executable} {bad_agent}",
         "--no-submit",
         "--hf-base", base],
        capture_output=True, text=True, timeout=60,
        cwd=WORKSPACE,
    )
    assert r.returncode != 0
    assert "agent" in r.stderr.lower() or "exit" in r.stderr.lower()
