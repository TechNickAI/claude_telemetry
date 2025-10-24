"""Sentry-specific configuration for LLM monitoring."""

import os
import sys

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider

from claude_telemetry.helpers.logger import logger


def configure_sentry(service_name: str = "claude-agents") -> TracerProvider:
    """
    Configure Sentry for LLM telemetry.

    Uses Sentry's native SDK for initialization and OpenTelemetry API for
    span creation. This provides full access to Sentry's LLM monitoring UI
    while maintaining consistency with other backends.

    Args:
        service_name: Service name for traces

    Returns:
        Configured TracerProvider with Sentry integration

    Environment Variables:
        SENTRY_DSN: Sentry project DSN (required)
        SENTRY_ENVIRONMENT: Environment name (default: "production")
        SENTRY_TRACES_SAMPLE_RATE: Trace sampling rate 0.0-1.0 (default: "1.0")
    """
    try:
        import sentry_sdk  # noqa: PLC0415
        from sentry_sdk.integrations.logging import LoggingIntegration  # noqa: PLC0415
        from sentry_sdk.integrations.opentelemetry import (  # noqa: PLC0415
            SentrySpanProcessor,
        )

        # Check DSN is present
        dsn = os.getenv("SENTRY_DSN")
        if not dsn:
            msg = "SENTRY_DSN environment variable is not set"
            raise ValueError(msg)  # noqa: TRY301

        # Parse configuration from environment
        environment = os.getenv("SENTRY_ENVIRONMENT", "production")
        traces_sample_rate = float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "1.0"))

        # Initialize Sentry SDK with LLM monitoring optimizations
        sentry_sdk.init(
            dsn=dsn,
            traces_sample_rate=traces_sample_rate,
            environment=environment,
            send_default_pii=False,  # Privacy: don't send PII by default
            enable_tracing=True,
            integrations=[
                LoggingIntegration(
                    level=None,  # Capture no logs by default
                    event_level=None,  # Only capture errors via spans
                ),
            ],
        )

        # Create OpenTelemetry provider with Sentry processor
        resource = Resource.create({"service.name": service_name})
        provider = TracerProvider(resource=resource)

        # Add Sentry span processor to bridge OTEL spans to Sentry
        provider.add_span_processor(SentrySpanProcessor())

        # Set as global tracer provider
        trace.set_tracer_provider(provider)

        logger.info(f"Sentry configured with service name: {service_name}")
        logger.info(f"Environment: {environment}")
        logger.info("Note: Traces will appear in Sentry's AI Monitoring section")

    except ImportError as e:
        logger.error("❌ SENTRY_DSN set but sentry-sdk not installed!")
        logger.error("   Run: pip install sentry-sdk")
        raise RuntimeError(
            "Sentry DSN provided but sentry-sdk package not installed"
        ) from e
    except Exception:
        logger.exception("Failed to configure Sentry")
        raise
    else:
        return provider


def get_sentry():
    """
    Get the configured Sentry SDK instance.

    Returns the sentry_sdk module if it's been imported, None otherwise.
    This avoids global state by checking sys.modules.
    """
    return sys.modules.get("sentry_sdk")
