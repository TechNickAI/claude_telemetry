"""Example: Interactive agent mode with telemetry.

This example shows how to use the interactive mode where you can have
a back-and-forth conversation with Claude, with full telemetry capture.

Prerequisites:
- Set ANTHROPIC_API_KEY environment variable
- Optionally set LOGFIRE_TOKEN for enhanced telemetry

Run:
    python examples/interactive_example.py
"""

import asyncio

from claude_telemetry import run_agent_interactive


async def main():
    """Run agent in interactive mode."""
    print("Starting interactive Claude session with telemetry...")
    print("Type 'exit', 'quit', or press Ctrl+C to end the session\n")

    await run_agent_interactive(
        system_prompt="You are a helpful coding assistant. Be concise but thorough.",
        allowed_tools=["Read", "Write", "Bash"],
    )

    print("\n✅ Session ended. Check your telemetry backend for the full conversation!")


if __name__ == "__main__":
    asyncio.run(main())
