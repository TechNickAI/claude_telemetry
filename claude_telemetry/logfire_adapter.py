"""Logfire-specific enhancements for LLM telemetry."""

import json
from typing import Any

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider

from claude_telemetry.helpers.logger import logger

# Global logfire instance - set during configure
_logfire = None


def configure_logfire(service_name: str = "claude-agents") -> TracerProvider:
    """
    Configure Logfire with LLM-specific formatting.

    Args:
        service_name: Service name for traces

    Returns:
        Configured TracerProvider with Logfire enhancements
    """
    global _logfire  # noqa: PLW0603
    import os  # noqa: PLC0415

    try:
        import logfire  # noqa: PLC0415

        # Check token is present
        token = os.getenv("LOGFIRE_TOKEN")
        if not token:
            msg = "LOGFIRE_TOKEN environment variable is not set"
            raise ValueError(msg)  # noqa: TRY301

        # Configure Logfire with service name
        logfire.configure(
            service_name=service_name,
            send_to_logfire=True,
        )

        # Store global logfire instance for span creation
        _logfire = logfire

        # Get the configured tracer provider
        provider = trace.get_tracer_provider()

        # Log the Logfire project URL
        logger.info(f"Logfire configured with service name: {service_name}")
        logger.info("Note: Token validation happens on first span export")

    except Exception:
        logger.exception("Failed to configure Logfire")
        raise
    else:
        return provider


def get_logfire():
    """Get the configured logfire instance."""
    return _logfire


def format_for_logfire_llm(
    span,
    model: str,
    messages: list,
    response: str | None = None,
    tools_used: list | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    cost_usd: float | None = None,
) -> None:
    """
    Format span attributes for Logfire's LLM UI.

    Logfire expects specific attributes to display LLM interactions properly:
    - request_data: Contains model and messages
    - response_data: Contains assistant response and usage
    - Special tags for LLM visualization

    Args:
        span: OpenTelemetry span to enhance
        model: Model name
        messages: Conversation messages
        response: Assistant response content
        tools_used: List of tool calls made
        input_tokens: Input token count
        output_tokens: Output token count
        cost_usd: Total cost in USD
    """
    try:
        # Format request data for Logfire LLM UI
        request_data = {
            "model": model,
            "messages": messages,
        }

        # Add tool definitions if any tools were used
        if tools_used:
            request_data["tools"] = [{"name": tool} for tool in set(tools_used)]

        # Set request attributes
        span.set_attribute("request_data", json.dumps(request_data))
        span.set_attribute("llm.request.model", model)

        # Format response data if available
        if response:
            response_data = {
                "message": {
                    "role": "assistant",
                    "content": response,
                },
            }

            # Add usage data if available
            if input_tokens or output_tokens:
                response_data["usage"] = {}
                if input_tokens:
                    response_data["usage"]["input_tokens"] = input_tokens
                if output_tokens:
                    response_data["usage"]["output_tokens"] = output_tokens
                if input_tokens and output_tokens:
                    response_data["usage"]["total_tokens"] = (
                        input_tokens + output_tokens
                    )

            span.set_attribute("response_data", json.dumps(response_data))

        # Add LLM-specific attributes for Logfire
        span.set_attribute("span.kind", "LLM")
        span.set_attribute("logfire.span_type", "llm")

        # Add token metrics
        if input_tokens:
            span.set_attribute("llm.usage.input_tokens", input_tokens)
        if output_tokens:
            span.set_attribute("llm.usage.output_tokens", output_tokens)
        if cost_usd is not None:
            span.set_attribute("llm.usage.cost_usd", cost_usd)

        # Add tool usage metrics
        if tools_used:
            span.set_attribute("llm.tools.count", len(tools_used))
            span.set_attribute("llm.tools.names", tools_used)

    except Exception as e:
        logger.warning(f"Failed to format span for Logfire LLM UI: {e}")
        # Don't fail - just log and continue


def create_tool_span_for_logfire(
    tracer,
    tool_name: str,
    tool_input: dict[str, Any],
) -> Any:
    """
    Create a child span for tool usage with Logfire formatting.

    Args:
        tracer: OpenTelemetry tracer
        tool_name: Name of the tool being called
        tool_input: Tool input parameters

    Returns:
        Span context manager
    """
    # Create span with tool emoji prefix
    span_name = f"🔧 {tool_name}"

    span = tracer.start_span(span_name)

    # Add tool-specific attributes
    span.set_attribute("tool.name", tool_name)

    # Add individual input parameters as attributes
    for key, val in tool_input.items():
        # Convert complex values to JSON strings
        if isinstance(val, (dict, list)):
            formatted_val = json.dumps(val)
        elif val is not None:
            formatted_val = str(val)
        else:
            formatted_val = val

        span.set_attribute(f"tool.input.{key}", formatted_val)

    return span
