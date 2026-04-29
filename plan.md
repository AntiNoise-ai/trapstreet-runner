# Trapstreet Agent Eval v0.1 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a working BYO-agent eval demo for trapstreet.run by 2026-04-30: one agent runs against one HF-hosted FinanceBench task, gets graded, submits to a public Supabase-backed leaderboard.

**Architecture:** Python single-file runner (`trapstreet_eval.py`) invokes an agent subprocess per a fixed contract. Cases live as JSON+text files on a public HuggingFace dataset. Submissions land in Supabase via REST. Existing GH Pages site at `apps/web` renders the leaderboard via JS fetch from Supabase.

**Tech Stack:** Python 3.11+, smolagents (with litellm extra), anthropic SDK, requests; Supabase (Postgres + REST + RLS); HuggingFace Hub (dataset); Next.js 15 / GH Pages (existing).

**Reference docs:**
- Spec: `/Users/zhengruqi/Documents/Projects/trapstreet-agent-eval-v0.1/spec.md`
- Existing skill (source for grade.py + question texts): `~/.claude/skills/trapstreet-eval/`
- Existing web app: `/Users/zhengruqi/Documents/Projects/Collaborating/trapstreet/apps/web/`

**Workspace:** `/Users/zhengruqi/Documents/Projects/trapstreet-agent-eval-v0.1/`

---

## Execution phases

| Phase | Blocker | Tasks |
|---|---|---|
| **1. Local code & cases** | None — pure local work | Tasks 1–11 |
| **2. External setup** | User must create HF dataset + Supabase project | Tasks 12–16 |
| **3. Web integration** | Phase 2 done | Tasks 17–19 |
| **4. Demo prep** | Phases 1–3 done | Tasks 20–21 |

**Auto-mode execution flow:** plow through Phase 1, then pause for user to provide HF dataset URL and Supabase URL/key, then resume.

---

## File structure to create

```
trapstreet-agent-eval-v0.1/
├── spec.md                              (already exists)
├── plan.md                              (this file)
├── README.md                            (workspace overview)
├── requirements.txt                     (python deps)
├── .gitignore
├── .env.example                         (env var template)
├── runner/
│   ├── __init__.py
│   ├── trapstreet_eval.py               (main CLI runner)
│   ├── grade.py                         (copied from existing skill)
│   ├── hf_fetch.py                      (HF dataset fetcher)
│   ├── supabase_client.py               (POST to Supabase)
│   ├── echo_agent.py                    (test fixture — agent that echoes input)
│   └── tests/
│       ├── test_grade.py
│       ├── test_hf_fetch.py
│       └── test_runner.py
├── agent/
│   ├── claude_finance.py                (hand-rolled fallback agent)
│   └── smolagents_finance.py            (smolagents primary agent)
├── case/
│   └── financebench-1/
│       ├── task.json
│       └── docs/
│           ├── doc_a.txt                (Netflix 2017 10-K — the answer)
│           ├── doc_b.txt                (AES 2022 10-K — distractor)
│           ├── doc_c.txt                (3M 2018 10-K — distractor)
│           ├── doc_d.txt                (Walmart 2018 10-K — distractor)
│           └── doc_e.txt                (Block 2016 10-K — distractor)
├── case/
│   └── index.json                       (manifest: suites → case IDs)
├── web-changes/
│   ├── leaderboard.tsx.snippet          (drop-in replacement for mock-data render)
│   └── README.md                        (where to apply the snippet)
└── notes/
    └── demo-runbook.md                  (one-page demo script)
```

---

## Phase 1 — Local code & cases (no external blockers)

### Task 1: Workspace bootstrap

**Files:**
- Create: `README.md`, `requirements.txt`, `.gitignore`, `.env.example`

- [ ] **Step 1: Write `requirements.txt`**

```
requests>=2.31
anthropic>=0.40
smolagents[litellm]>=1.0
pytest>=8.0
```

- [ ] **Step 2: Write `.gitignore`**

```
.env
__pycache__/
*.pyc
.pytest_cache/
venv/
.venv/
*.egg-info/
```

- [ ] **Step 3: Write `.env.example`**

```
ANTHROPIC_API_KEY=sk-ant-...
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_ANON_KEY=eyJ...
HF_DATASET_BASE=https://huggingface.co/datasets/AntiNoise-ai/trapstreet-cases/resolve/main
```

- [ ] **Step 4: Write `README.md`** (workspace overview, how to run)

```markdown
# Trapstreet Agent Eval v0.1 — Workspace

See `spec.md` for design, `plan.md` for implementation plan.

## Quick start

    python -m venv venv && source venv/bin/activate
    pip install -r requirements.txt
    cp .env.example .env  # fill in keys
    set -a; source .env; set +a
    python runner/trapstreet_eval.py financebench-1 --agent ./agent/claude_finance.py

## Layout

- `runner/` — the trapstreet evaluation runner (single-file CLI + helpers)
- `agent/` — reference agent implementations matching the BYO contract
- `case/` — case files staged before HF upload
- `web-changes/` — snippets to apply to apps/web (separate repo)
- `notes/` — demo runbook + scratch
```

- [ ] **Step 5: Initialize git, commit**

```bash
cd /Users/zhengruqi/Documents/Projects/trapstreet-agent-eval-v0.1
git init
git add .
git commit -m "chore: bootstrap workspace with spec, plan, deps"
```

---

### Task 2: Copy grader, write smoke test

**Files:**
- Create: `runner/grade.py` (copy from `~/.claude/skills/trapstreet-eval/grade.py`)
- Create: `runner/__init__.py` (empty)
- Create: `runner/tests/test_grade.py`
- Create: `runner/tests/__init__.py` (empty)

- [ ] **Step 1: Copy grade.py verbatim**

```bash
cp ~/.claude/skills/trapstreet-eval/grade.py runner/grade.py
chmod +x runner/grade.py
```

- [ ] **Step 2: Write the test**

`runner/tests/test_grade.py`:
```python
import subprocess
from pathlib import Path

GRADE = Path(__file__).parent.parent / "grade.py"


def grade(pred: str, gold: str) -> tuple[int, str]:
    r = subprocess.run(
        ["python3", str(GRADE), pred, gold],
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
```

- [ ] **Step 3: Run tests, expect PASS**

```bash
cd runner && python -m pytest tests/test_grade.py -v
```
Expected: 4 passed.

- [ ] **Step 4: Commit**

```bash
git add runner/grade.py runner/__init__.py runner/tests/
git commit -m "feat(runner): add grader and smoke tests"
```

---

### Task 3: Author case files locally

**Files:**
- Create: `case/financebench-1/task.json`
- Create: `case/financebench-1/docs/doc_a.txt` (Netflix — answer)
- Create: `case/financebench-1/docs/doc_b.txt` (AES — distractor)
- Create: `case/financebench-1/docs/doc_c.txt` (3M — distractor)
- Create: `case/financebench-1/docs/doc_d.txt` (Walmart — distractor)
- Create: `case/financebench-1/docs/doc_e.txt` (Block — distractor)
- Create: `case/index.json`

- [ ] **Step 1: Read source data from existing skill**

Source: `~/.claude/skills/trapstreet-eval/questions.json` — five entries, each with `evidence` field. Use these directly. Each entry's `evidence` becomes one of the doc_*.txt files (renamed so company isn't in filename).

Mapping:
- `financebench_id_03282` (Netflix) → `doc_a.txt` (the answer)
- `financebench_id_10420` (AES) → `doc_b.txt`
- `financebench_id_04672` (3M) → `doc_c.txt`
- `financebench_id_06247` (Walmart) → `doc_d.txt`
- `financebench_id_04660` (Block) → `doc_e.txt`

- [ ] **Step 2: Write a one-shot extractor script**

`case/_extract.py` (delete after running):
```python
import json
from pathlib import Path

src = Path.home() / ".claude/skills/trapstreet-eval/questions.json"
out = Path(__file__).parent / "financebench-1/docs"
out.mkdir(parents=True, exist_ok=True)

questions = json.loads(src.read_text())
mapping = {
    "financebench_id_03282": "doc_a.txt",
    "financebench_id_10420": "doc_b.txt",
    "financebench_id_04672": "doc_c.txt",
    "financebench_id_06247": "doc_d.txt",
    "financebench_id_04660": "doc_e.txt",
}
for q in questions:
    fname = mapping[q["id"]]
    (out / fname).write_text(q["evidence"])
print("wrote", list(mapping.values()))
```

- [ ] **Step 3: Run the extractor**

```bash
cd case && python _extract.py && rm _extract.py
```

- [ ] **Step 4: Write `task.json`**

`case/financebench-1/task.json`:
```json
{
  "id": "financebench-1",
  "question": "What is Netflix's year end FY2017 total current liabilities (in USD millions)? Source documents are available in ./docs/ — exactly one is the right Netflix filing, the rest are distractors. Read the document, identify the line item, and report the final number on the last line of your response.",
  "gold": "$5466.00",
  "doc_files": ["doc_a.txt", "doc_b.txt", "doc_c.txt", "doc_d.txt", "doc_e.txt"],
  "type": "financebench-retrieval-v0",
  "version": 1,
  "source": "FinanceBench (https://github.com/patronus-ai/financebench)",
  "expected_correct_doc": "doc_a.txt"
}
```

- [ ] **Step 5: Write `case/index.json`**

```json
{
  "version": 1,
  "suites": {
    "financebench": ["financebench-1"]
  }
}
```

- [ ] **Step 6: Verify files exist with non-zero size**

```bash
ls -la case/financebench-1/docs/ && wc -l case/financebench-1/docs/*.txt
```
Expected: 5 files, all non-empty.

- [ ] **Step 7: Commit**

```bash
git add case/
git commit -m "feat(case): author financebench-1 with 5 distractor docs"
```

---

### Task 4: Echo test agent (fixture)

**Files:**
- Create: `runner/echo_agent.py`

This is a tiny agent that ignores everything and prints a hardcoded answer. Used by tests so we don't need an LLM in the loop to verify the runner plumbing.

- [ ] **Step 1: Write echo agent**

`runner/echo_agent.py`:
```python
#!/usr/bin/env python3
"""Test fixture: an agent that prints a hardcoded answer regardless of input."""
import os
import sys

# Read and discard stdin, accept scratch dir as argv[1]
_ = sys.stdin.read()
scratch = sys.argv[1] if len(sys.argv) > 1 else "/tmp"
assert os.path.isdir(scratch), f"scratch dir not found: {scratch}"

# Hardcoded answer for financebench-1 — pretend this is what a smart agent figured out
print("$5466.31")
```

- [ ] **Step 2: Make it executable**

```bash
chmod +x runner/echo_agent.py
```

- [ ] **Step 3: Smoke test**

```bash
mkdir -p /tmp/scratch_test/docs && echo "what?" | python3 runner/echo_agent.py /tmp/scratch_test
```
Expected output: `$5466.31`

- [ ] **Step 4: Commit**

```bash
git add runner/echo_agent.py
git commit -m "test(runner): add echo_agent fixture for runner tests"
```

---

### Task 5: HF fetcher

**Files:**
- Create: `runner/hf_fetch.py`
- Create: `runner/tests/test_hf_fetch.py`

For Phase 1 dev, the HF base URL points to a local file:// URL or a placeholder; we wire real HF in Phase 2 once the dataset is uploaded. The fetcher abstraction lets us swap.

- [ ] **Step 1: Write the test**

`runner/tests/test_hf_fetch.py`:
```python
import json
import shutil
from pathlib import Path
import pytest

from runner.hf_fetch import fetch_case_to_scratch


@pytest.fixture
def fake_dataset(tmp_path):
    # Build a fake "HF dataset" on disk and serve via file://
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
```

- [ ] **Step 2: Run, expect FAIL (module missing)**

```bash
cd /Users/zhengruqi/Documents/Projects/trapstreet-agent-eval-v0.1
python -m pytest runner/tests/test_hf_fetch.py -v
```

- [ ] **Step 3: Implement `runner/hf_fetch.py`**

```python
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
```

- [ ] **Step 4: Run tests, expect PASS**

```bash
python -m pytest runner/tests/test_hf_fetch.py -v
```

- [ ] **Step 5: Commit**

```bash
git add runner/hf_fetch.py runner/tests/test_hf_fetch.py
git commit -m "feat(runner): add HF case fetcher with file:// support for tests"
```

---

### Task 6: Runner core — invoke agent + grade

**Files:**
- Create: `runner/trapstreet_eval.py`
- Create: `runner/tests/test_runner.py`

- [ ] **Step 1: Write the test**

`runner/tests/test_runner.py`:
```python
import json
import subprocess
import sys
from pathlib import Path

WORKSPACE = Path(__file__).parent.parent.parent
RUNNER = WORKSPACE / "runner/trapstreet_eval.py"
ECHO_AGENT = WORKSPACE / "runner/echo_agent.py"


def setup_local_dataset(tmp_path: Path) -> str:
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
        "version": 1
    }))
    (docs / "doc_a.txt").write_text("dummy doc")
    return f"file://{root}"


def test_runner_with_echo_agent_correct(tmp_path):
    base = setup_local_dataset(tmp_path)
    r = subprocess.run(
        [sys.executable, str(RUNNER), "financebench-1",
         "--agent", str(ECHO_AGENT),
         "--no-submit",
         "--hf-base", base],
        capture_output=True, text=True, timeout=60
    )
    assert r.returncode == 0, r.stderr
    assert "CORRECT" in r.stdout or "✅" in r.stdout
    assert "$5466.31" in r.stdout  # the agent's answer is in the output


def test_runner_with_failing_agent(tmp_path):
    """Agent that exits non-zero should cause runner to fail cleanly."""
    base = setup_local_dataset(tmp_path)
    bad_agent = tmp_path / "bad.py"
    bad_agent.write_text("import sys; sys.exit(7)")
    r = subprocess.run(
        [sys.executable, str(RUNNER), "financebench-1",
         "--agent", f"python3 {bad_agent}",
         "--no-submit",
         "--hf-base", base],
        capture_output=True, text=True, timeout=60
    )
    assert r.returncode != 0
    assert "agent" in r.stderr.lower() or "exit" in r.stderr.lower()
```

- [ ] **Step 2: Run, expect FAIL**

```bash
python -m pytest runner/tests/test_runner.py -v
```

- [ ] **Step 3: Implement runner**

`runner/trapstreet_eval.py`:
```python
#!/usr/bin/env python3
"""Trapstreet eval runner — fetches a case, invokes an agent, grades the result."""
from __future__ import annotations

import argparse
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from runner.hf_fetch import fetch_case_to_scratch

DEFAULT_HF_BASE = "https://huggingface.co/datasets/AntiNoise-ai/trapstreet-cases/resolve/main"
GRADE_SCRIPT = Path(__file__).parent / "grade.py"


def run_agent(agent_cmd: str, scratch: Path, question: str, timeout: int = 600) -> str:
    """Spawn the agent subprocess; return its final non-empty stdout line."""
    parts = shlex.split(agent_cmd) + [str(scratch)]
    r = subprocess.run(
        parts,
        input=question,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if r.returncode != 0:
        sys.stderr.write(f"agent exited {r.returncode}\nstderr:\n{r.stderr}\n")
        sys.exit(1)
    lines = [ln for ln in r.stdout.strip().splitlines() if ln.strip()]
    if not lines:
        sys.stderr.write("agent produced no output\n")
        sys.exit(1)
    return lines[-1]


def grade(answer: str, gold: str) -> tuple[bool, str]:
    r = subprocess.run(
        [sys.executable, str(GRADE_SCRIPT), answer, gold],
        capture_output=True, text=True
    )
    return (r.returncode == 0, r.stdout.strip())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("case_id")
    ap.add_argument("--agent", required=True, help="Agent command (e.g. ./agent/foo.py or 'python3 -m mymod')")
    ap.add_argument("--agent-label", default=None)
    ap.add_argument("--no-submit", action="store_true")
    ap.add_argument("--hf-base", default=os.environ.get("HF_DATASET_BASE", DEFAULT_HF_BASE))
    args = ap.parse_args()

    label = args.agent_label or Path(shlex.split(args.agent)[0]).stem

    scratch = Path(tempfile.mkdtemp(prefix="trapstreet-"))
    try:
        print(f"→ fetching {args.case_id} from {args.hf_base}")
        task = fetch_case_to_scratch(args.case_id, args.hf_base, scratch)
        print(f"  scratch: {scratch}")
        print(f"  docs: {task['doc_files']}")

        print(f"→ running agent: {args.agent}")
        answer = run_agent(args.agent, scratch, task["question"])
        print(f"  answer: {answer!r}")

        ok, msg = grade(answer, task["gold"])
        verdict = "correct" if ok else "wrong"
        print(f"→ grader: {msg}")
        print()
        print(f"  Score: {1 if ok else 0}/1")
        print(f"  Verdict: {verdict}")
        print(f"  Agent: {label}")

        if args.no_submit:
            print("  (skipped submission: --no-submit)")
            return 0

        # Submission wired in Task 9
        print("  (submission not yet implemented — see Task 9)")
        return 0
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Make executable**

```bash
chmod +x runner/trapstreet_eval.py
```

- [ ] **Step 5: Run tests, expect PASS**

```bash
python -m pytest runner/tests/ -v
```

- [ ] **Step 6: Commit**

```bash
git add runner/trapstreet_eval.py runner/tests/test_runner.py
git commit -m "feat(runner): core runner — fetch, invoke agent, grade"
```

---

### Task 7: Hand-rolled fallback agent

**Files:**
- Create: `agent/claude_finance.py`

Direct Anthropic SDK call with file-read tool — the safety-net agent that's guaranteed to work even if smolagents has issues.

- [ ] **Step 1: Write the agent**

`agent/claude_finance.py`:
```python
#!/usr/bin/env python3
"""Reference finance agent — Anthropic SDK with a file-read tool, single tool-use loop."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import anthropic

MODEL = "claude-opus-4-7"
MAX_TURNS = 10

SYSTEM = (
    "You are a financial analyst. Documents in ./docs/ contain SEC filings. "
    "Exactly one document contains the answer; the rest are distractors. "
    "Use the read_doc tool to read documents. "
    "When you have the answer, output ONLY the final numeric value as the LAST LINE of your response. "
    "Format the answer as a USD-millions value matching the question (e.g. '$5466.00')."
)

TOOLS = [{
    "name": "read_doc",
    "description": "Read a document from ./docs/ in the scratch dir.",
    "input_schema": {
        "type": "object",
        "properties": {"filename": {"type": "string"}},
        "required": ["filename"],
    },
}]


def main() -> int:
    scratch = Path(sys.argv[1])
    docs = scratch / "docs"
    question = sys.stdin.read().strip()
    available = sorted(p.name for p in docs.iterdir())

    client = anthropic.Anthropic()
    messages = [{
        "role": "user",
        "content": f"Files available in ./docs/: {available}\n\nQuestion: {question}",
    }]

    for _ in range(MAX_TURNS):
        resp = client.messages.create(
            model=MODEL,
            max_tokens=2048,
            system=SYSTEM,
            tools=TOOLS,
            messages=messages,
        )
        messages.append({"role": "assistant", "content": resp.content})

        if resp.stop_reason == "end_turn":
            text = "\n".join(b.text for b in resp.content if b.type == "text")
            print(text)
            return 0

        if resp.stop_reason == "tool_use":
            tool_results = []
            for block in resp.content:
                if block.type != "tool_use":
                    continue
                fname = block.input.get("filename", "")
                p = docs / fname
                content = p.read_text() if p.exists() else f"ERROR: {fname} not found. Available: {available}"
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": content,
                })
            messages.append({"role": "user", "content": tool_results})
            continue

        sys.stderr.write(f"unexpected stop_reason: {resp.stop_reason}\n")
        return 1

    sys.stderr.write("agent exceeded max turns\n")
    return 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Make executable**

```bash
chmod +x agent/claude_finance.py
```

- [ ] **Step 3: End-to-end test with real Claude (requires ANTHROPIC_API_KEY)**

```bash
# Build a local file:// dataset using the case files we authored
mkdir -p /tmp/local-ds/cases
cp -r case/financebench-1 /tmp/local-ds/cases/

python runner/trapstreet_eval.py financebench-1 \
  --agent ./agent/claude_finance.py \
  --no-submit \
  --hf-base file:///tmp/local-ds
```
Expected: agent reads docs, outputs an answer matching `$5466` ± tolerance, grader prints `CORRECT`.

- [ ] **Step 4: Commit**

```bash
git add agent/claude_finance.py
git commit -m "feat(agent): hand-rolled Claude finance agent (BYO contract)"
```

---

### Task 8: smolagents adapter (primary agent)

**Files:**
- Create: `agent/smolagents_finance.py`

- [ ] **Step 1: Write the agent**

`agent/smolagents_finance.py`:
```python
#!/usr/bin/env python3
"""Finance agent built on smolagents (HuggingFace) — primary demo agent."""
from __future__ import annotations

import os
import sys
from pathlib import Path

from smolagents import CodeAgent, LiteLLMModel, tool

scratch = Path(sys.argv[1])
docs_dir = scratch / "docs"
question = sys.stdin.read().strip()
available = sorted(p.name for p in docs_dir.iterdir())


@tool
def read_doc(filename: str) -> str:
    """Read one of the documents in the scratch dir's docs/ folder.

    Args:
        filename: The filename within ./docs/ (e.g. 'doc_a.txt')
    """
    p = docs_dir / filename
    if not p.exists():
        return f"ERROR: {filename} not found. Available: {available}"
    return p.read_text()


SYSTEM_PROMPT_ADDITION = (
    "You are a financial analyst. Documents in ./docs/ contain SEC filings; "
    "exactly one is relevant, the rest are distractors. "
    "Use read_doc(filename) to read documents. "
    "When you have the final number, output ONLY that number on the last line."
)

model = LiteLLMModel(model_id="anthropic/claude-opus-4-7")
agent = CodeAgent(tools=[read_doc], model=model)

prompt = (
    f"{SYSTEM_PROMPT_ADDITION}\n\n"
    f"Files available: {available}\n\n"
    f"Question: {question}"
)

answer = agent.run(prompt)
print(answer)
```

- [ ] **Step 2: Make executable**

```bash
chmod +x agent/smolagents_finance.py
```

- [ ] **Step 3: End-to-end test**

```bash
python runner/trapstreet_eval.py financebench-1 \
  --agent ./agent/smolagents_finance.py \
  --no-submit \
  --hf-base file:///tmp/local-ds
```
Expected: agent (Claude under smolagents) reads docs, outputs answer matching `$5466` ± tolerance, grader prints `CORRECT`.

If smolagents has install issues here, document them in `notes/` and demo with the hand-rolled fallback. Do NOT block subsequent tasks on smolagents — the fallback satisfies the demo.

- [ ] **Step 4: Commit**

```bash
git add agent/smolagents_finance.py
git commit -m "feat(agent): smolagents finance agent (primary)"
```

---

### Task 9: Supabase client stub (will activate in Phase 2)

**Files:**
- Create: `runner/supabase_client.py`

We write the client now so the runner can import it; the URL/key will be supplied via env in Phase 2.

- [ ] **Step 1: Write the client**

`runner/supabase_client.py`:
```python
"""Tiny Supabase REST client — POST /rest/v1/runs only."""
from __future__ import annotations

import json
import os
import urllib.request


def submit_run(payload: dict, *, supabase_url: str | None = None, anon_key: str | None = None) -> dict:
    """POST a run to the Supabase `runs` table. Returns the inserted row dict."""
    supabase_url = supabase_url or os.environ.get("SUPABASE_URL")
    anon_key = anon_key or os.environ.get("SUPABASE_ANON_KEY")
    if not supabase_url or not anon_key:
        raise RuntimeError(
            "SUPABASE_URL and SUPABASE_ANON_KEY must be set (or passed as args)"
        )

    url = f"{supabase_url.rstrip('/')}/rest/v1/runs"
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "apikey": anon_key,
            "Authorization": f"Bearer {anon_key}",
            "Prefer": "return=representation",
        },
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        rows = json.loads(r.read())
    return rows[0] if isinstance(rows, list) and rows else {}
```

- [ ] **Step 2: Wire into runner**

Edit `runner/trapstreet_eval.py` `main()` — replace the `# Submission wired in Task 9` placeholder block with:

```python
from runner.supabase_client import submit_run

# ...replace the placeholder block with:
        if args.no_submit:
            print("  (skipped submission: --no-submit)")
            return 0

        handle = input("\nHandle for the leaderboard (1–40 chars): ").strip()
        if not handle:
            print("  (no handle — skipping submission)")
            return 0

        try:
            row = submit_run({
                "handle": handle,
                "case_id": args.case_id,
                "agent_label": label,
                "score": 1 if ok else 0,
                "total": 1,
                "given": answer,
                "gold": task["gold"],
                "verdict": verdict,
            })
            print(f"  ✅ submitted: {row.get('id', '?')}")
            print(f"  → https://trapstreet.run/leaderboard/")
        except Exception as e:
            print(f"  ❌ submission failed: {e}")
            return 1
        return 0
```

- [ ] **Step 3: Add submission test (with mocked URL)**

`runner/tests/test_supabase_client.py`:
```python
import json
from unittest.mock import patch, MagicMock

from runner.supabase_client import submit_run


def test_submit_run_posts_payload():
    fake_response = MagicMock()
    fake_response.read.return_value = json.dumps([{"id": "abc-123"}]).encode()
    fake_response.__enter__ = lambda self: fake_response
    fake_response.__exit__ = lambda self, *a: None

    with patch("urllib.request.urlopen", return_value=fake_response) as mock_open:
        row = submit_run(
            {"handle": "x", "case_id": "y", "agent_label": "z",
             "score": 1, "total": 1, "given": "g", "gold": "g", "verdict": "correct"},
            supabase_url="https://fake.supabase.co",
            anon_key="anon",
        )
    assert row == {"id": "abc-123"}
    mock_open.assert_called_once()
    req = mock_open.call_args[0][0]
    assert req.full_url == "https://fake.supabase.co/rest/v1/runs"
    assert req.headers["Apikey"] == "anon"
```

- [ ] **Step 4: Run, expect PASS**

```bash
python -m pytest runner/tests/test_supabase_client.py -v
```

- [ ] **Step 5: Commit**

```bash
git add runner/supabase_client.py runner/trapstreet_eval.py runner/tests/test_supabase_client.py
git commit -m "feat(runner): wire Supabase submission to runner"
```

---

### Task 10: Phase 1 verification

**Files:** none

- [ ] **Step 1: Run full local pipeline with echo agent**

```bash
mkdir -p /tmp/local-ds/cases && cp -r case/financebench-1 /tmp/local-ds/cases/
python runner/trapstreet_eval.py financebench-1 \
  --agent ./runner/echo_agent.py \
  --no-submit \
  --hf-base file:///tmp/local-ds
```
Expected: prints `CORRECT`, score 1/1.

- [ ] **Step 2: Run full pytest suite**

```bash
python -m pytest runner/tests/ -v
```
Expected: all tests pass.

- [ ] **Step 3: Pause — phase 1 complete, request external setup from user**

Print a message like:
```
Phase 1 done. To proceed, please:

1. Create public HF dataset: https://huggingface.co/new-dataset
   - Owner: AntiNoise-ai
   - Name: trapstreet-cases
   - Visibility: public
   - Then drop me the URL.

2. Create Supabase project: https://supabase.com/dashboard/new
   - Free tier OK
   - Then drop me the project URL and anon key.

I'll handle the rest.
```

---

## Phase 2 — External setup + integration

### Task 11: HF dataset upload (joint — user creates account/repo, I push files)

**Blocker:** user creates the HF dataset (Task 10 step 3 prompt).

**Files:**
- Modify: `.env` (add real `HF_DATASET_BASE` URL once dataset is up)

- [ ] **Step 1: User creates `AntiNoise-ai/trapstreet-cases` public dataset on HF**

(Manual step by user; agent waits.)

- [ ] **Step 2: User generates an HF write token** at https://huggingface.co/settings/tokens (read+write scope)

- [ ] **Step 3: Push case files using huggingface_hub**

```bash
pip install huggingface_hub
huggingface-cli login  # paste token
cd case
huggingface-cli upload --repo-type dataset AntiNoise-ai/trapstreet-cases . .
```

- [ ] **Step 4: Verify resolve URLs work**

```bash
curl -fsS https://huggingface.co/datasets/AntiNoise-ai/trapstreet-cases/resolve/main/cases/financebench-1/task.json | head
curl -fsS https://huggingface.co/datasets/AntiNoise-ai/trapstreet-cases/resolve/main/cases/financebench-1/docs/doc_a.txt | wc -l
```
Expected: task.json prints, doc_a.txt has many lines.

- [ ] **Step 5: Update `.env` with real HF base**

```
HF_DATASET_BASE=https://huggingface.co/datasets/AntiNoise-ai/trapstreet-cases/resolve/main
```

- [ ] **Step 6: End-to-end test against real HF**

```bash
set -a; source .env; set +a
python runner/trapstreet_eval.py financebench-1 \
  --agent ./agent/claude_finance.py \
  --no-submit
```
Expected: fetches from HF, agent runs, grader says CORRECT.

- [ ] **Step 7: Commit env changes (without secrets)**

```bash
# Do not commit .env. Only README mentions if updated.
git status  # confirm .env stays gitignored
```

---

### Task 12: Supabase project + schema

**Blocker:** user creates the Supabase project.

**Files:**
- Create: `notes/supabase-setup.md` (record of what was done, for future reference)

- [ ] **Step 1: User creates Supabase project**

Free tier, any region close to user. Save the project URL (`https://xxx.supabase.co`) and anon key (Settings → API → anon public).

- [ ] **Step 2: Apply schema in Supabase SQL editor**

Paste and run:
```sql
create table runs (
  id           uuid         primary key default gen_random_uuid(),
  handle       text         not null check (length(handle) between 1 and 40),
  case_id      text         not null,
  agent_label  text         not null,
  score        integer      not null check (score >= 0),
  total        integer      not null check (total > 0 and total >= score),
  given        text,
  gold         text,
  verdict      text         not null check (verdict in ('correct','wrong')),
  ts           timestamptz  not null default now()
);

create index runs_case_score_idx on runs (case_id, score desc, ts desc);

alter table runs enable row level security;

create policy "public read" on runs
  for select to anon using (true);

create policy "public insert" on runs
  for insert to anon with check (true);
```

- [ ] **Step 3: Update `.env` with real Supabase values**

```
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_ANON_KEY=eyJ...
```

- [ ] **Step 4: Smoke test POST**

```bash
set -a; source .env; set +a
curl -X POST "$SUPABASE_URL/rest/v1/runs" \
  -H "Content-Type: application/json" \
  -H "apikey: $SUPABASE_ANON_KEY" \
  -H "Authorization: Bearer $SUPABASE_ANON_KEY" \
  -H "Prefer: return=representation" \
  -d '{"handle":"smoke","case_id":"financebench-1","agent_label":"smoke","score":0,"total":1,"given":"x","gold":"y","verdict":"wrong"}'
```
Expected: returns the inserted row with an `id`.

- [ ] **Step 5: Smoke test GET**

```bash
curl "$SUPABASE_URL/rest/v1/runs?select=*&order=ts.desc" \
  -H "apikey: $SUPABASE_ANON_KEY"
```
Expected: returns the smoke row.

- [ ] **Step 6: Delete the smoke row** via SQL editor: `delete from runs where handle = 'smoke';`

- [ ] **Step 7: Document in `notes/supabase-setup.md`**

```markdown
# Supabase setup (executed YYYY-MM-DD)

- Project: <name>
- URL: https://xxxxx.supabase.co
- Region: <region>
- Schema applied: see `spec.md` § Supabase schema
- RLS: public read + public insert (v0.1 demo trust model — replace in v0.2)
```

- [ ] **Step 8: Commit**

```bash
git add notes/supabase-setup.md
git commit -m "docs: record supabase setup"
```

---

### Task 13: Real submission end-to-end

**Files:** none

- [ ] **Step 1: Run full pipeline with submission**

```bash
set -a; source .env; set +a
python runner/trapstreet_eval.py financebench-1 \
  --agent ./agent/claude_finance.py
# When prompted, type a handle like "trapstreet-demo"
```
Expected: agent runs, grader says CORRECT, prompt for handle, submission succeeds, prints leaderboard URL.

- [ ] **Step 2: Verify in Supabase**

```bash
curl "$SUPABASE_URL/rest/v1/runs?select=*&order=ts.desc&limit=5" \
  -H "apikey: $SUPABASE_ANON_KEY"
```
Expected: row with the handle from step 1.

- [ ] **Step 3: Commit (no code changes; just confirm)**

```bash
# nothing to commit — phase 2 is done.
```

---

## Phase 3 — Web integration

### Task 14: Leaderboard page wired to Supabase

**Files:**
- Modify: existing leaderboard component in `/Users/zhengruqi/Documents/Projects/Collaborating/trapstreet/apps/web/`
- Create: `web-changes/leaderboard.tsx.snippet` (reference copy in workspace)
- Create: `web-changes/README.md` (how to apply)

- [ ] **Step 1: Locate the leaderboard component**

```bash
cd /Users/zhengruqi/Documents/Projects/Collaborating/trapstreet/apps/web
grep -r "mock-data" src/ --include="*.tsx" --include="*.ts"
```
Expected: lists the file(s) that import mock data.

- [ ] **Step 2: Identify which mock array represents leaderboard runs**

Read `src/lib/mock-data.ts`, find the array shaped like `{handle, score, ...}`. Note its name.

- [ ] **Step 3: Create the fetch hook**

In `apps/web/src/lib/`, create `leaderboard-fetch.ts`:
```typescript
const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL!;
const SUPABASE_ANON = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!;

export type RunRow = {
  id: string;
  handle: string;
  case_id: string;
  agent_label: string;
  score: number;
  total: number;
  given: string | null;
  gold: string | null;
  verdict: "correct" | "wrong";
  ts: string;
};

export async function fetchRuns(limit = 50): Promise<RunRow[]> {
  const url = `${SUPABASE_URL}/rest/v1/runs?select=*&order=score.desc,ts.desc&limit=${limit}`;
  const r = await fetch(url, { headers: { apikey: SUPABASE_ANON } });
  if (!r.ok) throw new Error(`supabase ${r.status}`);
  return await r.json();
}
```

- [ ] **Step 4: Add `NEXT_PUBLIC_SUPABASE_URL` and `NEXT_PUBLIC_SUPABASE_ANON_KEY` to apps/web env**

For local dev, create `apps/web/.env.local`:
```
NEXT_PUBLIC_SUPABASE_URL=https://xxxxx.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJ...
```

For GH Pages deploy: add the same as repo secrets and inject during build via `.github/workflows/deploy.yml` env block. (Confirm they're available at static export time — Next.js inlines `NEXT_PUBLIC_*` at build.)

- [ ] **Step 5: Replace mock data render in the leaderboard component**

In whichever component renders the leaderboard, replace `import { mockRuns } from "..."` with a `useEffect` + `useState` fetching `fetchRuns()`. Map rows to the existing table cells. Preserve styling.

Example (depending on existing component shape):
```tsx
"use client";
import { useEffect, useState } from "react";
import { fetchRuns, RunRow } from "@/lib/leaderboard-fetch";

export function Leaderboard() {
  const [rows, setRows] = useState<RunRow[]>([]);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    fetchRuns()
      .then(setRows)
      .catch(() => setRows([]))
      .finally(() => setLoading(false));
  }, []);
  if (loading) return <div>Loading…</div>;
  return (
    <table>
      <thead>
        <tr><th>#</th><th>Handle</th><th>Agent</th><th>Case</th><th>Score</th><th>When</th></tr>
      </thead>
      <tbody>
        {rows.map((r, i) => (
          <tr key={r.id}>
            <td>{i + 1}</td>
            <td>{r.handle}</td>
            <td>{r.agent_label}</td>
            <td>{r.case_id}</td>
            <td>{r.score}/{r.total}</td>
            <td>{new Date(r.ts).toLocaleString()}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
```

(Adapt to actual existing component structure — preserve their classNames, layout.)

- [ ] **Step 6: Save snippets to `web-changes/`**

Copy the final `leaderboard-fetch.ts` and the modified component to `web-changes/` for reference.

- [ ] **Step 7: Run dev server, verify**

```bash
cd /Users/zhengruqi/Documents/Projects/Collaborating/trapstreet/apps/web
pnpm dev
```
Visit `http://localhost:3000/leaderboard/` (or wherever the leaderboard route lives). Expected: shows the row from Task 13.

- [ ] **Step 8: Commit (in trapstreet repo, not workspace)**

```bash
cd /Users/zhengruqi/Documents/Projects/Collaborating/trapstreet
git add apps/web/src/lib/leaderboard-fetch.ts apps/web/src/<modified-component>
git commit -m "feat(web): live leaderboard from supabase, replaces mock data"
```

---

### Task 15: Deploy to GH Pages

**Files:**
- Modify (if needed): `/Users/zhengruqi/Documents/Projects/Collaborating/trapstreet/.github/workflows/deploy.yml`

- [ ] **Step 1: Check existing workflow**

```bash
cat /Users/zhengruqi/Documents/Projects/Collaborating/trapstreet/.github/workflows/deploy.yml
```
Confirm it builds the static export and deploys to GH Pages.

- [ ] **Step 2: Add Supabase env vars to the workflow**

If the workflow doesn't already pass env to the build, add an `env:` block to the build step:

```yaml
- name: Build
  env:
    NEXT_PUBLIC_SUPABASE_URL: ${{ secrets.NEXT_PUBLIC_SUPABASE_URL }}
    NEXT_PUBLIC_SUPABASE_ANON_KEY: ${{ secrets.NEXT_PUBLIC_SUPABASE_ANON_KEY }}
  run: pnpm --filter web build
```

- [ ] **Step 3: Add the secrets to the GitHub repo**

User adds `NEXT_PUBLIC_SUPABASE_URL` and `NEXT_PUBLIC_SUPABASE_ANON_KEY` at:
`https://github.com/AntiNoise-ai/trapstreet/settings/secrets/actions`

- [ ] **Step 4: Push to trigger deploy**

```bash
cd /Users/zhengruqi/Documents/Projects/Collaborating/trapstreet
git push
```

- [ ] **Step 5: Wait for the workflow to complete**

Watch at `https://github.com/AntiNoise-ai/trapstreet/actions`. Should be ~2-3 minutes.

- [ ] **Step 6: Verify on production**

Visit `https://trapstreet.run/leaderboard/` — should show the live data from Supabase.

- [ ] **Step 7: Hard-refresh** to bust GH Pages cache if showing old content.

---

## Phase 4 — Demo prep

### Task 16: Demo runbook

**Files:**
- Create: `notes/demo-runbook.md`

- [ ] **Step 1: Write the runbook**

```markdown
# Trapstreet Demo Runbook — 2026-04-30

## Pre-flight (10 min before)

- [ ] Open three terminals + browser tabs ready:
  - Terminal A: workspace dir, env loaded
  - Terminal B: `https://huggingface.co/datasets/AntiNoise-ai/trapstreet-cases` (browser)
  - Terminal C: `https://trapstreet.run/leaderboard/` (browser)
  - Editor: `agent/smolagents_finance.py` open
- [ ] Confirm `set -a; source .env; set +a` worked: `echo $SUPABASE_URL`
- [ ] Test internet
- [ ] Hard-refresh leaderboard
- [ ] Have fallback agent path ready: `agent/claude_finance.py`

## Demo (live, ~3 minutes)

1. **The case (HF tab)** — "trapstreet's cases live here, on HuggingFace. anyone can read them; adding a case is a git push, not a redeploy."

2. **The agent contract (editor)** — "every agent fits this contract: reads scratch dir, takes a question, prints an answer. ~30 lines. point trapstreet at *anything* that matches."

3. **Run it (terminal A)** —
   ```
   python runner/trapstreet_eval.py financebench-1 --agent ./agent/smolagents_finance.py
   ```
   Watch the agent read docs, find the right one, extract the number.

4. **Score** — runner prints "Score: 1/1, Verdict: correct".

5. **Submit** — type handle (e.g. "demo-2026-04-30"), confirm.

6. **Leaderboard** — refresh `trapstreet.run/leaderboard/`. Run is there.

7. **(Optional encore)** — run again with `--agent ./agent/claude_finance.py` to show BYO with a different agent. Two rows on the leaderboard.

## If something breaks

- Smolagents agent fails → fall back to `claude_finance.py` immediately.
- Submission fails → run with `--no-submit`, show the local CORRECT verdict, explain "leaderboard is a v0.1 add — let me show the data layer". Use the curl command in `notes/supabase-setup.md` to demo the API directly.
- HF fetch fails → use `--hf-base file:///tmp/local-ds` after `cp -r case/financebench-1 /tmp/local-ds/cases/`.

## After

- Save terminal output → `notes/demo-output-<date>.txt`
- Update README with v0.2 next steps based on demo feedback
```

- [ ] **Step 2: Commit**

```bash
git add notes/demo-runbook.md
git commit -m "docs: demo runbook for 2026-04-30"
```

---

### Task 17: Full rehearsal

**Files:** none

- [ ] **Step 1: Walk through the runbook end-to-end**

Run every command in the runbook against production HF and Supabase. Time it.

- [ ] **Step 2: Note timing**

Append to `notes/demo-runbook.md`: rehearsal time, any rough edges, fixes applied.

- [ ] **Step 3: If issues found, fix and re-rehearse.**

---

## Self-review

After completing all tasks:

1. **Spec coverage** — every section of `spec.md` has a corresponding task. ✅
2. **Placeholder scan** — no TBD/TODO in any file. (Run `grep -r 'TBD\|TODO' .` excluding `.git`.)
3. **Type consistency** — `case_id` field used consistently across runner, supabase_client, schema, leaderboard-fetch.
4. **Demo path runs** — full `trapstreet_eval.py financebench-1 --agent <real>` produces a leaderboard row.

---

## What this plan does NOT cover (v0.2+)

- Adding more cases (financebench-2..N): trivial extension once the pipeline works.
- Cross-vendor models (`--model openai/gpt-4o`): just env + adapter changes.
- Trajectory grading: requires storing tool-call logs.
- Closed-trap cases: server-side gold + a `/api/grade/<id>` endpoint.
- Auth on submissions: requires choosing GitHub OAuth or magic link.
- Inspect AI integration: replace bespoke runner with `inspect eval`.
