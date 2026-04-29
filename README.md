# trapstreet-runner

> Reference runner for [trapstreet.run](https://trapstreet.run) — a community
> eval harness for AI agents. Point it at any agent you've built, run a case,
> get a deterministic score, submit to the public leaderboard.

## Install

```bash
curl -fsSL https://trapstreet.run/install.sh | bash
```

This drops the CLI into `~/.local/bin/trapstreet` and the runtime into
`~/.trapstreet/` (a clean, removable directory). Re-running the installer
upgrades to the latest version.

## Run an eval

```bash
export ANTHROPIC_API_KEY=sk-ant-...
trapstreet eval financebench-1
```

That fetches the case from Hugging Face, runs the bundled reference agent
across all questions, grades each answer, and (if you provide a handle)
submits the result to <https://trapstreet.run/financebench/>.

## Bring your own agent

Any executable that matches the BYO contract works:

```
Invocation:  ./agent <scratch_dir>
Input:       question text on stdin
Files:       <scratch_dir>/docs/<file_a>, <file_b>, …
Output:      answer text on stdout (last non-empty line is the final answer)
Exit code:   0 on success
```

Then:

```bash
trapstreet eval financebench-1 --agent ./my-agent.py
```

See `agent/claude_finance.py` for a 50-line reference implementation
(direct Anthropic SDK + file-read tool) and `agent/smolagents_finance.py`
for the [smolagents](https://huggingface.co/docs/smolagents) version.

## Cases

Public dataset on Hugging Face:
<https://huggingface.co/datasets/Ruqii/trapstreet-cases>

Currently shipping:
- `financebench-1` — five SEC 10-K extraction & calculation questions
  (Netflix, AES, 3M, Walmart, Block) drawn from
  [PatronusAI's FinanceBench](https://github.com/patronus-ai/financebench).

## How submission works

The runner POSTs the result to a Supabase REST endpoint. Anyone with the
public anon key can submit (open-trust v0.1). Server-side regrade and
trust tiers are coming in v0.2. The leaderboard at `/financebench/` reads
the same rows live.

## Layout

```
runner/      CLI + grader + tests
agent/       reference agents
case/        local copies of cases (canonical source: Hugging Face)
bin/         the trapstreet shell launcher (installed to ~/.local/bin/)
install.sh   one-liner installer
spec.md      architecture and design rationale
plan.md      implementation plan
```

## Uninstall

```bash
rm -rf ~/.trapstreet ~/.local/bin/trapstreet
```

## License

MIT (see `LICENSE`).
