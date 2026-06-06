#!/usr/bin/env python3
"""Simple CLI interface for myClaw agent - Custom ReAct harness."""

import os
import sys
from pathlib import Path

# Auto-add project root to path for imports
_project_root = Path(__file__).parent
sys.path.insert(0, str(_project_root))

# Auto-load .env file
_env_file = Path(__file__).parent / ".env"
if _env_file.exists():
    with open(_env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip())

from core.agent import create_agent_harness
from core.provider import get_provider


def main():
    """Run an interactive agent session."""
    print("Initializing myClaw agent (Custom ReAct harness)...")

    # Get LLM provider
    provider = os.environ.get("MYCLAW_PROVIDER", "openai")
    model = os.environ.get("MYCLAW_MODEL", None)
    api_key = os.environ.get("OPENAI_API_KEY", None)
    base_url = os.environ.get("OPENAI_API_BASE", None)

    try:
        llm = get_provider(provider, model=model, api_key=api_key, base_url=base_url)
        print(f"Connected to {provider}")
    except ValueError as e:
        print(f"Error: {e}")
        print("\nPlease set your API key:")
        print("  export OPENAI_API_KEY=your-key  # for OpenAI")
        print("  export ANTHROPIC_API_KEY=your-key  # for Anthropic")
        return

    # Create agent harness
    harness = create_agent_harness(llm)
    print("Agent ready! Type 'exit' or 'quit' to stop.\n")

    # Interactive loop
    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if user_input.lower() in ("exit", "quit", "q"):
            print("Goodbye!")
            break

        if not user_input:
            continue

        # Run agent
        result = harness.run(user_input, verbose=True)

        # Print trace
        print("\n" + "=" * 60)
        print("TRACE")
        print("=" * 60)

        state = result["state"]
        for msg in state.messages:
            msg_type = msg.get("type")
            if msg_type == "human":
                print(f"> [User]: {msg.get('content', '')}")
            elif msg_type == "ai":
                tool_calls = msg.get("tool_calls")
                if tool_calls:
                    print(f"> [AI] → calling {len(tool_calls)} tool(s)")
                    for tc in tool_calls:
                        print(f"    └─ {tc.get('name')}: {tc.get('args')}")
                else:
                    print(f"> [AI]: {msg.get('content', '')}")
            elif msg_type == "tool":
                print(f"> [Tool/{msg.get('name')}]: {msg.get('content', '')[:150]}...")

        print("=" * 60)
        print(f"Turns: {result['turns']}")
        print(f"\nAgent: {result['answer'][:500]}\n")


if __name__ == "__main__":
    main()
