# Observability for Claude Code

[![CI](https://github.com/TechNickAI/claude_telemetry/actions/workflows/ci.yml/badge.svg)](https://github.com/TechNickAI/claude_telemetry/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

`claude_telemetry` wraps the Claude Code CLI with full observability. Every tool call,
token count, and cost flows to your OTEL backend as structured traces.

## The Problem

Claude Code works beautifully in your terminal. But when you run agents headless—in
CI/CD, cron jobs, production, or remote servers—you lose visibility into what's
happening. You can't see which tools were called, don't know token usage or costs, have
no context when debugging failures, and can't optimize without re-running locally.

Headless environments lack the rich console output you get during development.

## The Solution

`claude_telemetry` is a thin wrapper around the Claude Code CLI that adds observability.
It passes through all Claude Code flags unchanged while capturing execution traces.
Works with any OTEL backend—Logfire, Datadog, Honeycomb, Grafana. See exactly what
happened in production, debug remote failures without local reproduction, and track
costs to optimize expensive workflows.

Your agents become observable whether local or headless.

## Quick Start

The simplest way to add observability: swap `claude` for `claudia` on the command line.

```bash
# Before
claude code "Analyze my project and suggest improvements"

# After - same command, now with observability
claudia "Analyze my project and suggest improvements"
```

That's it. Every flag you use with `claude code` works with `claudia`. The behavior is
identical, but now you get full traces in your observability platform.

## For Developers

If you're already using `claude code` in your workflow, switching to `claudia` gives you
instant observability with zero behavior changes.

**Command-line usage:**

```bash
# Your existing workflow
claude code --model opus "Refactor this module"

# Same command, now observable
claudia --model opus "Refactor this module"
```

**In scripts and automation:**

```bash
#!/bin/bash
# CI/CD, cron jobs, or automation scripts

# Before - no visibility into what happened
claude code "Run tests and fix any failures"

# After - full traces in your observability platform
claudia "Run tests and fix any failures"
```

**The result:**

When you use `claudia`, you get the exact same output in your terminal as `claude code`.
But now your observability platform shows every tool call, token count, cost, and
timing. Debug headless failures, track production costs, and optimize expensive
workflows—all without changing how you work.

### Installation

```bash
# Basic installation - works with any OTEL backend
pip install claude_telemetry

# Or with Logfire support for enhanced LLM telemetry
pip install "claude_telemetry[logfire]"
```

### For Python Scripts

Add one line to your code:

```python
from claude_telemetry import run_agent_with_telemetry

# Instead of using Claude SDK directly, use this wrapper:
await run_agent_with_telemetry(
    prompt="Analyze my project and suggest improvements",
)
```

### Configure Your Backend

Same configuration for CLI and Python:

```bash
# For Logfire (get token from logfire.pydantic.dev)
export LOGFIRE_TOKEN="your-token"

# Or for any OTEL backend
export OTEL_EXPORTER_OTLP_ENDPOINT="https://your-otel-endpoint.com"
export OTEL_EXPORTER_OTLP_HEADERS="authorization=Bearer your-token"
```

That's it. Your agent's telemetry is now flowing to your observability platform.

## Usage Examples

### Headless/Production Use Case

The main use case: running agents in environments where you can't see console output.

```python
# In your CI/CD, cron job, or production script:
from claude_telemetry import run_agent_with_telemetry

await run_agent_with_telemetry(
    prompt="Analyze the latest logs and create a report",
    extra_args={"model": "sonnet"},
)
```

Your observability dashboard shows which tools were called, what errors occurred, how
many tokens were used, and the total cost of the operation.

### Local Development with Visibility

Even during local development, seeing traces helps you understand agent behavior:

```python
from claude_telemetry import run_agent_with_telemetry

# Your normal Claude Code workflow, now with observability
await run_agent_with_telemetry(
    prompt="Refactor the authentication module",
)
```

**With any OTEL backend:**

```python
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from claude_telemetry import run_agent_with_telemetry

# Configure your OTEL backend
provider = TracerProvider()
processor = BatchSpanProcessor(
    OTLPSpanExporter(
        endpoint="https://api.honeycomb.io/v1/traces",
        headers={"x-honeycomb-team": "your_api_key"},
    )
)
provider.add_span_processor(processor)
trace.set_tracer_provider(provider)

# Run with telemetry
await run_agent_with_telemetry(
    prompt="Your task here",
)
```

### CLI Usage

The `claudia` CLI passes all Claude Code flags through unchanged while adding
observability:

```bash
# Basic usage - just like `claude code`
claudia "Analyze my recent emails and create a summary"

# Pass any Claude Code flag
claudia --model opus "Refactor this module"
claudia --permission-mode bypassPermissions "Run the tests"
claudia --debug "Why is this failing?"

# Combine multiple flags - all forward to Claude Code
claudia --model haiku --permission-mode bypassPermissions "Quick task"
```

The `claudia` command accepts the same flags as `claude code`. It wraps the CLI with
telemetry hooks that capture execution without changing behavior. Configure your
observability backend via environment variables (same as library usage).

## What Gets Captured

Every agent run creates a full trace showing exactly what happened:

**Per execution:**

- 📝 Prompt and system instructions
- 🤖 Model used
- 🔢 Token counts (input/output/total)
- 💰 Cost in USD
- 🔧 Number of tool calls
- ⏱️ Execution time
- ❌ Any errors or failures

**Per tool call:**

- Tool name (Read, Write, Bash, etc.)
- Tool inputs
- Tool outputs
- Individual execution time
- Success/failure status

This gives you complete visibility into what your agent did, why it failed, and how much
it cost.

## Span Hierarchy

```
claude.agent.run (parent span)
  ├─ user.prompt (event)
  ├─ tool.read (child span)
  │   ├─ tool.input (attribute)
  │   └─ tool.output (attribute)
  ├─ tool.write (child span)
  │   ├─ tool.input (attribute)
  │   └─ tool.output (attribute)
  └─ agent.completed (event)
```

## Logfire Special Features

When using Logfire, the package enables LLM-specific UI features. Spans tagged with
`LLM` show in Logfire's LLM UI with request/response formatted for token visualization
and tool calls displayed as structured data. Enhanced formatting includes emoji
indicators (🤖 for agents, 🔧 for tools, ✅ for completion), proper nesting in console
output, and readable span titles showing task descriptions instead of generic "Message
with model X" text.

This happens automatically when `LOGFIRE_TOKEN` is set. With other backends, you get
standard OTEL spans.

## Configuration

### Environment Variables

**Logfire (easiest):**

```bash
export LOGFIRE_TOKEN="your_token"  # Get from logfire.pydantic.dev
```

**Any OTEL backend:**

```bash
export OTEL_EXPORTER_OTLP_ENDPOINT="https://your-endpoint.com/v1/traces"
export OTEL_EXPORTER_OTLP_HEADERS="authorization=Bearer your-token"
export OTEL_SERVICE_NAME="my-claude-agents"  # Optional, defaults to "claude-agents"
```

**Debug mode:**

```bash
export OTEL_DEBUG=1  # Verbose telemetry logging
```

### Programmatic Configuration

For more control, configure the tracer provider yourself:

```python
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from claude_telemetry import run_agent_with_telemetry

provider = TracerProvider()
# ... add your processors ...
trace.set_tracer_provider(provider)

# Pass it to the runner
await run_agent_with_telemetry(
    prompt="Your task",
    tracer_provider=provider,
)
```

### MCP Servers

MCP servers work the same way as with `claude code`. Configure them using
`claude mcp add`:

```bash
# Add an MCP server using Claude's config system
claude mcp add mcp-hubby --url https://connect.mcphubby.ai/mcp

# Or use project-local .mcp.json (same format as Claude Code)
# The wrapper loads user, project, and local settings automatically
```

The wrapper passes `setting_sources=["user", "project", "local"]` to the SDK, which
means it loads MCP servers from the same places `claude code` does. No special
configuration needed—if it works with `claude code`, it works with `claudia`.

**Need help with MCP servers?** Check out [MCP Hubby](https://mcphubby.ai)—a single
gateway to all your services (Gmail, Notion, Slack, etc.) that reduces context usage by
95%. One MCP connection instead of dozens.

## API

```python
async def run_agent_with_telemetry(
    prompt: str,
    extra_args: dict[str, str | None] | None = None,
    tracer_provider: TracerProvider | None = None,
    debug: bool = False,
)
```

**Parameters:**

- `prompt` - Task for Claude Code
- `extra_args` - Claude Code CLI flags as a dictionary. Any flag you can pass to
  `claude code` works here (e.g.,
  `{"model": "opus", "permission-mode": "bypassPermissions"}`)
- `tracer_provider` - Custom OTEL tracer provider (optional, auto-detected if not
  provided)
- `debug` - Enable Claude CLI debug mode

**Returns:**

- Nothing directly. Prints Claude's responses to console and sends all telemetry via
  OTEL.

**How it works:**

The function wraps the Claude Code SDK with observability hooks. It converts
`extra_args` to CLI flags and passes them through unchanged. The SDK runs exactly as if
you called `claude code` directly, but telemetry hooks capture every event.

**Example:**

```python
import asyncio
from claude_telemetry import run_agent_with_telemetry

async def main():
    # Any flag from `claude code --help` works in extra_args
    await run_agent_with_telemetry(
        prompt="List Python files and create a summary",
        extra_args={"model": "sonnet", "permission-mode": "bypassPermissions"},
    )

asyncio.run(main())
```

## How It Works

`claude_telemetry` is a thin observability layer around the Claude Code SDK. It uses the
SDK's hook system to capture execution without modifying behavior.

**Pass-through architecture:**

The `extra_args` dictionary passes directly to the Claude Code SDK as CLI flags. When
you call `run_agent_with_telemetry(prompt="...", extra_args={"model": "opus"})`, the SDK
receives exactly what `claude code --model opus` would pass. The library doesn't
interpret or validate flags—it forwards them unchanged. This means any flag that works
with `claude code` works here, including future flags not yet released.

**Observability hooks:**

- `UserPromptSubmit` - Opens parent span, logs prompt
- `PreToolUse` - Opens child span for tool, captures input
- `PostToolUse` - Captures output, closes tool span
- Session completion - Adds final metrics, closes parent span

Hooks are async callbacks that run during SDK execution. They capture telemetry data
without blocking or modifying the agent's behavior.

**OTEL export:**

- Spans sent via configured OTEL exporter
- Attributes follow semantic conventions where applicable
- Events add context without creating spans
- Works with any OTEL-compatible backend

**Logfire detection:**

- Checks for `LOGFIRE_TOKEN` environment variable
- If present, uses Logfire's Python SDK for auto-config
- Adds LLM-specific formatting and tags
- Falls back to standard OTEL if token not found

## Architecture Decisions

### Why Pass-Through Instead of Parameters?

Earlier versions exposed individual parameters like `model`, `allowed_tools`, etc. This
created maintenance burden—every new Claude Code flag required updating the wrapper's
signature. The pass-through architecture using `extra_args` eliminates this problem.

When you pass `extra_args={"model": "opus"}`, the library converts it to `--model opus`
and forwards it to the SDK unchanged. The library doesn't know what flags are valid—it
trusts the SDK to handle them. This means new Claude Code features work immediately
without updating `claude_telemetry`.

The CLI uses plain argument parsing to separate observability flags (`--logfire-token`,
`--otel-endpoint`) from Claude Code flags. Everything else passes through. This keeps
the wrapper thin and maintainable.

### Why OpenTelemetry?

OpenTelemetry is the industry standard for observability. Using it means the package
works with any observability backend, doesn't lock users into specific vendors,
integrates with existing infrastructure, and is future-proof as a CNCF project with wide
adoption.

### Why Special-Case Logfire?

Logfire has LLM-specific UI features that require specific span formatting. When Logfire
is detected, the package tags spans for LLM UI, formats request/response for token
visualization, and uses Logfire's SDK for optimal integration. This is additive—standard
OTEL still works, Logfire just gets enhanced features.

### Why Hooks Instead of Wrappers?

The Claude SDK provides hooks specifically for observability. Using them captures all
events without modifying SDK code, works across SDK updates, maintains clean separation
of concerns, and requires no monkey-patching.

## Supported Backends

**Tested and working:**

- Logfire (enhanced LLM features)
- Honeycomb
- Datadog
- Grafana Cloud
- Self-hosted OTEL collector

**Should work (standard OTEL):**

- New Relic
- Elastic APM
- AWS X-Ray
- Azure Monitor
- Any OTLP-compatible endpoint

## Console Output

Regardless of backend, console shows execution:

```
🤖 Analyze my recent emails and summarize them
  👤 User prompt submitted
  🔧 Calling tool: Read
  ✅ Tool completed: Read
  🔧 Calling tool: Write
  ✅ Tool completed: Write
  🎉 Agent completed

Session completed - Tokens: 145 in, 423 out, Tools called: 2
```

## Requirements

- Python 3.10 or later
- `claude-agent-sdk` - Claude Code integration
- `opentelemetry-api` - OTEL core
- `opentelemetry-sdk` - OTEL implementation
- `opentelemetry-exporter-otlp` - OTLP export
- `logfire` (optional) - Enhanced Logfire features

## Development

```bash
git clone https://github.com/TechNickAI/claude_telemetry.git
cd claude_telemetry
pip install -e ".[dev]"

# Run tests
pytest

# Run example with Logfire
export LOGFIRE_TOKEN="your_token"
python examples/logfire_example.py

# Run example with Honeycomb
export OTEL_EXPORTER_OTLP_ENDPOINT="https://api.honeycomb.io"
export OTEL_EXPORTER_OTLP_HEADERS="x-honeycomb-team=your_key"
python examples/otel_example.py
```

## Project Structure

```
claude_telemetry/
  claude_telemetry/
    __init__.py           # Package exports
    runner.py             # Async agent runner with observability hooks
    sync.py               # Sync wrapper for runner
    hooks.py              # Telemetry hook implementations
    telemetry.py          # OTEL configuration and setup
    logfire_adapter.py    # Logfire-specific enhancements
    cli.py                # CLI entry point with pass-through arg parsing
    helpers/              # Logger and utilities
  examples/
    logfire_example.py    # Logfire usage
    otel_example.py       # Generic OTEL usage
    honeycomb_example.py  # Honeycomb setup
  tests/
    test_telemetry.py     # Core telemetry tests
    test_cli_parsing.py   # CLI argument pass-through tests
    test_hooks.py         # Hook behavior tests
  pyproject.toml          # Package config
  README.md
  LICENSE
```

## Implementation Notes

### Logfire LLM Formatting

When Logfire is detected, spans need specific attributes for LLM UI:

```python
# Standard OTEL span
span.set_attribute("prompt", "...")
span.set_attribute("model", "...")

# Logfire LLM enhancement
span.set_attribute("request_data", {
    "model": "sonnet",
    "messages": [{"role": "user", "content": "..."}]
})
span.set_attribute("response_data", {
    "message": {"role": "assistant", "content": "..."},
    "usage": {"input_tokens": 123, "output_tokens": 456}
})
```

Logfire's UI parses these attributes to show token flow and LLM-specific visualizations.

### Hook Implementation

Hooks must be async and match the signature:

```python
async def on_user_prompt_submit(
    input_data: HookInput,
    tool_use_id: str | None,
    context: HookContext
) -> HookJSONOutput:
    # Open parent span
    # Log user prompt
    return {}  # Can return data to modify flow
```

Register hooks in SDK options:

```python
options = ClaudeAgentOptions(
    hooks={
        "UserPromptSubmit": [HookMatcher(matcher=None, hooks=[on_prompt])],
        "PreToolUse": [HookMatcher(matcher=None, hooks=[on_pre_tool])],
        "PostToolUse": [HookMatcher(matcher=None, hooks=[on_post_tool])],
    }
)
```

## FAQ & Troubleshooting

### Does `claudia` support all Claude Code flags?

Yes. The pass-through architecture means any flag that works with `claude code` works
with `claudia`. We don't maintain a list of supported flags—we just forward everything
to the SDK unchanged. This includes flags that don't exist yet. When Anthropic releases
new Claude Code features, they work immediately without updating `claude_telemetry`.

### Why not just use Logfire directly?

You can! But `claude_telemetry` works with any OTEL backend (not just Logfire), provides
pre-configured hooks for Claude agents specifically, captures LLM-specific metrics like
tokens, costs, and tool calls, and saves you setup time—no need to instrument everything
manually.

Use this if you want observability with minimal code changes.

### Does this add latency?

Negligible. Telemetry is async and doesn't block agent execution. Typical overhead:
<10ms per operation.

### What about streaming responses?

Fully supported! Streaming responses are captured and sent to telemetry after
completion.

### Common Issues

**No traces appearing:**

- Check your OTEL endpoint is reachable
- Verify environment variables are set
- Check console for error messages about telemetry connection

**Logfire LLM UI not showing:**

- Ensure `LOGFIRE_TOKEN` is set
- Install the `logfire` extra: `pip install "claude_telemetry[logfire]"`
- Check console for "Logfire project URL" to confirm connection

**Agent runs but no telemetry:**

- Make sure you're using `run_agent_with_telemetry()` wrapper
- Check that backend environment variables are set
- Try setting `OTEL_DEBUG=1` for verbose logging

**High costs showing in traces:**

- This is valuable data! Use it to optimize your prompts
- Consider using `haiku` model for cheaper operations
- Review which tools are being called unnecessarily

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Credits

Built for the 100x community.

Package name: `claude_telemetry` CLI name: `claudia`

Based on OpenTelemetry standards. Enhanced Logfire integration when available.
