#!/usr/bin/env python3
"""Finance agent built on smolagents (HuggingFace) — primary demo agent."""
from __future__ import annotations

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
