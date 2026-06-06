#!/usr/bin/env python3
"""Multi-step multi-tool test cases for myClaw agent harness.

These cases test the ReAct agent loop with multiple tool calls in sequence.
Run with: PYTHONPATH=/Users/baiding/LightClaw python tests/test_agent_loop_cases.py
"""

import sys
import os
from pathlib import Path

# Add parent to path for myClaw imports
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Load environment
ENV_PATH = Path(__file__).resolve().parents[1] / ".env"
if ENV_PATH.exists():
    for line in ENV_PATH.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if line and "=" in line and not line.startswith("#"):
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())

from core.agent import create_agent_harness
from core.provider import get_provider


def get_llm():
    """Get LLM instance."""
    provider_name = os.environ.get("MYCLAW_PROVIDER", "openai")
    model_name = os.environ.get("MYCLAW_MODEL")
    api_key = os.environ.get("OPENAI_API_KEY")
    base_url = os.environ.get("OPENAI_API_BASE")

    return get_provider(
        provider_name=provider_name,
        model=model_name,
        api_key=api_key,
        base_url=base_url,
    )


def run_case(name, message, harness, verbose=True):
    """Run a test case and print results."""
    print(f"\n{'='*60}")
    print(f"CASE: {name}")
    print(f"Input: {message}")
    print("="*60)

    try:
        result = harness.run(message, verbose=verbose)
        answer = result["answer"]
        turns = result["turns"]

        print(f"\nResult (turns={turns}):")
        print(f"  {answer[:500]}..." if len(answer) > 500 else f"  {answer}")

        return {"success": True, "answer": answer, "turns": turns}
    except Exception as e:
        print(f"\nERROR: {e}")
        return {"success": False, "error": str(e)}


def main():
    print("=" * 60)
    print("myClaw Agent Loop - Multi-Step Multi-Tool Test Cases")
    print("=" * 60)

    # Get LLM
    print("\nInitializing LLM...")
    llm = get_llm()
    print(f"  Provider: {os.environ.get('MYCLAW_PROVIDER', 'openai')}")
    print(f"  Model: {os.environ.get('MYCLAW_MODEL', 'default')}")

    # Create harness
    harness = create_agent_harness(llm, max_turns=15)
    print(f"  Tools: {[t.name for t in harness.tools]}")

    results = []

    # ==========================================
    # Case 1: Simple time query (single tool)
    # ==========================================
    result = run_case(
        "Single Tool - Get Time",
        "What's the current time?",
        harness
    )
    results.append(("Case 1: Single Tool - Get Time", result))

    # ==========================================
    # Case 2: Two tools - Calculator
    # ==========================================
    result = run_case(
        "Single Tool - Calculator",
        "What is 125 * 17?",
        harness
    )
    results.append(("Case 2: Single Tool - Calculator", result))

    # ==========================================
    # Case 3: Web Search
    # ==========================================
    result = run_case(
        "Single Tool - Web Search",
        "Search for the latest Python programming language version",
        harness
    )
    results.append(("Case 3: Single Tool - Web Search", result))

    # ==========================================
    # Case 4: Two tools in sequence - Search then Read URL
    # ==========================================
    result = run_case(
        "Two Tools - Search + Read URL",
        "Search for the official Python website, then read its homepage to find what version it shows",
        harness
    )
    results.append(("Case 4: Two Tools - Search + Read URL", result))

    # ==========================================
    # Case 5: Two tools - Time + Calculator
    # ==========================================
    result = run_case(
        "Two Tools - Time + Calculation",
        "What time is it now, and then calculate how many minutes are left until the next hour?",
        harness
    )
    results.append(("Case 5: Two Tools - Time + Calculation", result))

    # ==========================================
    # Case 6: Three tools - Search + Read + Calculator
    # ==========================================
    result = run_case(
        "Three Tools - Search + Read + Calculate",
        "Find the current Bitcoin price online, then calculate how much 0.5 BTC is worth in USD",
        harness
    )
    results.append(("Case 6: Three Tools - Search + Read + Calculate", result))

    # ==========================================
    # Case 7: Complex multi-step - Multiple web searches
    # ==========================================
    result = run_case(
        "Multi-Step - Multiple searches with calculation",
        "First search for the population of Tokyo, then search for the population of New York, and finally tell me which city is larger and by how much",
        harness
    )
    results.append(("Case 7: Multi-Step - Multiple searches", result))

    # ==========================================
    # Case 8: Echo tool for testing
    # ==========================================
    result = run_case(
        "Echo tool testing",
        "Use the echo tool to repeat back: 'Testing multi-tool coordination in myClaw'",
        harness
    )
    results.append(("Case 8: Echo tool", result))

    # ==========================================
    # Summary
    # ==========================================
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    passed = 0
    failed = 0
    for name, result in results:
        status = "PASS" if result.get("success") else "FAIL"
        if result.get("success"):
            passed += 1
        else:
            failed += 1
        turns = result.get("turns", "-")
        print(f"  [{status}] {name} (turns: {turns})")

    print(f"\nTotal: {passed} passed, {failed} failed")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())