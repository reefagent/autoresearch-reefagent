#!/usr/bin/env python3
"""
Autoresearch Prompt Evaluator for ReefAgent

Evaluates prompt.md against 10 test cases using 5 binary criteria.
Uses Claude as both the agent (with the prompt) and the judge.

Usage:
    python eval.py                  # Run eval, print results
    python eval.py --json           # Output JSON for parsing
    python eval.py --verbose        # Show each response + judgment
"""

import json
import sys
import os
import time
from pathlib import Path

try:
    import anthropic
except ImportError:
    print("ERROR: pip install anthropic")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

MODEL_AGENT = "claude-sonnet-4-20250514"   # cheaper model for generating responses
MODEL_JUDGE = "claude-sonnet-4-20250514"   # judge model for evaluation
MAX_TOKENS_AGENT = 1024
MAX_TOKENS_JUDGE = 512

# Binary evaluation criteria (pass/fail)
CRITERIA = [
    {
        "id": "actionable",
        "question": "Does the response provide at least one concrete, actionable next step (not vague advice)?",
    },
    {
        "id": "concise",
        "question": "Is the response concise and focused (under 250 words, no unnecessary preamble or filler)?",
    },
    {
        "id": "persona",
        "question": "Does the response sound like a sharp technical cofounder (direct, casual, solution-oriented) rather than a generic AI assistant?",
    },
    {
        "id": "no_hedging",
        "question": "Does the response avoid excessive hedging, caveats, or 'it depends' without specifics?",
    },
    {
        "id": "ships_fast",
        "question": "Does the response prioritize shipping (smallest slice, iterate, speed) over over-engineering or analysis paralysis?",
    },
]

# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------

def load_prompt() -> str:
    """Load the current prompt from prompt.md."""
    path = Path(__file__).parent / "prompt.md"
    return path.read_text()

def load_eval_cases() -> list[dict]:
    """Load test cases from eval_cases.json."""
    path = Path(__file__).parent / "eval_cases.json"
    return json.loads(path.read_text())

def get_agent_response(client: anthropic.Anthropic, prompt: str, case: dict) -> str:
    """Send a test case to the agent with the given system prompt."""
    response = client.messages.create(
        model=MODEL_AGENT,
        max_tokens=MAX_TOKENS_AGENT,
        system=prompt,
        messages=[{"role": "user", "content": case["input"]}],
    )
    return response.content[0].text

def judge_response(client: anthropic.Anthropic, case: dict, response: str, criterion: dict) -> bool:
    """Use Claude as judge to evaluate one criterion. Returns True = pass."""
    judge_prompt = f"""You are an impartial evaluator. You will judge an AI agent's response against a specific criterion.

CONTEXT: {case['context']}
USER INPUT: {case['input']}

AGENT RESPONSE:
{response}

CRITERION: {criterion['question']}

Answer ONLY "PASS" or "FAIL". Nothing else."""

    result = client.messages.create(
        model=MODEL_JUDGE,
        max_tokens=MAX_TOKENS_JUDGE,
        messages=[{"role": "user", "content": judge_prompt}],
    )
    answer = result.content[0].text.strip().upper()
    return "PASS" in answer

def run_eval(verbose: bool = False) -> dict:
    """Run the full evaluation. Returns results dict."""
    client = anthropic.Anthropic()
    prompt = load_prompt()
    cases = load_eval_cases()

    results = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "prompt_file": "prompt.md",
        "num_cases": len(cases),
        "num_criteria": len(CRITERIA),
        "cases": [],
        "criteria_scores": {c["id"]: 0 for c in CRITERIA},
        "total_pass": 0,
        "total_checks": 0,
        "pass_rate": 0.0,
    }

    for i, case in enumerate(cases):
        if verbose:
            print(f"\n{'='*60}")
            print(f"Case {i+1}/{len(cases)}: {case['id']}")
            print(f"Input: {case['input'][:80]}...")

        # Get agent response
        response = get_agent_response(client, prompt, case)

        if verbose:
            print(f"Response ({len(response.split())} words): {response[:200]}...")

        # Judge each criterion
        case_results = {"id": case["id"], "criteria": {}, "pass_count": 0}

        for criterion in CRITERIA:
            passed = judge_response(client, case, response, criterion)
            case_results["criteria"][criterion["id"]] = passed
            if passed:
                case_results["pass_count"] += 1
                results["criteria_scores"][criterion["id"]] += 1
                results["total_pass"] += 1
            results["total_checks"] += 1

            if verbose:
                status = "PASS" if passed else "FAIL"
                print(f"  [{status}] {criterion['id']}: {criterion['question'][:60]}")

        results["cases"].append(case_results)

    # Compute final score
    results["pass_rate"] = round(results["total_pass"] / results["total_checks"], 4) if results["total_checks"] > 0 else 0.0

    return results

def print_summary(results: dict):
    """Print a human-readable summary."""
    print(f"\n{'='*60}")
    print(f"AUTORESEARCH EVAL RESULTS")
    print(f"{'='*60}")
    print(f"Timestamp:  {results['timestamp']}")
    print(f"Cases:      {results['num_cases']}")
    print(f"Criteria:   {results['num_criteria']}")
    print(f"Total:      {results['total_pass']}/{results['total_checks']}")
    print(f"")
    print(f"pass_rate: {results['pass_rate']}")
    print(f"")

    print("Per-criterion breakdown:")
    for crit in CRITERIA:
        score = results["criteria_scores"][crit["id"]]
        pct = round(score / results["num_cases"] * 100)
        bar = "#" * (pct // 5) + "." * (20 - pct // 5)
        print(f"  {crit['id']:15s} {score:2d}/{results['num_cases']} ({pct:3d}%) [{bar}]")

    print("")
    print("Per-case breakdown:")
    for case in results["cases"]:
        score = case["pass_count"]
        total = len(CRITERIA)
        status = "OK" if score == total else "!!"
        fails = [k for k, v in case["criteria"].items() if not v]
        fail_str = f" (failed: {', '.join(fails)})" if fails else ""
        print(f"  {case['id']:25s} {score}/{total} {status}{fail_str}")

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    verbose = "--verbose" in sys.argv or "-v" in sys.argv
    json_output = "--json" in sys.argv

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERROR: Set ANTHROPIC_API_KEY environment variable")
        sys.exit(1)

    results = run_eval(verbose=verbose)

    if json_output:
        print(json.dumps(results, indent=2))
    else:
        print_summary(results)
