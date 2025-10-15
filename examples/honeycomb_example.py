"""Example: Using claude_telemetry with Honeycomb.

This example shows how to configure Honeycomb specifically with claude_telemetry.

Prerequisites:
- Set ANTHROPIC_API_KEY environment variable
- Set HONEYCOMB_API_KEY environment variable (from https://honeycomb.io)

Run:
    python examples/honeycomb_example.py
"""

import asyncio
import os

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from claude_telemetry import run_agent_with_telemetry


def configure_honeycomb():
    """Configure OTEL for Honeycomb."""
    honeycomb_api_key = os.getenv("HONEYCOMB_API_KEY")
    if not honeycomb_api_key:
        msg = "HONEYCOMB_API_KEY environment variable not set"
        raise ValueError(msg)

    # Create tracer provider
    provider = TracerProvider()

    # Configure Honeycomb exporter
    honeycomb_exporter = OTLPSpanExporter(
        endpoint="https://api.honeycomb.io/v1/traces",
        headers={"x-honeycomb-team": honeycomb_api_key},
    )

    processor = BatchSpanProcessor(honeycomb_exporter)
    provider.add_span_processor(processor)

    trace.set_tracer_provider(provider)
    return provider


async def main():
    """Run agent with Honeycomb telemetry."""
    print("Configuring Honeycomb...")
    tracer_provider = configure_honeycomb()

    print("\nRunning agent with telemetry...")
    await run_agent_with_telemetry(
        prompt="Create a simple Python function to calculate fibonacci numbers",
        system_prompt="You are a helpful coding assistant.",
        allowed_tools=["Write"],
        tracer_provider=tracer_provider,
    )

    print("\n✅ Check your Honeycomb dashboard to see the telemetry!")
    print("   Look for traces in your dataset")


if __name__ == "__main__":
    asyncio.run(main())
