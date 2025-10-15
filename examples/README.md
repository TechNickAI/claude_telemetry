# Examples

This directory contains examples showing how to use `claude_telemetry` with different
backends and configurations.

## Examples

### Basic Usage

- **[logfire_example.py](logfire_example.py)** - Using with Logfire for enhanced LLM
  telemetry
- **[otel_example.py](otel_example.py)** - Using with generic OTEL backend
- **[honeycomb_example.py](honeycomb_example.py)** - Using with Honeycomb specifically
- **[interactive_example.py](interactive_example.py)** - Interactive conversation mode

## Prerequisites

All examples require:

```bash
export ANTHROPIC_API_KEY="your-api-key"
```

For Logfire example:

```bash
export LOGFIRE_TOKEN="your-logfire-token"
```

For Honeycomb example:

```bash
export HONEYCOMB_API_KEY="your-honeycomb-api-key"
```

## Running Examples

```bash
# Install the package first
pip install claude_telemetry

# Or install from source
pip install -e .

# Run any example
python examples/logfire_example.py
python examples/otel_example.py
python examples/honeycomb_example.py
python examples/interactive_example.py
```

## What to Expect

Each example will:

1. Configure telemetry (either Logfire or custom OTEL backend)
2. Run a Claude agent with a specific task
3. Capture all telemetry (prompts, tool calls, tokens, costs)
4. Send telemetry to your configured backend
5. Show console output of the agent's work

After running, check your observability backend to see:

- Full trace of the agent execution
- Token usage and costs
- Tool calls with inputs/outputs
- Timing information
- Any errors or issues

## Customizing Examples

Feel free to modify these examples to:

- Change the prompts and tasks
- Enable/disable MCP servers
- Add different tools
- Configure different OTEL backends
- Adjust system prompts

The examples are meant to be starting points for your own use cases! 🚀
