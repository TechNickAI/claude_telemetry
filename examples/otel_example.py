"""Example: Using claude_telemetry with generic OTEL backend.

This example shows how to configure any OTEL-compatible backend
(Honeycomb, Datadog, Grafana, etc.) with claude_telemetry.

Prerequisites:
- Set ANTHROPIC_API_KEY environment variable

Run:
    python examples/otel_example.py
"""

import asyncio

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

from claude_telemetry import run_agent_with_telemetry


def configure_otel_backend():
    """Configure OTEL with your backend of choice."""
    # Create tracer provider
    provider = TracerProvider()

    # Add console exporter for demonstration
    # (You'll see spans printed to console)
    console_processor = BatchSpanProcessor(ConsoleSpanExporter())
    provider.add_span_processor(console_processor)

    # Uncomment to add your actual OTEL backend:
    # from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    # otlp_processor = BatchSpanProcessor(
    #     OTLPSpanExporter(
    #         endpoint="https://your-otel-endpoint.com/v1/traces",
    #         headers={"Authorization": "Bearer your-api-key"},
    #     )
    # )
    # provider.add_span_processor(otlp_processor)

    trace.set_tracer_provider(provider)
    return provider


async def main():
    """Run agent with custom OTEL backend."""
    print("Configuring OTEL backend...")
    tracer_provider = configure_otel_backend()

    print("\nRunning agent with telemetry...")
    await run_agent_with_telemetry(
        prompt="What is 15 * 37? Show your calculation.",
        system_prompt="You are a helpful math assistant.",
        allowed_tools=["Bash"],
        tracer_provider=tracer_provider,
    )

    print("\n✅ Check your OTEL backend to see the telemetry!")


if __name__ == "__main__":
    asyncio.run(main())
