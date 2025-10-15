"""Centralized logger configuration for claude_telemetry."""

import os
import sys

from loguru import logger as _logger


def _configure_logger(debug: bool = False) -> None:
    """
    Configure loguru with clean formatting for telemetry output.

    Args:
        debug: Enable debug logging with full details
    """
    # Remove default handler
    _logger.remove()

    if debug or os.getenv("CLAUDE_TELEMETRY_DEBUG"):
        # Debug mode: show module and function for debugging
        _logger.add(
            sys.stderr,
            format="<dim>{name}:{function}</dim> - <level>{message}</level>",
            level="DEBUG",
        )
    else:
        # Normal mode: clean output for telemetry messages only
        _logger.add(
            sys.stderr,
            format="<level>{message}</level>",
            level="INFO",
            filter=lambda record: _should_show_message(record),
        )


def _should_show_message(record) -> bool:
    """
    Filter to only show important telemetry messages.

    Hide debug messages and internal library noise.
    """
    # Always hide debug messages in normal mode
    if record["level"].no < 20:  # INFO = 20
        return False

    # Hide MCP config INFO/WARNING messages (only show errors)
    # MCP config is internal details users don't need to see
    if "mcp" in record["name"]:
        return record["level"].no >= 40  # ERROR level or above

    # ALWAYS show hook messages - they're the core debugging info!
    if "hooks" in record["name"]:
        return True

    # Show everything else at INFO level or above
    return True


def configure_logger(debug: bool = False) -> None:
    """
    Public API to reconfigure the logger.

    Args:
        debug: Enable debug logging
    """
    _configure_logger(debug)


# Initialize logger on import with sensible defaults
debug_mode = os.getenv("CLAUDE_TELEMETRY_DEBUG", "").lower() in ("1", "true", "yes")
_configure_logger(debug=debug_mode)

# Export the configured logger
logger = _logger

__all__ = ["logger", "configure_logger"]
