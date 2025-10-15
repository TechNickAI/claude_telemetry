"""Logfire-specific configuration."""

import sys

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider

from claude_telemetry.helpers.logger import logger


def configure_logfire(service_name: str = "claude-agents") -> TracerProvider:
    """
    Configure Logfire for telemetry.

    Args:
        service_name: Service name for traces

    Returns:
        Configured TracerProvider with Logfire
    """
    import os  # noqa: PLC0415

    try:
        import logfire  # noqa: PLC0415

        # Check token is present
        token = os.getenv("LOGFIRE_TOKEN")
        if not token:
            msg = "LOGFIRE_TOKEN environment variable is not set"
            raise ValueError(msg)  # noqa: TRY301

        # Configure Logfire with service name
        logfire.configure(
            service_name=service_name,
            send_to_logfire=True,
        )

        # Get the configured tracer provider
        provider = trace.get_tracer_provider()

        # Log the Logfire project URL
        logger.info(f"Logfire configured with service name: {service_name}")
        logger.info("Note: Token validation happens on first span export")

    except Exception:
        logger.exception("Failed to configure Logfire")
        raise
    else:
        return provider


def get_logfire():
    """
    Get the configured logfire instance.

    Returns the logfire module if it's been imported, None otherwise.
    This avoids global state by checking sys.modules.
    """
    return sys.modules.get("logfire")
