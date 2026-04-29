# Trapstreet Agent Eval v0.1 — Design Spec

**Date:** 2026-04-29
**Demo:** 2026-04-30
**Status:** Draft, awaiting user review

## Goal

Demo trapstreet as a **BYO-agent eval platform**: a user-built agent runs against a FinanceBench-derived task, gets graded by a deterministic scorer, and submits the result to a public leaderboard at trapstreet.run. One agent, one case, end-to-end.

## Scope (v0.1)

**In scope:**
- One agent task: `financebench-1` (Netflix FY2017 current liabilities, retrofitted as agent eval with 5 distractor docs)
- Two reference agents to demo BYO contract:
  - **Primary:** smolagents-based finance agent
  - **Fallback:** hand-rolled 30-line Claude API agent
- Cases hosted on HuggingFace Hub
- Submissions stored in Supabase with public read/write
- Leaderboard rendered on existing GH Pages site (`apps/web`)

**Out of scope (v0.2+):**
- Multi-vendor model comparison
- Cross-case eval (suites)
- Trajectory grading / step counting
- Closed-trap cases (server-side gold)
- Auth on submissions (real handle verification)
- Server-side regrade
- Sandbox isolation (Docker)

---

## Architecture

```
┌─ HuggingFace Hub ───────────────────────────────────────┐
│  AntiNoise-ai/trapstreet-cases (public dataset)         │
│    cases/                                               │
│      financebench-1/                                    │
│        task.json                                        │
│        docs/                                            │
│          doc_a.txt   ← Netflix 2017 10-K (the answer)   │
│          doc_b.txt   ← AES distractor                   │
│          doc_c.txt   ← 3M distractor                    │
│          doc_d.txt   ← Walmart distractor               │
│          doc_e.txt   ← Block distractor                 │
│    index.json                                           │
└─────────────────────────────────────────────────────────┘
                         │ HTTP GET (no auth, public dataset)
                         ▼
┌─ trapstreet_eval.py (single-file Python runner) ────────┐
│  $ trapstreet_eval.py financebench-1 --agent <cmd>      │
│                                                         │
│  1. Fetch task.json + docs/* from HF                    │
│  2. Unpack to mktemp scratch dir                        │
│  3. Spawn agent subprocess with contract (below)        │
│  4. Capture stdout → final answer                       │
│  5. Run grade.py → CORRECT / WRONG                      │
│  6. Prompt for handle                                   │
│  7. POST to Supabase                                    │
│  8. Print leaderboard URL                               │
└─────────────────────────────────────────────────────────┘
                         │ POST (anon key)
                         ▼
┌─ Supabase ──────────────────────────────────────────────┐
│  runs table — public INSERT + SELECT via RLS            │
└─────────────────────────────────────────────────────────┘
                         ▲
                         │ JS fetch (anon key)
┌─ trapstreet.run/leaderboard/ (GH Pages, static) ────────┐
│  Replaces apps/web/src/lib/mock-data.ts with live fetch │
└─────────────────────────────────────────────────────────┘
```

---

## Contracts (pinned)

### 1. Agent contract

Every agent — smolagents adapter, hand-rolled fallback, future BYO — implements **exactly this**:

```
Invocation:
    $ ./agent <scratch_dir>

Inputs:
    argv[1]   = absolute path to scratch dir
    stdin     = the question (plain text, possibly multi-line)
    env       = ANTHROPIC_API_KEY (or whatever the agent needs)

Files available to agent:
    <scratch_dir>/docs/doc_a.txt
    <scratch_dir>/docs/doc_b.txt
    ... (filenames from task.json's doc_files)

Output:
    stdout    = the answer. Last non-empty line is taken as final answer.
    exit code = 0 success, non-zero failure (run is not submitted)

Time budget:
    600 seconds wall clock (runner kills on timeout)
```

**Why this shape:** files live in the filesystem (SEC docs are large, JSON-encoding them is wasteful); question on stdin keeps invocation simple; scratch dir as argv lets the agent `cd` or pass it to its own tools.

### 2. HF case bundle — `task.json` schema

```json
{
  "id": "financebench-1",
  "question": "What is Netflix's year end FY2017 total current liabilities (in USD millions)? Source documents are available in ./docs/ — exactly one is the right Netflix filing, the rest are distractors.",
  "gold": "$5466.00",
  "doc_files": ["doc_a.txt", "doc_b.txt", "doc_c.txt", "doc_d.txt", "doc_e.txt"],
  "type": "financebench-retrieval-v0",
  "version": 1,
  "source": "FinanceBench (https://github.com/patronus-ai/financebench)",
  "expected_correct_doc": "doc_a.txt"
}
```

`expected_correct_doc` is for v0.2 trajectory scoring; v0.1 ignores it.

### 3. HF resolve URL pattern (no auth needed)

```
https://huggingface.co/datasets/AntiNoise-ai/trapstreet-cases/resolve/main/cases/<case-id>/task.json
https://huggingface.co/datasets/AntiNoise-ai/trapstreet-cases/resolve/main/cases/<case-id>/docs/<filename>
```

### 4. Supabase schema

```sql
create table runs (
  id           uuid         primary key default gen_random_uuid(),
  handle       text         not null check (length(handle) between 1 and 40),
  case_id      text         not null,
  agent_label  text         not null,   -- e.g. "smolagents-finance-v0", "claude-finance-v0", or BYO label
  score        integer      not null check (score >= 0),
  total        integer      not null check (total > 0 and total >= score),
  given        text,                    -- the agent's raw answer
  gold         text,                    -- the gold answer (kept here for transparency in v0.1 demo)
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

**v0.1 trust model:** anyone with the anon key can INSERT anything. Acceptable for demo; v0.2 will add server-side regrade and per-IP rate limits via Supabase Edge Functions or a small auth proxy.

### 5. Runner CLI

```
trapstreet_eval.py <case-id> --agent <cmd> [--agent-label <label>] [--no-submit]

  case-id        e.g. "financebench-1" — fetched from HF
  --agent        path to agent executable (required — makes BYO contract explicit)
  --agent-label  human-readable label for the leaderboard. Default: basename of --agent
  --no-submit    run + grade locally, skip Supabase POST
```

### 6. Environment

```
ANTHROPIC_API_KEY              required — for the agent's LLM calls
SUPABASE_URL                   required for submission — set in script or .env
SUPABASE_ANON_KEY              required for submission — set in script or .env
```

User exports these in their shell before running. Runner errors clearly if missing.

---

## Components & implementation breakdown

### Component 1 — HF case authoring (1h)

- Create public dataset `AntiNoise-ai/trapstreet-cases` on HuggingFace
- Author `cases/financebench-1/task.json` (use existing question text from skill's `questions.json`)
- Drop 5 SEC filing texts into `cases/financebench-1/docs/` as `doc_a.txt` through `doc_e.txt`
  - Source from existing FinanceBench data: Netflix, AES, 3M, Walmart, Block 10-Ks
  - Rename so company isn't in the filename — agent must read content
- Author `index.json` manifest at dataset root
- Verify resolve URLs work via `curl`

**Deliverable:** all files visible at `https://huggingface.co/datasets/AntiNoise-ai/trapstreet-cases/`

### Component 2 — Runner script (2h)

`runner/trapstreet_eval.py` — single-file Python, stdlib + `requests`:

```
- Parse args (case-id, --agent, --agent-label, --no-submit)
- Fetch task.json + each doc from HF (with timeout + retry)
- mktemp scratch dir, write docs/ with files, write .task.json for reference
- subprocess.run([agent_cmd, scratch_dir], input=question, timeout=600)
- Take final non-empty stdout line as answer
- Import grade module (copied from existing skill into runner/grade.py)
- Run grader, get verdict
- Print local result table
- If not --no-submit: prompt for handle, POST to Supabase
- Print leaderboard URL
```

`runner/grade.py` — copied verbatim from `~/.claude/skills/trapstreet-eval/grade.py`, single source of truth in this repo from now on.

### Component 3 — smolagents adapter (45 min)

`agent/smolagents_finance.py` — implements the agent contract above:

```python
import sys, os
from pathlib import Path
from smolagents import CodeAgent, LiteLLMModel, tool

scratch = Path(sys.argv[1])
docs_dir = scratch / "docs"
question = sys.stdin.read()

@tool
def read_doc(filename: str) -> str:
    """Read one of the documents in ./docs/."""
    p = docs_dir / filename
    if not p.exists():
        return f"ERROR: {filename} not found. Available: {sorted(os.listdir(docs_dir))}"
    return p.read_text()

model = LiteLLMModel(model_id="anthropic/claude-opus-4-7")
agent = CodeAgent(tools=[read_doc], model=model)

system = (
    "You are a financial analyst. The documents in ./docs/ contain SEC filings. "
    "Exactly one is relevant; the others are distractors. Read what you need, "
    "then output ONLY the final numeric answer on the last line."
)

answer = agent.run(f"{system}\n\nFiles available: {sorted(os.listdir(docs_dir))}\n\nQuestion: {question}")
print(answer)
```

Install: `pip install 'smolagents[litellm]'`

### Component 4 — Hand-rolled fallback agent (10 min)

`agent/claude_finance.py` — direct Anthropic API call with file-read tool:

```python
# ~50 lines: anthropic.Client, single tool-use loop with read_file tool,
# extracts final answer from last assistant message
```

Used as fallback if smolagents has install issues. Same agent contract.

### Component 5 — Supabase setup (1h)

- Create new Supabase project (free tier)
- Run schema SQL above in SQL editor
- Apply RLS policies
- Note `SUPABASE_URL` and `SUPABASE_ANON_KEY` from project settings
- Test: `curl -X POST` with sample payload, confirm row appears
- Test: `curl GET` with anon key, confirm row returns

**Deliverable:** working REST endpoints at `<project>.supabase.co/rest/v1/runs`

### Component 6 — Leaderboard page (1h)

In existing `trapstreet/apps/web/`:
- Replace mock data fetch in the leaderboard component with `fetch('${SUPABASE_URL}/rest/v1/runs?select=*&order=score.desc,ts.desc')` using anon key
- Hardcode Supabase URL + anon key as public env vars (Next.js public env)
- Render columns: `handle`, `agent_label`, `case_id`, `score/total`, `verdict`, `ts`
- Keep existing styling (no redesign)
- Deploy via existing GH Pages workflow

**Deliverable:** `https://trapstreet.run/leaderboard/` shows live submissions

### Component 7 — E2E + polish (1h)

- Run `trapstreet_eval.py financebench-1 --agent ./agent/smolagents_finance.py` end-to-end
- Verify result shows on live leaderboard
- Run with hand-rolled fallback agent to test BYO story
- Capture demo screenshots
- Write a one-page demo runbook (in this folder)

---

## Time estimate

| Component | Time |
|---|---|
| 1. HF case authoring | 1h |
| 2. Runner script | 2h |
| 3. smolagents adapter | 45 min |
| 4. Hand-rolled fallback | 10 min |
| 5. Supabase setup | 1h |
| 6. Leaderboard page | 1h |
| 7. E2E + polish + rehearsal | 1h |
| Buffer | 1h |
| **Total** | **~8h** |

**Critical path:** Component 5 (Supabase) blocks component 6 (leaderboard). Author cases (1) and runner (2) in parallel with Supabase (5). Adapters (3, 4) wait on runner (2).

---

## Risks & mitigations

| Risk | Likelihood | Mitigation |
|---|---|---|
| smolagents pip install pulls heavy deps | Low | Use `[litellm]` extra only, not `[transformers]`. Hand-rolled fallback is the safety net. |
| smolagents `CodeAgent` writes Python that fails sandboxing | Medium | smolagents runs Python locally by default — that's fine for this case. Test early. |
| HuggingFace dataset upload first-time friction | Medium | Allocate 30 min into block 1, have HF token ready. |
| Supabase RLS misconfigured → INSERTs fail silently | Medium | Test POST with curl immediately after schema apply. |
| GH Pages cache delays leaderboard update during demo | Medium | Push leaderboard changes early in the day; hard refresh in demo. |
| Buffer is thin (1h on 8h plan) | Real | If ahead of schedule, no-op. If behind, drop block 6 (leaderboard page) and demo via `curl GET` to Supabase to show submission landed. |

---

## Demo script (preview)

1. **Show the case** — open `huggingface.co/datasets/AntiNoise-ai/trapstreet-cases` → `financebench-1/task.json`. "Cases live on HF. Anyone can read them. Adding a case = git push, no redeploy."

2. **Show the agent contract** — open `agent/smolagents_finance.py`. "30 lines. Reads scratch dir, takes a question, prints an answer. Any agent that fits this contract works with trapstreet."

3. **Run it** — `trapstreet_eval.py financebench-1 --agent ./agent/smolagents_finance.py`. Watch the agent read docs, find the right one, extract the number. ~30 seconds.

4. **See the score** — runner prints local result table. "Correct. 1/1."

5. **Submit** — type handle, hit y. Runner POSTs to Supabase, prints leaderboard URL.

6. **Show the leaderboard** — open `trapstreet.run/leaderboard/`. Run is there.

7. **(Optional)** Run again with the hand-rolled agent to demo BYO. Same case, different agent, second row on the leaderboard.

---

## v0.2 roadmap (not for tomorrow)

- 5–10 more cases authored (financebench-2..10, then other categories)
- Trajectory scoring (step count, right-doc-on-first-read)
- Server-side regrade in Supabase Edge Function (close the trust loop)
- Auth (GitHub OAuth) for verified submissions
- Closed-trap cases (gold server-side)
- Sandbox=docker option for untrusted agents
- Inspect AI integration as the "real" runner
- Cross-vendor model comparison page on leaderboard
