# autoresearch-reefagent

Autonomous prompt optimization for ReefAgent using the Karpathy autoresearch pattern.

## How It Works

1. `prompt.md` is the ONLY mutable file — the agent's identity prompt
2. `eval.py` scores it against 10 test cases x 5 binary criteria = 50 checks
3. An AI agent modifies `prompt.md`, runs eval, keeps improvements, discards regressions
4. Git tracks all experiments; `results.tsv` is the audit trail

## Quick Start

```bash
# Install dependency
pip install anthropic

# Set API key
export ANTHROPIC_API_KEY=sk-...

# Run baseline evaluation
python eval.py

# Run with details
python eval.py --verbose

# Start the autonomous loop (give this to Claude Code)
# "Read program.md and kick off the autoresearch loop"
```

## The 5 Criteria

| Criterion | What It Measures |
|-----------|-----------------|
| actionable | Concrete next steps, not vague advice |
| concise | Under 250 words, no filler |
| persona | Sharp cofounder energy, not generic AI |
| no_hedging | No excessive caveats without specifics |
| ships_fast | Prioritizes shipping over over-engineering |

## Files

| File | Role | Mutable? |
|------|------|----------|
| `prompt.md` | The agent identity prompt being optimized | YES |
| `eval.py` | Evaluation harness (10 cases x 5 criteria) | NO |
| `eval_cases.json` | Test scenarios | NO |
| `program.md` | Strategy doc for the AI agent | NO |
| `baseline.md` | Original prompt for reference | NO |
| `results.tsv` | Experiment log | Auto-updated |

## Based On

[Karpathy's autoresearch](https://github.com/karpathy/autoresearch) — the pattern of "one mutable file + one scalar metric + fixed eval + git as memory + loop forever."
