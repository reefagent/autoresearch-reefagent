# autoresearch-reefagent

Autonomous prompt optimization for [ReefAgent](https://github.com/reefagent/reefagent) using the [Karpathy autoresearch](https://github.com/karpathy/autoresearch) pattern.

**One mutable file. One scalar metric. Git as memory. Loop forever.**

## What This Does

An AI agent autonomously improves the ReefAgent identity prompt (`prompt.md`) by:
1. Modifying the prompt with one focused change
2. Evaluating it against 10 real scenarios x 5 binary criteria = 50 checks
3. Keeping improvements, discarding regressions
4. Recording everything in `results.tsv`
5. Repeating forever until interrupted

The eval uses Claude Code CLI (pre-authenticated) — no API keys needed.

## Setup

```bash
# Clone
git clone https://github.com/reefagent/autoresearch-reefagent.git
cd autoresearch-reefagent

# Requires Claude Code CLI installed and authenticated
# https://docs.anthropic.com/en/docs/claude-code
claude --version  # verify it works
```

No Python dependencies needed beyond the standard library — eval.py calls the `claude` CLI directly via subprocess.

## Running the Evaluation

### Sequential (all 10 cases, ~5-8min)
```bash
python3 eval.py                 # Quick run — prints pass_rate and breakdown
python3 eval.py --verbose       # Show each response + every PASS/FAIL judgment
python3 eval.py --json          # JSON output for programmatic parsing
```

### Parallel via subagents (5 batches, ~1-2min)
When running inside Claude Code, use 5 subagents to run batches simultaneously:
```bash
# Each subagent runs one batch (2 cases each, 12 CLI calls)
python3 eval.py --batch 1       # feature_request + bug_report
python3 eval.py --batch 2       # architecture_decision + vague_request
python3 eval.py --batch 3       # prioritization + debugging_help
python3 eval.py --batch 4       # quick_question + strategy
python3 eval.py --batch 5       # code_review + onboarding

# After all 5 finish, merge results
python3 eval.py --merge         # Combines batch_results/*.json → final score
```

You can also run specific cases by ID:
```bash
python3 eval.py --cases feature_request,bug_report --json
```

**What happens:** Each batch fires 12 Claude CLI calls (2 agent responses + 10 judge calls). 5 batches in parallel = ~60 calls completed in ~1-2 minutes instead of ~5-8. Uses `sonnet` model. Token usage and cost tracked per-case and total.

**Expected output:**
```
============================================================
AUTORESEARCH EVAL RESULTS
============================================================
Timestamp:  2026-03-23T17:05:00
Agent:      haiku
Judge:      haiku
Cases:      10
Criteria:   5
Total:      42/50

pass_rate: 0.84

Per-criterion breakdown:
  actionable       9/10 ( 90%) [##################..]
  concise          7/10 ( 70%) [##############......]
  persona          9/10 ( 90%) [##################..]
  no_hedging       8/10 ( 80%) [################....]
  ships_fast       9/10 ( 90%) [##################..]
```

## Running the Autonomous Loop

Give this to Claude Code:

```
Read program.md and kick off the autoresearch loop
```

Or manually:

```bash
# Create experiment branch
git checkout -b autoresearch/session-1

# Run baseline
python3 eval.py
# Record baseline score in results.tsv

# The agent then loops:
# 1. Edit prompt.md (one change)
# 2. git commit
# 3. python3 eval.py
# 4. If improved → keep. If not → git reset --hard HEAD~1
# 5. Repeat forever
```

## The 5 Binary Criteria

Every agent response is judged PASS/FAIL on each:

| Criterion | What It Measures |
|-----------|-----------------|
| **actionable** | Provides at least one concrete next step (not vague advice) |
| **concise** | Under 250 words, no unnecessary preamble or filler |
| **persona** | Sounds like a sharp technical cofounder, not a generic AI |
| **no_hedging** | Avoids excessive caveats or "it depends" without specifics |
| **ships_fast** | Prioritizes shipping and iteration over over-engineering |

## The 10 Test Scenarios

| ID | Scenario | Tests |
|----|----------|-------|
| `feature_request` | User wants webhooks support | Planning, scoping |
| `bug_report` | Memory system dropping observations | Debugging, urgency |
| `architecture_decision` | PostgreSQL vs SQLite at scale | Technical judgment |
| `vague_request` | "Make the agent better" | Clarification skill |
| `prioritization` | Pick 1 of 3 features for this sprint | Decision-making |
| `debugging_help` | Debate system timeout with 4+ agents | Deep technical |
| `quick_question` | "What's the max context window?" | Brevity |
| `strategy` | Competitive positioning vs OpenClaw/Devin | Strategic thinking |
| `code_review` | Retry mechanism PR review | Code quality judgment |
| `onboarding` | New team member orientation | Mentoring |

## File Structure

```
autoresearch-reefagent/
  prompt.md           <- THE ONE MUTABLE FILE (agent identity prompt)
  eval.py             <- Evaluation harness (calls claude CLI)
  eval_cases.json     <- 10 test scenarios
  program.md          <- Strategy doc for the autonomous loop
  baseline.md         <- Original prompt for reference (immutable)
  results.tsv         <- Experiment audit trail
  batch_results/      <- Temporary batch outputs (auto-created in parallel mode)
```

| File | Role | Mutable? |
|------|------|----------|
| `prompt.md` | Agent identity prompt being optimized | **YES** (only this) |
| `eval.py` | Evaluation harness | NO |
| `eval_cases.json` | Test scenarios | NO |
| `program.md` | Strategy doc for the AI agent | NO |
| `baseline.md` | Original prompt for reference | NO |
| `results.tsv` | Experiment log | Auto-updated |
| `batch_results/` | Parallel batch outputs | Auto-created, ephemeral |

## How the Pattern Works

```
Human writes program.md (strategy doc)
       |
       v
Agent runs infinite loop:
  1. Read prompt.md + results.tsv
  2. Form hypothesis for improvement
  3. Modify prompt.md (one focused change)
  4. git commit
  5. Eval (parallel):
     ├─ Subagent 1: eval.py --batch 1  (feature_request, bug_report)
     ├─ Subagent 2: eval.py --batch 2  (architecture_decision, vague_request)
     ├─ Subagent 3: eval.py --batch 3  (prioritization, debugging_help)
     ├─ Subagent 4: eval.py --batch 4  (quick_question, strategy)
     └─ Subagent 5: eval.py --batch 5  (code_review, onboarding)
     → eval.py --merge → pass_rate
  6. If pass_rate improved -> KEEP
  7. If not -> git reset --hard HEAD~1
  8. Record in results.tsv
  9. GOTO 1
       |
       v
Git tracks all experiments (commit = checkpoint, reset = rollback)
```

## Cost Estimate

Using `sonnet` model for both agent and judge (token tracking built-in):
- ~60 CLI calls per eval run
- Token usage reported per-case and total after each run
- Use `--json` output to capture exact cost breakdown

## Extending

**Add test cases:** Edit `eval_cases.json` — add scenarios your agent struggles with.

**Add criteria:** Edit the `CRITERIA` list in `eval.py` — add what matters for your use case.

**Change models:** Edit `MODEL_AGENT` and `MODEL_JUDGE` in `eval.py`. Default is `sonnet`. Use `haiku` for faster/cheaper runs.

**Optimize other agents:** Copy `prompt.md` from any agent in `reefagent/agents/*/IDENTITY.md` and run the same loop.

## Based On

- [Karpathy's autoresearch](https://github.com/karpathy/autoresearch) — the original autonomous experiment loop
- [ReefAgent](https://github.com/reefagent/reefagent) — the agent platform whose prompts we're optimizing
- Research from 39 parallel agents exploring the autoresearch ecosystem (see `auto_learning.md` and `auto_discoveries.md` in [mac-mini-agent](https://github.com/reefagent/mac-mini-agent))
