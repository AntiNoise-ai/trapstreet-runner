#!/usr/bin/env python3
"""Trapstreet eval runner — fetches a case, invokes an agent per question, grades the result."""
from __future__ import annotations

import argparse
import os
import platform
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
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


def auto_patch(label: str) -> str:
    """Auto-detected environment string for the leaderboard's `patch` column."""
    base = f"{platform.system()} {platform.machine()}"
    lab = label.lower()
    if "smolagent" in lab:
        return f"claude-opus-4-7 via smolagents CodeAgent, {base}"
    if "claude" in lab:
        return f"claude-opus-4-7 (anthropic SDK) + Read tool, {base}"
    return base  # BYO agent — runner doesn't know what it ran


def estimate_cost_usd(label: str, num_questions: int) -> float:
    """Rough $/task estimate. v0.1 ships per-agent constants until we instrument
    real token capture (TODO v0.2). BYO agents return 0 unless self-reported.
    """
    lab = label.lower()
    if "smolagent" in lab:
        per_q = 0.08  # smolagents emits more tokens (code reasoning)
    elif "claude" in lab:
        per_q = 0.04  # opus 4.7 with ~2k tokens/q on this case
    else:
        return 0.0  # BYO — unknown
    return round(per_q * num_questions, 4)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("case_id")
    ap.add_argument("--agent", required=True, help="Agent command (e.g. ./agent/foo.py or 'python3 -m mymod')")
    ap.add_argument("--agent-label", default=None)
    ap.add_argument("--patch", default=None,
                    help="Override the auto-detected environment string (model + OS)")
    ap.add_argument("--cost-usd", type=float, default=None,
                    help="Self-reported $/run. Overrides the v0.1 per-agent estimate.")
    ap.add_argument("--github", default=None,
                    help="Optional GitHub username — renders avatar + link on the leaderboard")
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

        start = time.monotonic()
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

        latency_ms = int((time.monotonic() - start) * 1000)
        score = sum(1 for r in per_q if r["verdict"] == "correct")
        total = len(per_q)
        patch = args.patch or auto_patch(label)
        cost_usd = args.cost_usd if args.cost_usd is not None else estimate_cost_usd(label, total)

        print()
        print(f"  Score:    {score}/{total}")
        print(f"  Agent:    {label}")
        print(f"  Case:     {args.case_id}")
        print(f"  Latency:  {latency_ms / 1000:.1f}s")
        print(f"  Cost:     ${cost_usd:.4f} (estimated)")
        print(f"  Patch:    {patch}")

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

        github = args.github
        if not github and sys.stdin.isatty():
            try:
                github = input("GitHub username (optional, for avatar): ").strip()
            except EOFError:
                github = ""

        given_summary = " | ".join(f"{r['id']}={r['given']}" for r in per_q)
        gold_summary = " | ".join(f"{r['id']}={r['gold']}" for r in per_q)
        payload = {
            "handle": handle,
            "case_id": args.case_id,
            "agent_label": label,
            "score": score,
            "total": total,
            "given": given_summary[:1000],
            "gold": gold_summary[:1000],
            "verdict": "correct" if score == total else "wrong",
            "tier": "bronze",
            "fabrications": 0,
            "cost_usd": cost_usd,
            "latency_ms": latency_ms,
            "patch": patch,
        }
        if github:
            payload["github_handle"] = github
        try:
            row = submit_run(payload)
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
