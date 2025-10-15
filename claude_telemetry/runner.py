"""Main agent runner with telemetry hooks."""

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient, HookMatcher
from opentelemetry.sdk.trace import TracerProvider
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from claude_telemetry.helpers.logger import logger
from claude_telemetry.hooks import TelemetryHooks
from claude_telemetry.telemetry import configure_telemetry


def extract_message_text(message) -> str:
    """
    Extract text content from Claude SDK message.

    Handles different message content types:
    - List of text blocks
    - String content
    - Other content types (converted to string)

    Args:
        message: Claude SDK message object

    Returns:
        Extracted text content or empty string
    """
    if not hasattr(message, "content"):
        return ""

    content = message.content

    if isinstance(content, list):
        # Extract text from list of blocks
        return "".join(block.text for block in content if hasattr(block, "text"))
    elif isinstance(content, str):
        return content
    else:
        # Fallback for other types
        return str(content)


async def run_agent_with_telemetry(
    prompt: str,
    extra_args: dict[str, str | None] | None = None,
    tracer_provider: TracerProvider | None = None,
    debug: bool = False,
) -> None:
    """
    Run a Claude agent with OpenTelemetry instrumentation.

    This is the main async entry point for the library.

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
    """
    if extra_args is None:
        extra_args = {}
    # Configure telemetry
    configure_telemetry(tracer_provider)

    # Initialize hooks
    hooks = TelemetryHooks()

    # Create hook configuration
    hook_config = {
        "UserPromptSubmit": [
            HookMatcher(matcher=None, hooks=[hooks.on_user_prompt_submit])
        ],
        "PreToolUse": [HookMatcher(matcher=None, hooks=[hooks.on_pre_tool_use])],
        "PostToolUse": [HookMatcher(matcher=None, hooks=[hooks.on_post_tool_use])],
        "MessageComplete": [
            HookMatcher(matcher=None, hooks=[hooks.on_message_complete])
        ],
        "PreCompact": [HookMatcher(matcher=None, hooks=[hooks.on_pre_compact])],
    }

    # Add debug flag if requested
    if debug and "debug" not in extra_args:
        extra_args["debug"] = None

    # Callback for stderr output from Claude CLI
    def log_claude_stderr(line: str) -> None:
        """Log Claude CLI stderr output for debugging."""
        if line.strip():
            logger.info(f"[Claude CLI] {line}")

    # Create agent options with hooks
    # Note: Don't pass mcp_servers - let Claude CLI use its own config
    # IMPORTANT: Must explicitly set setting_sources to load user/project/local settings
    # SDK defaults to isolated environment (no settings) when None.
    # We want CLI-like behavior, so explicitly request all sources.
    options = ClaudeAgentOptions(
        hooks=hook_config,
        setting_sources=["user", "project", "local"],
        extra_args=extra_args,
        stderr=log_claude_stderr if debug else None,
    )

    # Use async context manager for proper resource handling
    console = Console()
    try:
        async with ClaudeSDKClient(options=options) as client:
            # Send the query
            await client.query(prompt=prompt)

            # Receive and process responses
            async for message in client.receive_response():
                # Extract and display text content
                text = extract_message_text(message)
                if text:
                    console.print(text, end="")
    finally:
        # Always complete telemetry session, even on error
        if hooks.session_span:
            hooks.complete_session()


async def run_agent_interactive(  # noqa: PLR0915
    extra_args: dict[str, str | None] | None = None,
    tracer_provider: TracerProvider | None = None,
    debug: bool = False,
) -> None:
    """
    Run Claude agent in interactive mode.

    This function handles multiple prompts in a session with shared context.

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
    """
    if extra_args is None:
        extra_args = {}
    console = Console()

    # Configure telemetry once for the session
    configure_telemetry(tracer_provider)

    # This banner is now handled by CLI layer

    # Interactive loop
    session_metrics = {
        "total_input_tokens": 0,
        "total_output_tokens": 0,
        "total_tools_used": 0,
        "prompts_count": 0,
    }

    # Initialize hooks once for the session
    hooks = TelemetryHooks()

    # Add debug flag if requested
    if debug and "debug" not in extra_args:
        extra_args["debug"] = None

    # Callback for stderr output from Claude CLI
    def log_claude_stderr(line: str) -> None:
        """Log Claude CLI stderr output for debugging."""
        if line.strip():
            logger.info(f"[Claude CLI] {line}")

    # Create options with hooks
    # Note: Don't pass mcp_servers - let Claude CLI use its own config
    # IMPORTANT: Must explicitly set setting_sources to load user/project/local settings
    # SDK defaults to isolated environment (no settings) when None.
    # We want CLI-like behavior, so explicitly request all sources.
    options = ClaudeAgentOptions(
        setting_sources=["user", "project", "local"],
        extra_args=extra_args,
        stderr=log_claude_stderr if debug else None,
        hooks={
            "UserPromptSubmit": [
                HookMatcher(matcher=None, hooks=[hooks.on_user_prompt_submit])
            ],
            "PreToolUse": [HookMatcher(matcher=None, hooks=[hooks.on_pre_tool_use])],
            "PostToolUse": [HookMatcher(matcher=None, hooks=[hooks.on_post_tool_use])],
            "MessageComplete": [
                HookMatcher(matcher=None, hooks=[hooks.on_message_complete])
            ],
            "PreCompact": [HookMatcher(matcher=None, hooks=[hooks.on_pre_compact])],
        },
    )

    # Use async context manager for the session
    async with ClaudeSDKClient(options=options) as client:
        ctrl_c_count = 0
        try:
            while True:
                try:
                    # Get user input
                    user_input = input("\n> ")
                    ctrl_c_count = 0  # Reset on successful input

                    if user_input.lower() in ["exit", "quit", "bye"]:
                        break

                    if not user_input.strip():
                        continue

                    # Submit prompt and get response
                    console.print()  # Empty line for spacing

                    try:
                        # Send the query
                        await client.query(prompt=user_input)

                        # Receive responses
                        response_text = ""
                        async for message in client.receive_response():
                            text = extract_message_text(message)
                            if text:
                                response_text += text

                        # Display response with formatting
                        if response_text:
                            console.print(
                                Panel(
                                    Markdown(response_text),
                                    title="Claude",
                                    border_style="cyan",
                                )
                            )

                        # Update session metrics
                        session_metrics["prompts_count"] += 1

                    except Exception as e:
                        logger.exception(f"Error during prompt execution: {e}")
                        console.print(
                            f"[bold red]Error:[/bold red] {e}\n"
                            "[yellow]Continuing session...[/yellow]"
                        )
                        # Continue the interactive session instead of ending it
                        continue

                except KeyboardInterrupt:
                    ctrl_c_count += 1
                    if ctrl_c_count >= 2:
                        console.print("\n[yellow]Interrupted by user[/yellow]")
                        break
                    console.print(
                        "\n[yellow]Press Ctrl+C again to exit, or type 'exit'[/yellow]"
                    )
                    continue
                except EOFError:
                    break

        finally:
            # Complete telemetry session after ALL prompts
            if hooks.session_span:
                hooks.complete_session()

        # Show session summary
        console.print("\n" + "=" * 50)
        console.print(
            Panel.fit(
                f"[bold]Session Summary[/bold]\n"
                f"Prompts: {session_metrics['prompts_count']}\n"
                f"Total tokens: "
                f"{session_metrics['total_input_tokens'] + session_metrics['total_output_tokens']}",  # noqa: E501
                title="📊 Metrics",
                border_style="green",
            )
        )
        console.print("\nGoodbye! 👋")
