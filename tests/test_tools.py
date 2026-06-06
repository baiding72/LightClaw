#!/usr/bin/env python3
"""Tool tests for myClaw - P0 tools + web_search."""

import sys
from pathlib import Path

# Add parent to path for myClaw imports
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.tools.builtins import ALL_TOOLS

# Test results tracking
passed = 0
failed = 0


def run_tool_case(tool, name, args, expected_contains=None):
    """Test a single tool invocation."""
    global passed, failed

    print(f"\n--- Testing {name} ---")
    try:
        result = tool.invoke(args) if isinstance(args, dict) else tool.invoke(**args)
        print(f"Result: {result[:200] if len(str(result)) > 200 else result}")

        if expected_contains:
            if any(exp in str(result) for exp in expected_contains):
                print(f"  ✓ Contains expected: {expected_contains}")
                passed += 1
            else:
                print(f"  ✗ Missing expected content: {expected_contains}")
                failed += 1
        else:
            print(f"  ✓ Tool executed successfully")
            passed += 1

    except Exception as e:
        print(f"  ✗ Exception: {e}")
        failed += 1

    return result


def main():
    global passed, failed

    print("=" * 60)
    print("myClaw P0 Tools Test Suite")
    print("=" * 60)

    # Create a tool map for easy access
    tool_map = {t.name: t for t in ALL_TOOLS}

    # ==========================================
    # Test 1: get_time (no arguments)
    # ==========================================
    run_tool_case(tool_map["get_time"], "get_time", {},
              expected_contains=["2026", "-", ":"])

    # ==========================================
    # Test 2: calculator (basic)
    # ==========================================
    run_tool_case(tool_map["calculator"], "calculator - basic", {"expression": "2 + 2"},
              expected_contains=["4"])

    run_tool_case(tool_map["calculator"], "calculator - complex", {"expression": "(10 * 5) - 20"},
              expected_contains=["30"])

    # ==========================================
    # Test 3: echo (no arguments = no-op)
    # ==========================================
    result = run_tool_case(tool_map["echo"], "echo - basic", {"message": "Hello myClaw"},
                       expected_contains=["Echo:", "Hello myClaw"])

    # ==========================================
    # Test 4: web_search
    # ==========================================
    result = run_tool_case(tool_map["web_search"], "web_search - simple query",
                       {"query": "Python programming language", "max_results": 3},
                       expected_contains=["Search results", "http"])

    # ==========================================
    # Test 5: read_url
    # ==========================================
    result = run_tool_case(tool_map["read_url"], "read_url - simple page",
                       {"url": "https://example.com"},
                       expected_contains=["Example", "domain"])

    # ==========================================
    # Summary
    # ==========================================
    print("\n" + "=" * 60)
    print(f"SUMMARY: {passed} passed, {failed} failed")
    print("=" * 60)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
