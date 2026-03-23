# program.md — ReefAgent Prompt Optimization

> Autonomous experiment loop for improving the ReefAgent IDENTITY prompt.
> Inspired by Karpathy's autoresearch pattern.

## Objective

Maximize `pass_rate` by modifying `prompt.md`.

`pass_rate` is the fraction of (test_case x criterion) pairs that pass binary evaluation.
Higher is better. Range: 0.0 to 1.0.

## Scope

### In scope (you may modify)
- `prompt.md` — The agent's identity prompt. This is the ONLY file you modify.

### Out of scope (do NOT modify)
- `eval.py` — The evaluation harness (immutable)
- `eval_cases.json` — The test cases (immutable)
- `baseline.md` — The original prompt for reference (immutable)
- `program.md` — These instructions (immutable)

## Constraints

- `prompt.md` must remain under 800 words (the agent needs room for conversation)
- The prompt must maintain the ReefAgent brand identity (cofounder energy, ships fast, technical)
- Do not add few-shot examples longer than 2 lines each
- Do not add explicit instructions like "always respond in under 250 words" — the prompt should guide behavior through persona, not rules
- Simplicity criterion: if a change adds complexity but only marginally improves score, prefer the simpler version

## Evaluation

### Sequential (simple, slower ~5-8min)
```bash
python3 eval.py
```

### Parallel via subagents (fast, ~1-2min)
Use Claude Code's Agent tool to run 5 batches simultaneously:

1. **Create tasks** for tracking (TaskCreate for each batch 1-5)
2. **Spawn 5 subagents in parallel** — each runs one batch:
   ```bash
   python3 eval.py --batch 1 --json   # cases: feature_request, bug_report
   python3 eval.py --batch 2 --json   # cases: architecture_decision, vague_request
   python3 eval.py --batch 3 --json   # cases: prioritization, debugging_help
   python3 eval.py --batch 4 --json   # cases: quick_question, strategy
   python3 eval.py --batch 5 --json   # cases: code_review, onboarding
   ```
   Each subagent: run its batch, results auto-save to `batch_results/batch_N.json`
3. **Mark tasks completed** as each subagent finishes (TaskUpdate)
4. **Merge results** after all 5 complete:
   ```bash
   python3 eval.py --merge
   ```

### Subagent prompt template
When spawning each eval subagent:
```
Run eval batch N for the autoresearch project.
Execute: python3 eval.py --batch N --json
Working directory: /path/to/autoresearch-reefagent
Report the pass_rate from the output when done.
```

Extract the key metric from stdout:
```
pass_rate: <number>
```

Lower word count at same pass_rate is better (secondary metric).

## The 5 Binary Criteria

Each response is judged on:
1. **actionable** — Provides concrete next steps (not vague advice)
2. **concise** — Under 250 words, no filler
3. **persona** — Sounds like a sharp cofounder, not a generic AI
4. **no_hedging** — No excessive caveats or "it depends" without specifics
5. **ships_fast** — Prioritizes shipping over over-engineering

## Experiment Loop

### Setup (once)
1. Read this file, `prompt.md`, `eval.py`, and `eval_cases.json`
2. Run baseline: `python eval.py`
3. Record baseline score in `results.tsv`
4. Create branch: `git checkout -b autoresearch/session-1`

### Loop (repeat forever)
1. Read current `prompt.md` and `results.tsv` to understand history
2. Form a hypothesis for improvement (e.g., "adding decision framework will improve actionable score")
3. Modify `prompt.md` with ONE focused change
4. `git commit -am "experiment: <description>"`
5. Run eval — use **parallel mode** for speed:
   a. Create 5 tasks (TaskCreate) for tracking batches
   b. Spawn 5 subagents in parallel, each runs `python3 eval.py --batch N --json`
   c. Mark tasks completed as subagents finish (TaskUpdate)
   d. Merge: `python3 eval.py --merge` → extracts `pass_rate`
6. Record in `results.tsv`: `<commit>	<pass_rate>	<word_count>	<status>	<description>`
7. If pass_rate improved (higher): **KEEP** — this becomes the new baseline
8. If pass_rate equal or worse: **REVERT** — `git reset --hard HEAD~1`
9. **GOTO 1**

### Results format (results.tsv)
```
commit	pass_rate	word_count	status	description
baseline	0.7200	142	baseline	Original IDENTITY.md prompt
a1b2c3d	0.7600	155	keep	Added decision framework section
e4f5g6h	0.7400	168	discard	Added example responses (too long)
```

### When stuck
- Re-read `eval_cases.json` — which cases are failing?
- Run `python eval.py --verbose` to see actual responses and judgments
- Try removing content instead of adding (simpler prompts often score higher)
- Combine two near-miss ideas from previous experiments
- Try a radically different prompt structure (sections, bullets vs prose, etc.)

## NEVER STOP

Do NOT pause to ask the human if you should continue.
The human might be asleep.
You are autonomous.
If you run out of ideas, think harder.
The loop runs until the human interrupts you.
