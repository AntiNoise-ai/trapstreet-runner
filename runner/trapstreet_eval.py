#!/usr/bin/env python3
"""Trapstreet eval runner — fetches a case, invokes an agent per question, grades the result."""
from __future__ import annotations

import argparse
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# Allow running as both `python runner/trapstreet_eval.py` and `python -m runner.trapstreet_eval`
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from runner.hf_fetch import fetch_case_to_scratch
from runner.supabase_client import submit_run

DEFAULT_HF_BASE = "https://huggingface.co/datasets/Ruqii/trapstreet-cases/resolve/main"
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


def task_questions(task: dict) -> list[dict]:
    """Normalize: support v2 multi-question schema and v1 single-question fallback."""
    if "questions" in task:
        return list(task["questions"])
    return [{
        "id": task.get("id", "q1"),
        "question": task["question"],
        "gold": task["gold"],
    }]


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
        questions = task_questions(task)
        print(f"  scratch: {scratch}")
        print(f"  docs: {task.get('doc_files', [])}")
        print(f"  questions: {len(questions)}")

        per_q = []
        for i, q in enumerate(questions, 1):
            print()
            print(f"→ Q{i}/{len(questions)} [{q['id']}]: invoking agent")
            answer = run_agent(args.agent, scratch, q["question"])
            ok, msg = grade(answer, q["gold"])
            verdict = "correct" if ok else "wrong"
            mark = "✅" if ok else "❌"
            print(f"  answer: {answer!r}")
            print(f"  gold:   {q['gold']!r}")
            print(f"  {mark} {verdict} — {msg}")
            per_q.append({
                "id": q["id"],
                "given": answer,
                "gold": q["gold"],
                "verdict": verdict,
            })

        score = sum(1 for r in per_q if r["verdict"] == "correct")
        total = len(per_q)
        print()
        print(f"  Score:   {score}/{total}")
        print(f"  Agent:   {label}")
        print(f"  Case:    {args.case_id}")

        if args.no_submit:
            print("  (skipped submission: --no-submit)")
            return 0

        try:
            handle = input("\nHandle for the leaderboard (1–40 chars): ").strip()
        except EOFError:
            handle = ""
        if not handle:
            print("  (no handle — skipping submission)")
            return 0

        # Compact summary into given/gold for the row (keeps schema unchanged).
        given_summary = " | ".join(f"{r['id']}={r['given']}" for r in per_q)
        gold_summary = " | ".join(f"{r['id']}={r['gold']}" for r in per_q)
        try:
            row = submit_run({
                "handle": handle,
                "case_id": args.case_id,
                "agent_label": label,
                "score": score,
                "total": total,
                "given": given_summary[:1000],
                "gold": gold_summary[:1000],
                "verdict": "correct" if score == total else "wrong",
            })
            print(f"  ✅ submitted: {row.get('id', '?')}")
            print(f"  → https://trapstreet.run/financebench/")
        except Exception as e:
            print(f"  ❌ submission failed: {e}")
            return 1
        return 0
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
