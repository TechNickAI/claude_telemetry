"""OpenTelemetry instrumentation for Claude agents."""

from importlib.metadata import version

__version__ = version("claude_telemetry")

# Async API (primary)
from .runner import run_agent_interactive, run_agent_with_telemetry

# Sync API (convenience wrappers)
from .sync import run_agent_interactive_sync, run_agent_with_telemetry_sync

# Configuration utilities
from .telemetry import configure_telemetry

__all__ = [
    "__version__",
    # Async API
    "run_agent_with_telemetry",
    "run_agent_interactive",
    # Sync API
    "run_agent_with_telemetry_sync",
    "run_agent_interactive_sync",
    # Configuration
    "configure_telemetry",
]
