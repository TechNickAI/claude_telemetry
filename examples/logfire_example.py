"""Example: Using claude_telemetry with Logfire.

This example shows how to use claude_telemetry with Logfire for enhanced
LLM telemetry visualization.

Prerequisites:
- Set LOGFIRE_TOKEN environment variable (from https://logfire.pydantic.dev)
- Set ANTHROPIC_API_KEY environment variable

Run:
    python examples/logfire_example.py
"""

import asyncio

from claude_telemetry import run_agent_with_telemetry


async def main():
    """Run agent with Logfire telemetry."""
    # When LOGFIRE_TOKEN is set, the package automatically configures Logfire
    # with proper LLM span formatting and tagging

    await run_agent_with_telemetry(
        prompt="List the Python files in the current directory and summarize them",
        system_prompt="You are a helpful coding assistant.",
        allowed_tools=["Bash", "Read"],
    )

    print("\n✅ Check your Logfire dashboard to see the telemetry!")
    print("   Spans will appear in the LLM UI with token visualization")


if __name__ == "__main__":
    asyncio.run(main())
