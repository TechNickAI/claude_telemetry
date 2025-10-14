"""Command-line interface for Claude Telemetry."""

import logging
import os
from pathlib import Path

import typer
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from claude_telemetry import __version__
from claude_telemetry.sync import (
    run_agent_interactive_sync,
    run_agent_with_telemetry_sync,
)

app = typer.Typer(
    name="claudia",
    help="🤖 Claude agent with OpenTelemetry instrumentation",
    add_completion=False,
)

console = Console()

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    handlers=[logging.StreamHandler()],
)


@app.command()
def main(
    prompt: str | None = typer.Argument(
        None,
        help="Task for Claude to perform. If not provided, starts interactive mode.",
    ),
    model: str = typer.Option(
        "claude-3-5-sonnet-20241022",
        "--model",
        "-m",
        help="Claude model to use",
    ),
    system: str | None = typer.Option(
        None,
        "--system",
        "-s",
        help="System prompt for Claude",
    ),
    tools: list[str] | None = typer.Option(  # noqa: B008
        None,
        "--tool",
        "-t",
        help="SDK tools to allow (can specify multiple times)",
    ),
    no_mcp: bool = typer.Option(
        False,
        "--no-mcp",
        help="Disable MCP server loading from .mcp.json",
    ),
    interactive: bool = typer.Option(
        False,
        "--interactive",
        "-i",
        help="Force interactive mode even with a prompt",
    ),
    debug: bool = typer.Option(
        False,
        "--debug",
        help="Enable debug output to console",
    ),
    logfire_token: str | None = typer.Option(
        None,
        "--logfire-token",
        envvar="LOGFIRE_TOKEN",
        help="Logfire API token (or set LOGFIRE_TOKEN env var)",
    ),
    otel_endpoint: str | None = typer.Option(
        None,
        "--otel-endpoint",
        envvar="OTEL_EXPORTER_OTLP_ENDPOINT",
        help="OTEL endpoint URL",
    ),
    otel_headers: str | None = typer.Option(
        None,
        "--otel-headers",
        envvar="OTEL_EXPORTER_OTLP_HEADERS",
        help="OTEL headers (format: key1=value1,key2=value2)",
    ),
) -> None:
    """
    Run Claude with telemetry instrumentation.

    Examples:

        # Single prompt
        claudia "Analyze my Python files"

        # Interactive mode (no prompt)
        claudia

        # Interactive with custom model
        claudia -i --model claude-3-opus-20240229

        # With specific tools
        claudia "Fix the bug" -t Read -t Write -t Bash

        # With Logfire
        claudia "Help me refactor" --logfire-token YOUR_TOKEN

        # With custom OTEL backend
        claudia "Review my code" \\
            --otel-endpoint https://api.honeycomb.io \\
            --otel-headers "x-honeycomb-team=YOUR_KEY"
    """
    # Set environment variables if provided via CLI
    if logfire_token:
        os.environ["LOGFIRE_TOKEN"] = logfire_token

    if otel_endpoint:
        os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = otel_endpoint

    if otel_headers:
        os.environ["OTEL_EXPORTER_OTLP_HEADERS"] = otel_headers

    if debug:
        os.environ["CLAUDE_TELEMETRY_DEBUG"] = "1"
        logging.getLogger().setLevel(logging.DEBUG)

    # Determine mode
    use_interactive = interactive or prompt is None

    if use_interactive:
        # Show fancy startup banner
        _show_startup_banner(model, tools, not no_mcp)

        # Run interactive mode
        try:
            run_agent_interactive_sync(
                system_prompt=system,
                model=model,
                allowed_tools=tools,
                use_mcp=not no_mcp,
            )
        except KeyboardInterrupt:
            console.print("\n[yellow]Interrupted by user[/yellow]")
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
            raise typer.Exit(1) from e

    else:
        # Single prompt mode
        if not prompt:
            console.print("[red]Error: No prompt provided[/red]")
            raise typer.Exit(1)

        try:
            run_agent_with_telemetry_sync(
                prompt=prompt,
                system_prompt=system,
                model=model,
                allowed_tools=tools,
                use_mcp=not no_mcp,
            )
        except KeyboardInterrupt:
            console.print("\n[yellow]Interrupted by user[/yellow]")
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
            raise typer.Exit(1) from e


def _show_startup_banner(model: str, tools: list[str] | None, use_mcp: bool) -> None:
    """Show a fancy startup banner."""
    # Create configuration table
    table = Table(show_header=False, box=None, padding=(0, 1))
    table.add_column("Key", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Model", model)
    table.add_row("Tools", ", ".join(tools) if tools else "All available")
    table.add_row("MCP", "✅ Enabled" if use_mcp else "❌ Disabled")

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


@app.command("version")
def version() -> None:
    """Show version information."""
    console.print(f"claudia version {__version__}")


@app.command("config")
def config() -> None:
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

    # Note: Claude API key is managed by Claude Code internally

    console.print(table)


if __name__ == "__main__":
    app()
