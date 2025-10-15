"""Command-line interface for Claude Telemetry."""

import os
import sys
from pathlib import Path

import typer
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from claude_telemetry import __version__
from claude_telemetry.helpers.logger import configure_logger
from claude_telemetry.sync import (
    run_agent_interactive_sync,
    run_agent_with_telemetry_sync,
)

console = Console()

# Load environment variables from .env file
load_dotenv()


def handle_agent_error(e: Exception) -> None:
    """Handle agent execution errors consistently."""
    if isinstance(e, KeyboardInterrupt):
        console.print("\n[yellow]Interrupted by user[/yellow]")
        raise typer.Exit(0) from e
    if isinstance(e, RuntimeError):
        # Telemetry configuration errors - show them prominently
        console.print(f"\n[bold red]{e}[/bold red]\n")
        raise typer.Exit(1) from e
    # For other exceptions, show error and re-raise with context
    console.print(f"[red]Error: {e}[/red]")
    raise typer.Exit(1) from e


def parse_args() -> tuple[str | None, dict[str, str | None], bool]:  # noqa: PLR0915
    """
    Parse command line arguments.

    Returns:
        (prompt, extra_args, claudia_debug)
    """
    argv = sys.argv[1:]  # Skip program name

    # Handle special commands first
    if "version" in argv or "--version" in argv or "-v" in argv:
        console.print(f"claudia version {__version__}")
        sys.exit(0)

    if "config" in argv or "--config" in argv:
        show_config()
        sys.exit(0)

    if "--help" in argv or "-h" in argv:
        show_help()
        sys.exit(0)

    # Extract claudia-specific flags and separate extra args
    logfire_token = None
    otel_endpoint = None
    otel_headers = None
    claudia_debug = False
    extra_args_list = []

    i = 0
    while i < len(argv):
        arg = argv[i]

        if arg == "--logfire-token":
            logfire_token = argv[i + 1] if i + 1 < len(argv) else None
            i += 2
            continue
        elif arg == "--otel-endpoint":
            otel_endpoint = argv[i + 1] if i + 1 < len(argv) else None
            i += 2
            continue
        elif arg == "--otel-headers":
            otel_headers = argv[i + 1] if i + 1 < len(argv) else None
            i += 2
            continue
        elif arg == "--claudia-debug":
            claudia_debug = True
            i += 1
            continue

        # Everything else goes to extra_args_list
        extra_args_list.append(arg)
        i += 1

    # Set telemetry env vars
    if logfire_token:
        os.environ["LOGFIRE_TOKEN"] = logfire_token
    if otel_endpoint:
        os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = otel_endpoint
    if otel_headers:
        os.environ["OTEL_EXPORTER_OTLP_HEADERS"] = otel_headers
    if claudia_debug:
        os.environ["CLAUDE_TELEMETRY_DEBUG"] = "1"
        configure_logger(debug=True)

    # Find the prompt - it's the last standalone argument (not a flag or flag value)
    # Work backwards to find it
    prompt = None
    prompt_idx = -1

    for i in range(len(extra_args_list) - 1, -1, -1):
        arg = extra_args_list[i]

        if arg.startswith("-"):
            # This is a flag, keep looking
            continue

        # This is a non-flag argument
        # Check if it's a value for the previous flag
        if i > 0:
            prev_arg = extra_args_list[i - 1]
            # If previous arg is a flag without =, this is its value
            if prev_arg.startswith("-") and "=" not in prev_arg:
                continue

        # Found the prompt!
        prompt = arg
        prompt_idx = i
        break

    # Remove prompt from extra_args_list if found
    if prompt_idx >= 0:
        extra_args_list.pop(prompt_idx)

    # Parse extra_args into dict
    extra_args = _parse_flags(extra_args_list)

    return prompt, extra_args, claudia_debug


def _parse_flags(args: list[str]) -> dict[str, str | None]:
    """Parse flag arguments into a dict."""
    extra_args = {}
    i = 0

    while i < len(args):
        arg = args[i]

        if not arg.startswith("-"):
            # Standalone value - shouldn't happen if prompt was removed correctly
            i += 1
            continue

        # Handle --flag or -f
        if "=" in arg:
            # --flag=value or -f=value format
            flag_part, value_part = arg.split("=", 1)
            flag_name = flag_part.lstrip("-")
            extra_args[flag_name] = value_part
            i += 1
        else:
            # --flag value or --flag (boolean) format
            flag_name = arg.lstrip("-")

            # Check if next arg is a value (doesn't start with -)
            if i + 1 < len(args) and not args[i + 1].startswith("-"):
                extra_args[flag_name] = args[i + 1]
                i += 2
            else:
                # Boolean flag
                extra_args[flag_name] = None
                i += 1

    return extra_args


def show_help() -> None:
    """Show help message."""
    console.print("""
[bold]Usage:[/bold] claudia [OPTIONS] [PROMPT]

[bold]🤖 Claude agent with OpenTelemetry instrumentation[/bold]

Claudia is a thin wrapper around Claude CLI that adds telemetry.
All Claude CLI flags are supported - just pass them through.

[bold]Arguments:[/bold]
  PROMPT              Task for Claude to perform. If not provided, starts
                      interactive mode. The prompt should be the last argument.

[bold]Telemetry Options:[/bold]
  --logfire-token TEXT    Logfire API token (or set LOGFIRE_TOKEN env var)
  --otel-endpoint TEXT    OTEL endpoint URL
  --otel-headers TEXT     OTEL headers (format: key1=value1,key2=value2)
  --claudia-debug         Enable claudia debug output

[bold]Claude CLI Options (pass-through):[/bold]
  Any Claude CLI flag can be used. For best results, use --flag=value format.
  Examples:
    --permission-mode=bypassPermissions
    --model=opus
    --debug=api,hooks
  See 'claude --help' for full list

[bold]Commands:[/bold]
  version, --version, -v  Show version information
  config, --config        Show current configuration

[bold]Examples:[/bold]

  # Single prompt (recommended: use = for flags)
  claudia --permission-mode=bypassPermissions "fix this"

  # With specific model and Logfire telemetry
  claudia --model=opus --logfire-token YOUR_TOKEN "review my code"

  # Interactive mode
  claudia

  # Multiple flags
  claudia --model=opus --debug=api "analyze my code"

[bold]Note:[/bold] For flags that take values, the --flag=value format is recommended
to avoid ambiguity with the prompt argument.
    """)


def show_config() -> None:
    """Show current configuration and environment."""
    table = Table(title="Configuration", show_header=True)
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="green")
    table.add_column("Source", style="dim")

    # Check Logfire
    logfire_token = os.getenv("LOGFIRE_TOKEN")
    if logfire_token:
        table.add_row(
            "Logfire Token",
            f"{'*' * 8}...{logfire_token[-4:] if len(logfire_token) > 4 else '****'}",
            "Environment",
        )

    # Check OTEL
    otel_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    if otel_endpoint:
        table.add_row("OTEL Endpoint", otel_endpoint, "Environment")

    otel_headers = os.getenv("OTEL_EXPORTER_OTLP_HEADERS")
    if otel_headers:
        table.add_row("OTEL Headers", "***configured***", "Environment")

    # Check MCP config
    mcp_path = Path.cwd() / ".mcp.json"
    if mcp_path.exists():
        table.add_row("MCP Config", str(mcp_path), "File")
    else:
        table.add_row("MCP Config", "Not found", "N/A")

    console.print(table)


def show_startup_banner(extra_args: dict[str, str | None]) -> None:
    """Show a fancy startup banner."""
    # Create configuration table
    table = Table(show_header=False, box=None, padding=(0, 1))
    table.add_column("Key", style="cyan")
    table.add_column("Value", style="green")

    # Extract commonly used flags from extra_args
    model = extra_args.get("model") or extra_args.get("m")
    permission_mode = extra_args.get("permission-mode")

    table.add_row("Model", model or "Claude Code default")

    if permission_mode:
        table.add_row("Permission Mode", permission_mode)

    table.add_row("MCP", "Via Claude Code config")

    # Check telemetry backend
    if os.getenv("LOGFIRE_TOKEN"):
        table.add_row("Telemetry", "🔥 Logfire")
    elif os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"):
        table.add_row("Telemetry", "📊 OpenTelemetry")
    else:
        table.add_row("Telemetry", "⚠️  None (debug mode)")

    # Show banner
    console.print()
    console.print(
        Panel(
            "[bold cyan]Claude Telemetry Interactive Mode[/bold cyan]\n\n"
            "[dim]Type your prompts below. Use 'exit' or Ctrl+D to quit.[/dim]",
            title="🤖 Claudia",
            expand=False,
        )
    )
    console.print()
    console.print(table)
    console.print()


def main() -> None:
    """Main entry point."""
    prompt, extra_args, claudia_debug = parse_args()

    if claudia_debug:
        console.print(f"[dim]Debug: extra_args = {extra_args}[/dim]")

    # Determine mode
    use_interactive = prompt is None

    if use_interactive:
        # Show fancy startup banner
        show_startup_banner(extra_args)

        # Run interactive mode
        try:
            run_agent_interactive_sync(
                extra_args=extra_args,
                debug="debug" in extra_args or "d" in extra_args,
            )
        except Exception as e:
            handle_agent_error(e)

    else:
        # Single prompt mode
        try:
            run_agent_with_telemetry_sync(
                prompt=prompt,
                extra_args=extra_args,
                debug="debug" in extra_args or "d" in extra_args,
            )
        except Exception as e:
            handle_agent_error(e)


if __name__ == "__main__":
    main()
