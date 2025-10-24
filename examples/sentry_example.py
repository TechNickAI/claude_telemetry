"""Example: Using claude_telemetry with Sentry LLM Monitoring.

Demonstrates how to use claude_telemetry with Sentry for AI application
monitoring, combining LLM observability with Sentry's error tracking.

Prerequisites:
- Set SENTRY_DSN environment variable (from https://sentry.io)
- Set ANTHROPIC_API_KEY environment variable
- Install sentry-sdk: pip install sentry-sdk

Run:
    python examples/sentry_example.py
"""

import asyncio

from claude_telemetry import run_agent_with_telemetry


async def main():
    """Run agent with Sentry LLM monitoring."""
    # When SENTRY_DSN is set, the package automatically configures Sentry
    # with LLM-specific span formatting and attributes

    result = await run_agent_with_telemetry(
        prompt="List the Python files in the current directory and summarize them",
    )

    print("\n✅ Check your Sentry dashboard to see the LLM monitoring!")
    print("   Navigate to: Performance → AI Monitoring")
    print("   You'll see:")
    print("   - Full trace with token usage and costs")
    print("   - Tool execution spans with inputs/outputs")
    print("   - Gen AI attributes for filtering and analysis")

    return result


if __name__ == "__main__":
    asyncio.run(main())
