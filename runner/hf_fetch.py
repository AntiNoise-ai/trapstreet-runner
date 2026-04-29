"""Fetch trapstreet case bundles from HuggingFace Hub (or any HTTP/file URL base)."""
from __future__ import annotations

import json
import urllib.parse
import urllib.request
from pathlib import Path


def _read_url(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=30) as r:
        return r.read()


def fetch_case_to_scratch(case_id: str, base_url: str, scratch_dir: Path) -> dict:
    """Download a case's task.json + docs/* to a scratch dir.

    Returns the parsed task.json dict.
    """
    scratch_dir = Path(scratch_dir)
    docs_dir = scratch_dir / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)

    base = base_url.rstrip("/")
    task_url = f"{base}/cases/{case_id}/task.json"
    task_bytes = _read_url(task_url)
    task = json.loads(task_bytes)

    (scratch_dir / "task.json").write_bytes(task_bytes)

    for fname in task["doc_files"]:
        doc_url = f"{base}/cases/{case_id}/docs/{urllib.parse.quote(fname)}"
        (docs_dir / fname).write_bytes(_read_url(doc_url))

    return task
