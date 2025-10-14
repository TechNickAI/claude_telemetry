"""Main agent runner with telemetry hooks."""

import logging
from typing import List, Optional

from claude_agent_sdk import ClaudeAgent, ClaudeAgentOptions, HookMatcher
from opentelemetry.sdk.trace import TracerProvider

from claude_telemetry.hooks import TelemetryHooks
from claude_telemetry.mcp import load_mcp_config
from claude_telemetry.telemetry import configure_telemetry

logger = logging.getLogger(__name__)


async def run_agent_with_telemetry(
    prompt: str,
    system_prompt: Optional[str] = None,
    model: str = "claude-3-5-sonnet-20241022",
    allowed_tools: Optional[List[str]] = None,
    use_mcp: bool = True,
    tracer_provider: Optional[TracerProvider] = None,
) -> None:
    """
    Run a Claude agent with OpenTelemetry instrumentation.

    This is the main async entry point for the library.

    Args:
        prompt: Task for Claude to perform
        system_prompt: System instructions for Claude
        model: Claude model to use
        allowed_tools: List of SDK tool names to allow (e.g., ["Read", "Write", "Bash"])
        use_mcp: Whether to load MCP servers from .mcp.json
        tracer_provider: Optional custom tracer provider

    Returns:
        None - prints Claude's responses and sends telemetry
    """
    # Configure telemetry
    provider = configure_telemetry(tracer_provider)

    # Initialize hooks
    hooks = TelemetryHooks()

    # Create hook configuration
    hook_config = {
        "UserPromptSubmit": [
            HookMatcher(
                matcher=None,
                hooks=[hooks.on_user_prompt_submit],
            )
        ],
        "PreToolUse": [
            HookMatcher(
                matcher=None,
                hooks=[hooks.on_pre_tool_use],
            )
        ],
        "PostToolUse": [
            HookMatcher(
                matcher=None,
                hooks=[hooks.on_post_tool_use],
            )
        ],
        "MessageComplete": [
            HookMatcher(
                matcher=None,
                hooks=[hooks.on_message_complete],
            )
        ],
    }

    # Load MCP configuration if requested
    mcp_config = None
    if use_mcp:
        mcp_config = load_mcp_config()

    # Create agent options
    options = ClaudeAgentOptions(
        model=model,
        system_prompt=system_prompt or "You are a helpful assistant.",
        allowed_tools=allowed_tools,
        mcp_servers=mcp_config,
        hooks=hook_config,
    )

    # Create and run agent
    try:
        agent = ClaudeAgent(options=options)

        # Submit the prompt
        await agent.submit_prompt(prompt)

        # Wait for completion
        # The SDK handles the conversation loop internally

    finally:
        # Complete telemetry session
        hooks.complete_session()


async def run_agent_interactive(
    system_prompt: Optional[str] = None,
    model: str = "claude-3-5-sonnet-20241022",
    allowed_tools: Optional[List[str]] = None,
    use_mcp: bool = True,
    tracer_provider: Optional[TracerProvider] = None,
) -> None:
    """
    Run Claude agent in interactive mode.

    This function handles multiple prompts in a session with shared context.

    Args:
        system_prompt: System instructions for Claude
        model: Claude model to use
        allowed_tools: List of SDK tool names to allow
        use_mcp: Whether to load MCP servers from .mcp.json
        tracer_provider: Optional custom tracer provider

    Returns:
        None - runs interactive session
    """
    from prompt_toolkit import prompt
    from prompt_toolkit.history import FileHistory
    from rich.console import Console
    from rich.markdown import Markdown
    from rich.panel import Panel

    console = Console()

    # Configure telemetry once for the session
    provider = configure_telemetry(tracer_provider)

    # Load MCP configuration if requested
    mcp_config = None
    if use_mcp:
        mcp_config = load_mcp_config()

    # Create agent options
    options = ClaudeAgentOptions(
        model=model,
        system_prompt=system_prompt or "You are a helpful assistant.",
        allowed_tools=allowed_tools,
        mcp_servers=mcp_config,
    )

    # Create agent
    agent = ClaudeAgent(options=options)

    # Welcome message
    console.print(Panel.fit(
        "[bold green]Claude Telemetry Interactive Mode[/bold green]\n"
        f"Model: {model}\n"
        f"Tools: {', '.join(allowed_tools) if allowed_tools else 'None'}\n"
        "Type 'exit' or Ctrl+D to quit",
        title="🤖 Welcome",
    ))

    # Interactive loop
    history = FileHistory(".claudia_history")
    session_metrics = {
        "total_input_tokens": 0,
        "total_output_tokens": 0,
        "total_tools_used": 0,
        "prompts_count": 0,
    }

    try:
        while True:
            try:
                # Get user input with history
                user_input = prompt(
                    "\n> ",
                    history=history,
                    multiline=False,
                )

                if user_input.lower() in ["exit", "quit", "bye"]:
                    break

                if not user_input.strip():
                    continue

                # Initialize hooks for this prompt
                hooks = TelemetryHooks()

                # Add hooks to agent for this prompt
                agent.options.hooks = {
                    "UserPromptSubmit": [
                        HookMatcher(matcher=None, hooks=[hooks.on_user_prompt_submit])
                    ],
                    "PreToolUse": [
                        HookMatcher(matcher=None, hooks=[hooks.on_pre_tool_use])
                    ],
                    "PostToolUse": [
                        HookMatcher(matcher=None, hooks=[hooks.on_post_tool_use])
                    ],
                    "MessageComplete": [
                        HookMatcher(matcher=None, hooks=[hooks.on_message_complete])
                    ],
                }

                # Submit prompt and get response
                console.print()  # Empty line for spacing

                try:
                    response = await agent.submit_prompt(user_input)

                    # Display response with formatting
                    if response:
                        console.print(Panel(
                            Markdown(response),
                            title="Claude",
                            border_style="cyan",
                        ))

                    # Update session metrics
                    session_metrics["prompts_count"] += 1

                finally:
                    # Complete telemetry for this prompt
                    hooks.complete_session()

            except KeyboardInterrupt:
                console.print("\n[yellow]Use 'exit' to quit or Ctrl+D[/yellow]")
                continue
            except EOFError:
                break

    finally:
        # Show session summary
        console.print("\n" + "=" * 50)
        console.print(Panel.fit(
            f"[bold]Session Summary[/bold]\n"
            f"Prompts: {session_metrics['prompts_count']}\n"
            f"Total tokens: {session_metrics['total_input_tokens'] + session_metrics['total_output_tokens']}",
            title="📊 Metrics",
            border_style="green",
        ))
        console.print("\nGoodbye! 👋")