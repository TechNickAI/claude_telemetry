# claude-telemetry

[![CI](https://github.com/TechNickAI/claude-telemetry/actions/workflows/ci.yml/badge.svg)](https://github.com/TechNickAI/claude-telemetry/actions/workflows/ci.yml)
[![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

OpenTelemetry instrumentation for Claude agents.

Captures every prompt, tool call, token count, and cost as structured OTEL spans. Send
traces to any observability backend: Logfire, Datadog, Honeycomb, Grafana, or your own
collector.

## Installation

```bash
pip install git+https://github.com/TechNickAI/claude-telemetry.git
```

## Usage

**With Logfire (automatic configuration):**

```python
from claude_telemetry import run_agent_with_telemetry

await run_agent_with_telemetry(
    prompt="Analyze my recent emails and summarize them",
    system_prompt="You are a helpful email assistant.",
    allowed_tools=["Read", "Write"],
)
```

Set `LOGFIRE_TOKEN` as an environment variable. The package auto-configures Logfire with
proper LLM span formatting.

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
    system_prompt="Your instructions",
)
```

**From the command line:**

```bash
claudia "Analyze my recent emails"
```

The CLI uses Logfire by default. Configure other backends via OTEL environment
variables.

## What Gets Captured

Every agent execution creates one parent span containing:

**Span attributes:**

- `prompt` - The task given to Claude
- `model` - Claude model used
- `input_tokens` - Tokens sent to Claude
- `output_tokens` - Tokens generated
- `total_tokens` - Complete count
- `cost_usd` - Execution cost
- `tools_used` - Number of tool calls
- `turns` - Conversation rounds

**Child spans for each tool:**

- Tool name
- Tool inputs (as attributes)
- Tool outputs (as attributes)
- Execution time

**Events within spans:**

- User prompt submitted
- Tool calling started
- Tool completed
- Agent finished

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

When using Logfire, the package enables LLM-specific UI features:

**LLM span tagging:**

- Spans tagged with `LLM` show in Logfire's LLM UI
- Request/response formatted for token visualization
- Tool calls displayed as structured data

**Enhanced formatting:**

- Emoji indicators (🤖 for agents, 🔧 for tools, ✅ for completion)
- Proper nesting in console output
- Readable span titles (task description, not "Message with model X")

This happens automatically when `LOGFIRE_TOKEN` is set. With other backends, you get
standard OTEL spans.

## Configuration

### Logfire (default)

```bash
export LOGFIRE_TOKEN="your_token_here"
```

The package detects the token and configures:

- EU region endpoint (or US via `LOGFIRE_BASE_URL`)
- LLM span formatting
- Proper attribute structure for Logfire's UI

### Other OTEL Backends

Configure via standard OTEL environment variables:

```bash
export OTEL_EXPORTER_OTLP_ENDPOINT="https://api.honeycomb.io"
export OTEL_EXPORTER_OTLP_HEADERS="x-honeycomb-team=your_key"
export OTEL_SERVICE_NAME="claude-agents"
```

Or programmatically (see Usage section above).

### MCP Servers

Place `.mcp.json` in your project root:

```json
{
  "mcpServers": {
    "mcp-hubby": {
      "url": "https://connect.mcphubby.ai/mcp",
      "transport": "http",
      "headers": {
        "Authorization": "Bearer YOUR_TOKEN"
      }
    },
    "local-tools": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem"]
    }
  }
}
```

Both HTTP and stdio MCP servers are supported. The package converts your config to SDK
format automatically.

## API

```python
async def run_agent_with_telemetry(
    prompt: str,
    system_prompt: Optional[str] = None,
    model: str = "claude-3-5-sonnet-20241022",
    allowed_tools: Optional[List[str]] = None,
    use_mcp: bool = True,
    tracer_provider: Optional[TracerProvider] = None,
)
```

**Parameters:**

- `prompt` - Task for Claude
- `system_prompt` - System instructions
- `model` - Claude model (default: claude-3-5-sonnet-20241022)
- `allowed_tools` - SDK tool names (e.g., `["Read", "Write", "Bash"]`)
- `use_mcp` - Load MCP servers from `.mcp.json` (default: True)
- `tracer_provider` - Custom OTEL tracer provider (optional, auto-detected if not
  provided)

**Returns:**

- Nothing directly. Prints Claude's responses to console and sends all telemetry via
  OTEL.

**Example:**

```python
import asyncio
from claude_telemetry import run_agent_with_telemetry

async def main():
    await run_agent_with_telemetry(
        prompt="List Python files and create a summary",
        system_prompt="You are a helpful coding assistant.",
        allowed_tools=["Bash", "Glob", "Write"],
        use_mcp=False,
    )

asyncio.run(main())
```

## How It Works

The package uses Claude SDK's hook system to capture execution:

**Hooks registered:**

- `UserPromptSubmit` - Opens parent span, logs prompt
- `PreToolUse` - Opens child span for tool, captures input
- `PostToolUse` - Captures output, closes tool span
- Session completion - Adds final metrics, closes parent span

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

### Why OpenTelemetry?

OpenTelemetry is the industry standard for observability. Using it means:

- Works with any observability backend
- Doesn't lock users into specific vendors
- Integrates with existing infrastructure
- Future-proof (CNCF project with wide adoption)

### Why Special-Case Logfire?

Logfire has LLM-specific UI features that require specific span formatting. When Logfire
is detected, the package:

- Tags spans for LLM UI
- Formats request/response for token visualization
- Uses Logfire's SDK for optimal integration

This is additive - standard OTEL still works, Logfire just gets enhanced features.

### Why Hooks Instead of Wrappers?

The Claude SDK provides hooks specifically for observability. Using them:

- Captures all events without modifying SDK code
- Works across SDK updates
- Clean separation of concerns
- No monkey-patching required

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
git clone https://github.com/TechNickAI/claude-telemetry.git
cd claude-telemetry
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
claude-telemetry/
  claude_telemetry/
    __init__.py           # Package exports
    runner.py             # Main agent runner with hooks
    telemetry.py          # OTEL configuration and setup
    logfire_adapter.py    # Logfire-specific enhancements
    cli.py                # CLI entry point (claudia command)
  examples/
    logfire_example.py    # Logfire usage
    otel_example.py       # Generic OTEL usage
    honeycomb_example.py  # Honeycomb setup
  tests/
    test_telemetry.py     # Core telemetry tests
    test_logfire.py       # Logfire integration tests
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
    "model": "claude-3-5-sonnet-20241022",
    "messages": [{"role": "user", "content": "..."}]
})
span.set_attribute("response_data", {
    "message": {"role": "assistant", "content": "..."},
    "usage": {"input_tokens": 123, "output_tokens": 456}
})
```

Logfire's UI parses these attributes to show token flow and LLM-specific visualizations.

### MCP Server Loading

The package needs to convert `.mcp.json` format to Claude SDK format:

```python
# User's .mcp.json
{
  "mcpServers": {
    "mcp-hubby": {
      "transport": "http",  # User format
      "url": "...",
      "headers": {...}
    }
  }
}

# Convert to SDK format
{
  "mcp-hubby": {
    "type": "http",  # SDK format
    "url": "...",
    "headers": {...}
  }
}
```

Key conversion: `transport` → `type`

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

## Troubleshooting

**No traces appearing:**

Check your OTEL configuration. Verify the endpoint and credentials. Test with a simple
OTEL example first to confirm backend connectivity.

**Logfire LLM UI not showing:**

Ensure `LOGFIRE_TOKEN` is set. The package must detect it to enable LLM formatting.
Check console for "Logfire project URL" to confirm connection.

**MCP servers not loading:**

Validate `.mcp.json` syntax. Ensure `transport` field is present for HTTP servers. Check
MCP server health: `claude mcp list`

**Tool calls missing from traces:**

Verify tools are enabled via `allowed_tools` or `use_mcp=True`. Check console output to
confirm tools are being called.

## License

MIT License

## Credits

Built for the 100x community.

Package name: `claude-telemetry` CLI name: `claudia`

Based on OpenTelemetry standards. Enhanced Logfire integration when available.
