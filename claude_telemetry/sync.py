"""Synchronous wrappers for async functions."""

import asyncio

from opentelemetry.sdk.trace import TracerProvider

from claude_telemetry.runner import run_agent_interactive, run_agent_with_telemetry


def run_agent_with_telemetry_sync(
    prompt: str,
    extra_args: dict[str, str | None] | None = None,
    tracer_provider: TracerProvider | None = None,
    debug: bool = False,
) -> None:
    """
    Synchronous wrapper for run_agent_with_telemetry.

    This is a convenience function for users who prefer sync APIs.
    It uses asyncio.run() internally to execute the async version.

    Args:
        prompt: Task for Claude to perform
        extra_args: Extra arguments to pass to Claude CLI
            (e.g., {"permission-mode": "bypassPermissions"})
        tracer_provider: Optional custom tracer provider
        debug: Enable Claude CLI debug mode (shows MCP errors and more)

    Returns:
        None - prints Claude's responses and sends telemetry

    Note:
        MCP servers configured via `claude mcp add` will be automatically available.
        Pass any Claude CLI flag via extra_args.

    Example:
        >>> from claude_telemetry import run_agent_with_telemetry_sync
        >>> run_agent_with_telemetry_sync(
        ...     "Analyze my Python files",
        ...     extra_args={"permission-mode": "bypassPermissions"},
        ... )
    """
    # Use asyncio.run() for Python 3.10+
    asyncio.run(
        run_agent_with_telemetry(
            prompt=prompt,
            extra_args=extra_args,
            tracer_provider=tracer_provider,
            debug=debug,
        )
    )


def run_agent_interactive_sync(
    extra_args: dict[str, str | None] | None = None,
    tracer_provider: TracerProvider | None = None,
    debug: bool = False,
) -> None:
    """
    Synchronous wrapper for interactive mode.

    Args:
        extra_args: Extra arguments to pass to Claude CLI
            (e.g., {"permission-mode": "bypassPermissions"})
        tracer_provider: Optional custom tracer provider
        debug: Enable Claude CLI debug mode (shows MCP errors and more)

    Returns:
        None - runs interactive session

    Note:
        MCP servers configured via `claude mcp add` will be automatically available.
        Pass any Claude CLI flag via extra_args.

    Example:
        >>> from claude_telemetry import run_agent_interactive_sync
        >>> run_agent_interactive_sync(
        ...     extra_args={"model": "opus", "permission-mode": "bypassPermissions"}
        ... )
    """

    asyncio.run(
        run_agent_interactive(
            extra_args=extra_args,
            tracer_provider=tracer_provider,
            debug=debug,
        )
    )
