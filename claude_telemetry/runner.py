"""Main agent runner with telemetry hooks."""

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient, HookMatcher
from opentelemetry.sdk.trace import TracerProvider
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from claude_telemetry.helpers.logger import logger
from claude_telemetry.hooks import TelemetryHooks
from claude_telemetry.telemetry import configure_telemetry


async def run_agent_with_telemetry(
    prompt: str,
    system_prompt: str | None = None,
    model: str | None = None,
    allowed_tools: list[str] | None = None,
    tracer_provider: TracerProvider | None = None,
    debug: bool = False,
) -> None:
    """
    Run a Claude agent with OpenTelemetry instrumentation.

    This is the main async entry point for the library.

    Args:
        prompt: Task for Claude to perform
        system_prompt: System instructions for Claude
        model: Claude model to use
        allowed_tools: List of SDK tool names to allow (e.g., ["Read", "Write", "Bash"])
        tracer_provider: Optional custom tracer provider
        debug: Enable Claude CLI debug mode (shows MCP errors and more)

    Returns:
        None - prints Claude's responses and sends telemetry

    Note:
        MCP servers configured via `claude mcp add` will be automatically available.
    """
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

    # Build extra CLI args
    extra_args = {}
    if debug:
        extra_args["debug"] = None  # Flag with no value

    # Callback for stderr output from Claude CLI
    def log_claude_stderr(line: str) -> None:
        """Log Claude CLI stderr output for debugging."""
        if line.strip():
            logger.info(f"[Claude CLI] {line}")

    # Create agent options with hooks
    # Note: Don't pass mcp_servers - let Claude CLI use its own config
    # IMPORTANT: Must explicitly set setting_sources to load user/project/local settings
    # SDK bug: passes --setting-sources="" when None, which blocks all settings
    options = ClaudeAgentOptions(
        system_prompt=system_prompt,
        allowed_tools=allowed_tools,
        hooks=hook_config,
        setting_sources=["user", "project", "local"],
        extra_args=extra_args,
        stderr=log_claude_stderr if debug else None,
    )

    # Add model only if specified
    if model:
        options.model = model

    # Use async context manager for proper resource handling
    try:
        async with ClaudeSDKClient(options=options) as client:
            # Send the query
            await client.query(prompt=prompt)

            # Receive and process responses
            response_text = ""
            async for message in client.receive_response():
                # Handle different message types
                if hasattr(message, "content"):
                    # Extract text from content (could be a list of TextBlocks)
                    if isinstance(message.content, list):
                        for block in message.content:
                            if hasattr(block, "text"):
                                response_text += block.text
                                # Output to console for user
                                console = Console()
                                console.print(block.text, end="")
                    elif isinstance(message.content, str):
                        response_text = message.content
                        # Output to console for user
                        console = Console()
                        console.print(message.content, end="")
    finally:
        # Always complete telemetry session, even on error
        if hooks.session_span:
            hooks.complete_session()


async def run_agent_interactive(  # noqa: PLR0915
    system_prompt: str | None = None,
    model: str | None = None,
    allowed_tools: list[str] | None = None,
    tracer_provider: TracerProvider | None = None,
    debug: bool = False,
) -> None:
    """
    Run Claude agent in interactive mode.

    This function handles multiple prompts in a session with shared context.

    Args:
        system_prompt: System instructions for Claude
        model: Claude model to use
        allowed_tools: List of SDK tool names to allow
        tracer_provider: Optional custom tracer provider
        debug: Enable Claude CLI debug mode (shows MCP errors and more)

    Returns:
        None - runs interactive session

    Note:
        MCP servers configured via `claude mcp add` will be automatically available.
    """
    console = Console()

    # Configure telemetry once for the session
    configure_telemetry(tracer_provider)

    # Welcome message
    model_info = f"Model: {model}\n" if model else ""
    console.print(
        Panel.fit(
            "[bold green]Claude Telemetry Interactive Mode[/bold green]\n"
            f"{model_info}"
            f"Tools: {', '.join(allowed_tools) if allowed_tools else 'None'}\n"
            "Type 'exit' or Ctrl+D to quit",
            title="🤖 Welcome",
        )
    )

    # Interactive loop
    session_metrics = {
        "total_input_tokens": 0,
        "total_output_tokens": 0,
        "total_tools_used": 0,
        "prompts_count": 0,
    }

    # Initialize hooks once for the session
    hooks = TelemetryHooks()

    # Build extra CLI args
    extra_args = {}
    if debug:
        extra_args["debug"] = None  # Flag with no value

    # Callback for stderr output from Claude CLI
    def log_claude_stderr(line: str) -> None:
        """Log Claude CLI stderr output for debugging."""
        if line.strip():
            logger.info(f"[Claude CLI] {line}")

    # Create options with hooks
    # Note: Don't pass mcp_servers - let Claude CLI use its own config
    # IMPORTANT: Must explicitly set setting_sources to load user/project/local settings
    # SDK bug: passes --setting-sources="" when None, which blocks all settings
    options = ClaudeAgentOptions(
        system_prompt=system_prompt,
        allowed_tools=allowed_tools,
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

    # Add model only if specified
    if model:
        options.model = model

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
                            if hasattr(message, "content"):
                                # Extract text from content
                                if isinstance(message.content, list):
                                    for block in message.content:
                                        if hasattr(block, "text"):
                                            response_text += block.text
                                elif isinstance(message.content, str):
                                    response_text = message.content
                                else:
                                    response_text = str(message.content)

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
