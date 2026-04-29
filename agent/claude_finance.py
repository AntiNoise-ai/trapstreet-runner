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
