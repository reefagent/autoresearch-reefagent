#!/usr/bin/env python3
"""
Autoresearch Prompt Evaluator for ReefAgent

Evaluates prompt.md against 10 test cases using 5 binary criteria.
Uses Claude Code CLI (already authenticated) as both agent and judge.

Usage:
    python3 eval.py                 # Run all 10 cases sequentially
    python3 eval.py --verbose       # Show each response + judgment
    python3 eval.py --json          # Output JSON for parsing

Batch mode (for parallel execution via Claude Code subagents):
    python3 eval.py --batch 1       # Run batch 1 (cases 1-2 of 10)
    python3 eval.py --batch 3 --json # Run batch 3, output JSON
    python3 eval.py --cases feature_request,bug_report  # Run specific cases
    python3 eval.py --merge         # Merge batch_results/*.json into final score
"""

import json
import subprocess
import sys
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

MODEL_AGENT = "sonnet"   # generates agent responses
MODEL_JUDGE = "sonnet"   # judges responses (PASS/FAIL only)
BATCH_SIZE = 2           # cases per batch (10 cases / 5 batches)
BATCH_RESULTS_DIR = Path(__file__).parent / "batch_results"

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

def claude_cli(prompt: str, system_prompt: str | None = None, model: str = "haiku") -> tuple[str, dict]:
    """Call claude CLI in print mode. Returns (text_response, token_usage)."""
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
        timeout=120,
    )

    if result.returncode != 0:
        raise RuntimeError(f"claude CLI failed: {result.stderr[:200]}")

    try:
        data = json.loads(result.stdout)
        if data.get("is_error"):
            raise RuntimeError(f"claude error: {data.get('result', 'unknown')}")
        usage = data.get("usage", {})
        tokens = {
            "input_tokens": usage.get("input_tokens", 0),
            "output_tokens": usage.get("output_tokens", 0),
            "cache_read_tokens": usage.get("cache_read_input_tokens", 0),
            "cache_creation_tokens": usage.get("cache_creation_input_tokens", 0),
            "cost_usd": data.get("total_cost_usd", 0.0),
            "duration_ms": data.get("duration_ms", 0),
        }
        return data.get("result", ""), tokens
    except json.JSONDecodeError:
        return result.stdout.strip(), {"input_tokens": 0, "output_tokens": 0, "cache_read_tokens": 0, "cache_creation_tokens": 0, "cost_usd": 0.0, "duration_ms": 0}

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

def get_agent_response(prompt: str, case: dict) -> tuple[str, dict]:
    """Send a test case to the agent. Returns (response_text, token_usage)."""
    return claude_cli(case["input"], system_prompt=prompt, model=MODEL_AGENT)

def judge_response(case: dict, response: str, criterion: dict) -> tuple[bool, dict]:
    """Use Claude as judge. Returns (passed, token_usage)."""
    judge_prompt = f"""You are an impartial evaluator. Judge this AI agent response against one criterion.

CONTEXT: {case['context']}
USER INPUT: {case['input']}

AGENT RESPONSE:
{response}

CRITERION: {criterion['question']}

Answer ONLY "PASS" or "FAIL". Nothing else."""

    answer, tokens = claude_cli(judge_prompt, model=MODEL_JUDGE)
    return "PASS" in answer.strip().upper(), tokens

def add_tokens(totals: dict, usage: dict):
    """Accumulate token usage into totals dict."""
    for key in ("input_tokens", "output_tokens", "cache_read_tokens", "cache_creation_tokens", "cost_usd", "duration_ms"):
        totals[key] = totals.get(key, 0) + usage.get(key, 0)

def get_batch_cases(cases: list[dict], batch_num: int) -> list[dict]:
    """Get cases for a specific batch (1-indexed). 5 batches of 2."""
    start = (batch_num - 1) * BATCH_SIZE
    end = start + BATCH_SIZE
    return cases[start:end]

def filter_cases_by_id(cases: list[dict], case_ids: list[str]) -> list[dict]:
    """Filter cases to only include specified IDs."""
    return [c for c in cases if c["id"] in case_ids]

def empty_token_totals() -> dict:
    return {"input_tokens": 0, "output_tokens": 0, "cache_read_tokens": 0, "cache_creation_tokens": 0, "cost_usd": 0.0, "duration_ms": 0}

def run_eval(cases: list[dict], verbose: bool = False) -> dict:
    """Run evaluation on given cases. Returns results dict."""
    prompt = load_prompt()
    total_tokens = empty_token_totals()

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
        "token_usage": {},
    }

    for i, case in enumerate(cases):
        if verbose:
            print(f"\n{'='*60}")
            print(f"Case {i+1}/{len(cases)}: {case['id']}")
            print(f"Input: {case['input'][:80]}...")

        case_tokens = empty_token_totals()

        # Get agent response
        response, agent_tokens = get_agent_response(prompt, case)
        add_tokens(case_tokens, agent_tokens)
        add_tokens(total_tokens, agent_tokens)

        if verbose:
            print(f"Response ({len(response.split())} words):")
            print(f"  {response[:300]}...")
            print(f"  tokens: in={agent_tokens['input_tokens']} out={agent_tokens['output_tokens']} cost=${agent_tokens['cost_usd']:.4f}")

        # Judge each criterion
        case_results = {"id": case["id"], "criteria": {}, "pass_count": 0}

        for criterion in CRITERIA:
            passed, judge_tokens = judge_response(case, response, criterion)
            add_tokens(case_tokens, judge_tokens)
            add_tokens(total_tokens, judge_tokens)
            case_results["criteria"][criterion["id"]] = passed
            if passed:
                case_results["pass_count"] += 1
                results["criteria_scores"][criterion["id"]] += 1
                results["total_pass"] += 1
            results["total_checks"] += 1

            if verbose:
                status = "PASS" if passed else "FAIL"
                print(f"  [{status}] {criterion['id']}")

        case_results["token_usage"] = case_tokens
        results["cases"].append(case_results)

    # Compute final score
    results["pass_rate"] = round(
        results["total_pass"] / results["total_checks"], 4
    ) if results["total_checks"] > 0 else 0.0
    results["token_usage"] = total_tokens

    return results

def save_batch_result(results: dict, batch_id: str):
    """Save batch results to batch_results/<batch_id>.json."""
    BATCH_RESULTS_DIR.mkdir(exist_ok=True)
    out_path = BATCH_RESULTS_DIR / f"{batch_id}.json"
    out_path.write_text(json.dumps(results, indent=2))
    print(f"Batch results saved to {out_path}")

def merge_batch_results() -> dict:
    """Merge all batch_results/*.json into a single results dict."""
    if not BATCH_RESULTS_DIR.exists():
        raise RuntimeError(f"No batch_results/ directory found")

    batch_files = sorted(BATCH_RESULTS_DIR.glob("*.json"))
    if not batch_files:
        raise RuntimeError(f"No .json files in batch_results/")

    all_cases = []
    criteria_scores = {c["id"]: 0 for c in CRITERIA}
    total_pass = 0
    total_checks = 0
    total_tokens = empty_token_totals()

    for bf in batch_files:
        batch = json.loads(bf.read_text())
        all_cases.extend(batch["cases"])
        for cid, score in batch["criteria_scores"].items():
            criteria_scores[cid] += score
        total_pass += batch["total_pass"]
        total_checks += batch["total_checks"]
        if batch.get("token_usage"):
            add_tokens(total_tokens, batch["token_usage"])

    num_cases = len(all_cases)
    merged = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "prompt_file": "prompt.md",
        "model_agent": MODEL_AGENT,
        "model_judge": MODEL_JUDGE,
        "num_cases": num_cases,
        "num_criteria": len(CRITERIA),
        "cases": all_cases,
        "criteria_scores": criteria_scores,
        "total_pass": total_pass,
        "total_checks": total_checks,
        "pass_rate": round(total_pass / total_checks, 4) if total_checks > 0 else 0.0,
        "batches_merged": len(batch_files),
        "token_usage": total_tokens,
    }
    return merged

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
    if results.get("batches_merged"):
        print(f"Batches:    {results['batches_merged']} merged")
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
        ct = case.get("token_usage", {})
        tok_str = ""
        if ct.get("input_tokens"):
            tok_str = f"  [in:{ct['input_tokens']:,} out:{ct['output_tokens']:,} ${ct['cost_usd']:.4f}]"
        print(f"  {case['id']:25s} {score}/{total} {status}{fail_str}{tok_str}")

    # Token usage summary
    tu = results.get("token_usage", {})
    if tu.get("input_tokens"):
        print(f"\nToken usage:")
        print(f"  Input:          {tu['input_tokens']:,}")
        print(f"  Output:         {tu['output_tokens']:,}")
        print(f"  Cache read:     {tu['cache_read_tokens']:,}")
        print(f"  Cache created:  {tu['cache_creation_tokens']:,}")
        print(f"  Total cost:     ${tu['cost_usd']:.4f}")
        print(f"  Total duration: {tu['duration_ms'] / 1000:.1f}s")

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    verbose = "--verbose" in sys.argv or "-v" in sys.argv
    json_output = "--json" in sys.argv

    # --merge: combine batch results
    if "--merge" in sys.argv:
        print("Merging batch results...")
        results = merge_batch_results()
        if json_output:
            print(json.dumps(results, indent=2))
        else:
            print_summary(results)
        sys.exit(0)

    all_cases = load_eval_cases()

    # --batch N: run specific batch (1-5)
    batch_num = None
    if "--batch" in sys.argv:
        idx = sys.argv.index("--batch")
        batch_num = int(sys.argv[idx + 1])
        cases = get_batch_cases(all_cases, batch_num)
        batch_id = f"batch_{batch_num}"
        print(f"Running batch {batch_num}/5: {[c['id'] for c in cases]}")

    # --cases id1,id2: run specific cases
    elif "--cases" in sys.argv:
        idx = sys.argv.index("--cases")
        case_ids = sys.argv[idx + 1].split(",")
        cases = filter_cases_by_id(all_cases, case_ids)
        batch_id = f"cases_{'_'.join(case_ids)}"
        print(f"Running cases: {[c['id'] for c in cases]}")

    # default: run all
    else:
        cases = all_cases
        batch_id = None
        print("Running eval using Claude Code CLI (pre-authenticated)...")

    print(f"Agent model: {MODEL_AGENT} | Judge model: {MODEL_JUDGE}")
    cli_calls = len(cases) * (1 + len(CRITERIA))
    print(f"{len(cases)} cases x {len(CRITERIA)} criteria = {len(cases) * len(CRITERIA)} checks + {len(cases)} responses = {cli_calls} CLI calls")
    print("")

    results = run_eval(cases, verbose=verbose)

    # Save batch results if running in batch mode
    if batch_id:
        save_batch_result(results, batch_id)

    if json_output:
        print(json.dumps(results, indent=2))
    else:
        print_summary(results)
