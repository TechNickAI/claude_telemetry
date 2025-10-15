"""Command-line interface for Claude Telemetry."""

import os
from pathlib import Path

import typer
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from typing import Annotated

from claude_telemetry import __version__
from claude_telemetry.helpers.logger import configure_logger
from claude_telemetry.sync import (
    run_agent_interactive_sync,
    run_agent_with_telemetry_sync,
)

console = Console()

# Load environment variables from .env file
load_dotenv()

# Create Typer app with settings to allow unknown options
app = typer.Typer(
    context_settings={"ignore_unknown_options": True, "allow_extra_args": True},
    add_completion=False,
    rich_markup_mode="rich",
    pretty_exceptions_enable=True,
)


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


def version_callback(value: bool) -> None:
    """Show version and exit."""
    if value:
        console.print(f"claudia version {__version__}")
        raise typer.Exit


def config_callback(value: bool) -> None:
    """Show config and exit."""
    if value:
        show_config()
        raise typer.Exit


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


def parse_claude_args(
    args: list[str] | None,
) -> tuple[str | None, dict[str, str | None]]:
    """
    Parse Claude CLI arguments into prompt and flags dict.

    Strategy:
    1. Last non-option argument is the prompt
    2. Parse flags:
       - `--flag=value` → {flag: value}
       - `--flag` followed by non-option → {flag: value}
       - `--flag` standalone → {flag: None}

    Args:
        args: Raw arguments from command line

    Returns:
        Tuple of (prompt, extra_args dict for Claude SDK)
    """
    if args is None or len(args) == 0:
        return None, {}

    # Find the last non-option argument (the prompt)
    prompt = None
    claude_args = list(args)

    for i in range(len(claude_args) - 1, -1, -1):
        if not claude_args[i].startswith("-"):
            prompt = claude_args.pop(i)
            break

    # Parse flags into dict for SDK
    extra_args = {}
    i = 0
    while i < len(claude_args):
        arg = claude_args[i]

        if "=" in arg:
            # --flag=value format
            key, value = arg.lstrip("-").split("=", 1)
            extra_args[key] = value
            i += 1
        elif i + 1 < len(claude_args) and not claude_args[i + 1].startswith("-"):
            # --flag value format (next arg is not a flag)
            extra_args[arg.lstrip("-")] = claude_args[i + 1]
            i += 2
        else:
            # --flag standalone (boolean flag)
            extra_args[arg.lstrip("-")] = None
            i += 1

    return prompt, extra_args


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


@app.command(
    context_settings={"ignore_unknown_options": True},
    help="""
    [bold]🤖 Claude agent with OpenTelemetry instrumentation[/bold]

    Claudia is a thin wrapper around Claude CLI that adds telemetry.
    All Claude CLI flags are supported - just pass them through.

    [bold]Examples:[/bold]

      # Single prompt (recommended: use = for flags)
      claudia --permission-mode=bypassPermissions "fix this"

      # With specific model and Logfire telemetry
      claudia --model=opus --logfire-token YOUR_TOKEN "review my code"

      # Interactive mode
      claudia

      # Multiple flags
      claudia --model=opus --debug=api "analyze my code"

    [bold]Note:[/bold] For flags that take values, the --flag=value format
    is recommended to avoid ambiguity with the prompt argument.
    """,
)
def main(
    args: Annotated[
        list[str],
        typer.Argument(help="Prompt and Claude CLI flags (all pass-through arguments)"),
    ] = None,
    logfire_token: Annotated[
        str | None,
        typer.Option(
            "--logfire-token",
            help="Logfire API token (or set LOGFIRE_TOKEN env var)",
            envvar="LOGFIRE_TOKEN",
        ),
    ] = None,
    otel_endpoint: Annotated[
        str | None,
        typer.Option(
            "--otel-endpoint",
            help="OTEL endpoint URL",
            envvar="OTEL_EXPORTER_OTLP_ENDPOINT",
        ),
    ] = None,
    otel_headers: Annotated[
        str | None,
        typer.Option(
            "--otel-headers",
            help="OTEL headers (format: key1=value1,key2=value2)",
            envvar="OTEL_EXPORTER_OTLP_HEADERS",
        ),
    ] = None,
    claudia_debug: Annotated[
        bool, typer.Option("--claudia-debug", help="Enable claudia debug output")
    ] = False,
    version: Annotated[
        bool | None,
        typer.Option(
            "--version",
            "-v",
            callback=version_callback,
            is_eager=True,
            help="Show version and exit",
        ),
    ] = None,
    config: Annotated[
        bool | None,
        typer.Option(
            "--config",
            callback=config_callback,
            is_eager=True,
            help="Show configuration and exit",
        ),
    ] = None,
) -> None:
    """Main CLI entry point."""
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

    # Parse arguments into prompt and Claude CLI flags
    prompt, extra_args = parse_claude_args(args)

    if claudia_debug:
        console.print(f"[dim]Debug: extra_args = {extra_args}[/dim]")
        console.print(f"[dim]Debug: prompt = {prompt}[/dim]")

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
    app()
