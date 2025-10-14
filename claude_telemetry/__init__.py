"""OpenTelemetry instrumentation for Claude agents."""

from importlib.metadata import version

__version__ = version("claude_telemetry")

# Main exports will go here once implemented
# from .runner import run_agent_with_telemetry
# from .telemetry import configure_telemetry

__all__ = [
    "__version__",
]
