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

Run:
```bash
python eval.py
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
5. Run: `python eval.py`
6. Extract `pass_rate` from output
7. Record in `results.tsv`: `<commit>	<pass_rate>	<word_count>	<status>	<description>`
8. If pass_rate improved (higher): **KEEP** — this becomes the new baseline
9. If pass_rate equal or worse: **REVERT** — `git reset --hard HEAD~1`
10. **GOTO 1**

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
