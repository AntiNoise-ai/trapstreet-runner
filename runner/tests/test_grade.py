import subprocess
import sys
from pathlib import Path

GRADE = Path(__file__).parent.parent / "grade.py"


def grade(pred: str, gold: str) -> tuple[int, str]:
    r = subprocess.run(
        [sys.executable, str(GRADE), pred, gold],
        capture_output=True, text=True
    )
    return r.returncode, r.stdout.strip()


def test_numeric_match_with_tolerance():
    rc, out = grade("$5466.31", "$5466.00")
    assert rc == 0
    assert "CORRECT" in out


def test_numeric_mismatch():
    rc, out = grade("100", "200")
    assert rc == 1
    assert "WRONG" in out


def test_string_match():
    rc, out = grade("yes", "yes")
    assert rc == 0


def test_empty_prediction():
    rc, out = grade("", "anything")
    assert rc == 1
