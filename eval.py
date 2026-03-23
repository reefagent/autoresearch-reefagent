#!/usr/bin/env python3
"""
Autoresearch Prompt Evaluator for ReefAgent

Evaluates prompt.md against 10 test cases using 5 binary criteria.
Uses Claude Code CLI (already authenticated) as both agent and judge.

Usage:
    python3 eval.py                 # Run eval, print results
    python3 eval.py --json          # Output JSON for parsing
    python3 eval.py --verbose       # Show each response + judgment
"""

import json
import subprocess
import sys
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

MODEL_AGENT = "haiku"    # fast + cheap for generating responses
MODEL_JUDGE = "haiku"    # fast + cheap for judging (PASS/FAIL only)

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
# Claude CLI wrapper
# ---------------------------------------------------------------------------

def claude_cli(prompt: str, system_prompt: str | None = None, model: str = "haiku") -> str:
    """Call claude CLI in print mode. Returns the text response."""
    cmd = [
        "claude", "-p",
        "--model", model,
        "--output-format", "json",
        "--no-session-persistence",
    ]
    if system_prompt:
        cmd.extend(["--system-prompt", system_prompt])
    cmd.append(prompt)

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=60,
    )

    if result.returncode != 0:
        raise RuntimeError(f"claude CLI failed: {result.stderr[:200]}")

    try:
        data = json.loads(result.stdout)
        if data.get("is_error"):
            raise RuntimeError(f"claude error: {data.get('result', 'unknown')}")
        return data.get("result", "")
    except json.JSONDecodeError:
        return result.stdout.strip()

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

def get_agent_response(prompt: str, case: dict) -> str:
    """Send a test case to the agent with the given system prompt."""
    return claude_cli(case["input"], system_prompt=prompt, model=MODEL_AGENT)

def judge_response(case: dict, response: str, criterion: dict) -> bool:
    """Use Claude as judge to evaluate one criterion. Returns True = pass."""
    judge_prompt = f"""You are an impartial evaluator. Judge this AI agent response against one criterion.

CONTEXT: {case['context']}
USER INPUT: {case['input']}

AGENT RESPONSE:
{response}

CRITERION: {criterion['question']}

Answer ONLY "PASS" or "FAIL". Nothing else."""

    answer = claude_cli(judge_prompt, model=MODEL_JUDGE)
    return "PASS" in answer.strip().upper()

def run_eval(verbose: bool = False) -> dict:
    """Run the full evaluation. Returns results dict."""
    prompt = load_prompt()
    cases = load_eval_cases()

    results = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "prompt_file": "prompt.md",
        "model_agent": MODEL_AGENT,
        "model_judge": MODEL_JUDGE,
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
        response = get_agent_response(prompt, case)

        if verbose:
            print(f"Response ({len(response.split())} words):")
            print(f"  {response[:300]}...")

        # Judge each criterion
        case_results = {"id": case["id"], "criteria": {}, "pass_count": 0}

        for criterion in CRITERIA:
            passed = judge_response(case, response, criterion)
            case_results["criteria"][criterion["id"]] = passed
            if passed:
                case_results["pass_count"] += 1
                results["criteria_scores"][criterion["id"]] += 1
                results["total_pass"] += 1
            results["total_checks"] += 1

            if verbose:
                status = "PASS" if passed else "FAIL"
                print(f"  [{status}] {criterion['id']}")

        results["cases"].append(case_results)

    # Compute final score
    results["pass_rate"] = round(
        results["total_pass"] / results["total_checks"], 4
    ) if results["total_checks"] > 0 else 0.0

    return results

def print_summary(results: dict):
    """Print a human-readable summary."""
    print(f"\n{'='*60}")
    print(f"AUTORESEARCH EVAL RESULTS")
    print(f"{'='*60}")
    print(f"Timestamp:  {results['timestamp']}")
    print(f"Agent:      {results['model_agent']}")
    print(f"Judge:      {results['model_judge']}")
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

    print("Running eval using Claude Code CLI (pre-authenticated)...")
    print(f"Agent model: {MODEL_AGENT} | Judge model: {MODEL_JUDGE}")
    print(f"10 cases x 5 criteria = 50 checks + 10 responses = 60 CLI calls")
    print("")

    results = run_eval(verbose=verbose)

    if json_output:
        print(json.dumps(results, indent=2))
    else:
        print_summary(results)
