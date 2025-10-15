"""Synchronous wrappers for async functions."""

import asyncio

from opentelemetry.sdk.trace import TracerProvider

from claude_telemetry.runner import run_agent_interactive, run_agent_with_telemetry


def run_agent_with_telemetry_sync(
    prompt: str,
    system_prompt: str | None = None,
    model: str = "claude-3-5-sonnet-20241022",
    allowed_tools: list[str] | None = None,
    tracer_provider: TracerProvider | None = None,
) -> None:
    """
    Synchronous wrapper for run_agent_with_telemetry.

    This is a convenience function for users who prefer sync APIs.
    It uses asyncio.run() internally to execute the async version.

    Args:
        prompt: Task for Claude to perform
        system_prompt: System instructions for Claude
        model: Claude model to use
        allowed_tools: List of SDK tool names to allow
        tracer_provider: Optional custom tracer provider

    Returns:
        None - prints Claude's responses and sends telemetry

    Note:
        MCP servers configured via `claude mcp add` will be automatically available.

    Example:
        >>> from claude_telemetry import run_agent_with_telemetry_sync
        >>> run_agent_with_telemetry_sync(
        ...     "Analyze my Python files", allowed_tools=["Read", "Glob"]
        ... )
    """
    # Use asyncio.run() for Python 3.10+
    asyncio.run(
        run_agent_with_telemetry(
            prompt=prompt,
            system_prompt=system_prompt,
            model=model,
            allowed_tools=allowed_tools,
            tracer_provider=tracer_provider,
        )
    )


def run_agent_interactive_sync(
    system_prompt: str | None = None,
    model: str = "claude-3-5-sonnet-20241022",
    allowed_tools: list[str] | None = None,
    tracer_provider: TracerProvider | None = None,
) -> None:
    """
    Synchronous wrapper for interactive mode.

    Args:
        system_prompt: System instructions for Claude
        model: Claude model to use
        allowed_tools: List of SDK tool names to allow
        tracer_provider: Optional custom tracer provider

    Returns:
        None - runs interactive session

    Note:
        MCP servers configured via `claude mcp add` will be automatically available.

    Example:
        >>> from claude_telemetry import run_agent_interactive_sync
        >>> run_agent_interactive_sync(allowed_tools=["Read", "Write", "Bash"])
    """

    asyncio.run(
        run_agent_interactive(
            system_prompt=system_prompt,
            model=model,
            allowed_tools=allowed_tools,
            tracer_provider=tracer_provider,
        )
    )
