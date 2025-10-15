"""OpenTelemetry configuration and setup for Claude agents."""

import asyncio
import os

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

from claude_telemetry.helpers.logger import logger


def configure_telemetry(
    tracer_provider: TracerProvider | None = None,
    service_name: str = "claude-agents",
) -> TracerProvider:
    """
    Configure OpenTelemetry for Claude agent tracing.

    Priority order:
    1. Provided tracer_provider
    2. Logfire (if LOGFIRE_TOKEN is set)
    3. OTEL environment variables
    4. No-op tracer (telemetry disabled)

    Args:
        tracer_provider: Optional custom tracer provider
        service_name: Service name for traces

    Returns:
        Configured TracerProvider
    """
    # Use provided tracer if given
    if tracer_provider:
        trace.set_tracer_provider(tracer_provider)
        logger.info("✅ Using provided tracer provider")
        return tracer_provider

    # Check if a real TracerProvider has already been configured
    # (not just the default ProxyTracerProvider)
    existing = trace.get_tracer_provider()
    if isinstance(existing, TracerProvider) and not isinstance(
        existing, trace.NoOpTracerProvider
    ):
        logger.debug("Using existing tracer provider")
        return existing

    # Check for Logfire configuration
    if os.getenv("LOGFIRE_TOKEN"):
        try:
            from claude_telemetry.logfire_adapter import configure_logfire  # noqa: PLC0415

            provider = configure_logfire(service_name)
            logger.info(
                "🔥 Logfire telemetry configured → https://logfire.pydantic.dev/"
            )
            return provider  # noqa: TRY300
        except ImportError as e:
            logger.error("❌ LOGFIRE_TOKEN set but logfire not installed!")
            logger.error("   Run: pip install logfire")
            raise RuntimeError(
                "Logfire token provided but logfire package not installed"
            ) from e
        except Exception as e:
            logger.error(f"❌ Failed to configure Logfire: {e}")
            logger.error(
                "   Check your LOGFIRE_TOKEN is valid at https://logfire.pydantic.dev/"
            )
            raise RuntimeError(f"Failed to configure Logfire telemetry: {e}") from e

    # Check for OTEL configuration
    otel_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    if otel_endpoint:
        try:
            provider = _configure_otel(otel_endpoint, service_name)
            logger.info(f"📊 OpenTelemetry configured → {otel_endpoint}")
            return provider  # noqa: TRY300
        except Exception as e:
            logger.error(f"❌ Failed to configure OTEL: {e}")
            logger.error(f"   Check endpoint is reachable: {otel_endpoint}")
            raise RuntimeError(f"Failed to configure OTEL telemetry: {e}") from e

    # No configuration found - use console exporter for debugging
    if os.getenv("CLAUDE_TELEMETRY_DEBUG"):
        logger.info("🔍 Debug mode: telemetry output to console")
        return _configure_console_exporter(service_name)

    # No telemetry backend configured - FAIL LOUDLY
    error_msg = """
❌ NO TELEMETRY BACKEND CONFIGURED!

This package exists to provide telemetry - it cannot function without a backend.

Configure one of the following:

1. Logfire (recommended for LLM observability):
   export LOGFIRE_TOKEN="your_token_here"
   pip install "claude_telemetry[logfire]"

2. Any OTEL backend:
   export OTEL_EXPORTER_OTLP_ENDPOINT="https://api.honeycomb.io"
   export OTEL_EXPORTER_OTLP_HEADERS="x-honeycomb-team=your_key"

3. Debug mode (console output only):
   export CLAUDE_TELEMETRY_DEBUG=1

See https://github.com/TechNickAI/claude_telemetry for more details.
"""
    logger.error(error_msg)
    raise RuntimeError(
        "No telemetry backend configured - cannot proceed without telemetry"
    )


def _configure_otel(endpoint: str, service_name: str) -> TracerProvider:
    """Configure standard OTEL exporter."""
    resource = Resource.create({"service.name": service_name})

    # Parse headers from environment
    headers = {}
    headers_env = os.getenv("OTEL_EXPORTER_OTLP_HEADERS", "")
    if headers_env:
        for header in headers_env.split(","):
            if "=" in header:
                key, value = header.split("=", 1)
                headers[key.strip()] = value.strip()

    # Create OTLP exporter
    exporter = OTLPSpanExporter(
        endpoint=endpoint
        if endpoint.endswith("/v1/traces")
        else f"{endpoint}/v1/traces",
        headers=headers,
    )

    # Create and configure tracer provider
    provider = TracerProvider(resource=resource)
    processor = BatchSpanProcessor(exporter)
    provider.add_span_processor(processor)

    # Set as global tracer
    trace.set_tracer_provider(provider)

    return provider


def _configure_console_exporter(service_name: str) -> TracerProvider:
    """Configure console exporter for debugging."""
    resource = Resource.create({"service.name": service_name})

    provider = TracerProvider(resource=resource)
    processor = BatchSpanProcessor(ConsoleSpanExporter())
    provider.add_span_processor(processor)

    trace.set_tracer_provider(provider)

    return provider


def safe_span_operation(operation):
    """
    Decorator to safely execute telemetry operations without blocking.

    Telemetry failures should NEVER block agent execution.
    """

    def wrapper(*args, **kwargs):
        try:
            return operation(*args, **kwargs)
        except Exception as e:
            logger.warning(f"Telemetry operation failed (ignored): {e}")
            return None

    async def async_wrapper(*args, **kwargs):
        try:
            return await operation(*args, **kwargs)
        except Exception as e:
            logger.warning(f"Telemetry operation failed (ignored): {e}")
            return None

    # Return appropriate wrapper based on function type
    if asyncio.iscoroutinefunction(operation):
        return async_wrapper
    return wrapper
