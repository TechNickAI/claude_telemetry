"""OpenTelemetry instrumentation for Claude agents."""

from importlib.metadata import version

from dotenv import load_dotenv

# Load .env file FIRST - before anything else imports and configures
load_dotenv()

# Configure logger early (import triggers configuration)
from .helpers import logger  # noqa: F401, E402

# Async API (primary)
from .runner import run_agent_interactive, run_agent_with_telemetry  # noqa: E402

# Sync API (convenience wrappers)
from .sync import (  # noqa: E402
    run_agent_interactive_sync,
    run_agent_with_telemetry_sync,
)

# Configuration utilities
from .telemetry import configure_telemetry  # noqa: E402

__version__ = version("claude_telemetry")

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
