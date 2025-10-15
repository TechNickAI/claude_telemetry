"""Claude SDK hooks for telemetry capture."""

import json
import time
from contextvars import ContextVar
from typing import Any

from loguru import logger
from opentelemetry import trace

from claude_telemetry.logfire_adapter import (
    create_tool_span_for_logfire,
    format_for_logfire_llm,
)
from claude_telemetry.telemetry import safe_span_operation

# Context variables to track spans across async boundaries
current_session_span: ContextVar[Any | None] = ContextVar("session_span", default=None)
current_tool_spans: ContextVar[dict[str, Any] | None] = ContextVar(
    "tool_spans", default=None
)
session_metrics: ContextVar[dict[str, Any] | None] = ContextVar(
    "session_metrics", default=None
)


class TelemetryHooks:
    """Hooks for capturing Claude agent telemetry."""

    def __init__(self, tracer_name: str = "claude-telemetry"):
        """Initialize hooks with a tracer."""
        self.tracer = trace.get_tracer(tracer_name)
        self.start_time = None
        self.messages = []
        self.tools_used = []
        self.is_logfire = self._detect_logfire()

    def _detect_logfire(self) -> bool:
        """Check if Logfire is configured."""
        try:
            import logfire  # noqa: F401, PLC0415

            return trace.get_tracer_provider() is not None
        except ImportError:
            return False

    @safe_span_operation
    async def on_user_prompt_submit(
        self,
        input_data: dict[str, Any],
        tool_use_id: str | None,
        context: Any,
    ) -> dict[str, Any]:
        """
        Hook called when user submits a prompt.

        Opens the parent span and logs the initial prompt.
        """
        # Extract prompt from input
        prompt = input_data.get("text", "")
        model = context.options.model if hasattr(context, "options") else "unknown"

        # Initialize session metrics
        metrics = {
            "prompt": prompt,
            "model": model,
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "tools_used": 0,
            "turns": 0,
            "start_time": time.time(),
        }
        session_metrics.set(metrics)

        # Start parent span
        span = self.tracer.start_span(f"🤖 {prompt[:50]}...")
        current_session_span.set(span)

        # Set initial attributes
        span.set_attribute("prompt", prompt)
        span.set_attribute("model", model)

        # Add user prompt event
        span.add_event("👤 User prompt submitted", {"prompt": prompt})

        # Store message for Logfire formatting
        self.messages.append({"role": "user", "content": prompt})

        # Log to console with nice formatting
        logger.info(f"🤖 {prompt}")
        logger.info("  👤 User prompt submitted")

        return {}

    @safe_span_operation
    async def on_pre_tool_use(
        self,
        tool_name: str,
        tool_input: dict[str, Any],
        context: Any,
    ) -> dict[str, Any]:
        """
        Hook called before tool execution.

        Opens a child span for the tool.
        """
        parent_span = current_session_span.get()
        if not parent_span:
            return {}

        # Create tool span
        if self.is_logfire:
            span = create_tool_span_for_logfire(self.tracer, tool_name, tool_input)
        else:
            span = self.tracer.start_span(f"tool.{tool_name}")
            span.set_attribute("tool.name", tool_name)
            # Add tool inputs as JSON string for non-Logfire
            span.set_attribute("tool.input", json.dumps(tool_input))

        # Store span for post-tool hook
        tool_spans = current_tool_spans.get() or {}
        tool_id = f"{tool_name}_{time.time()}"
        tool_spans[tool_id] = span
        current_tool_spans.set(tool_spans)

        # Track tool usage
        self.tools_used.append(tool_name)
        metrics = session_metrics.get()
        if metrics:
            metrics["tools_used"] += 1

        # Log to console
        logger.info(f"  🔧 Calling tool: {tool_name}")

        # Add event to parent span
        parent_span.add_event(f"Tool call started: {tool_name}", {"tool": tool_name})

        return {"tool_id": tool_id}

    @safe_span_operation
    async def on_post_tool_use(
        self,
        tool_name: str,
        tool_output: Any,
        context: Any,
        tool_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Hook called after tool execution.

        Closes the tool span and logs output.
        """
        # Get tool span
        tool_spans = current_tool_spans.get() or {}

        # Find the span (try with tool_id first, then search by name)
        span = None
        if tool_id and tool_id in tool_spans:
            span = tool_spans[tool_id]
        else:
            # Find most recent span for this tool
            for tid, s in reversed(list(tool_spans.items())):
                if tid.startswith(f"{tool_name}_"):
                    span = s
                    tool_id = tid
                    break

        if span:
            # Add output attribute
            output_str = (
                json.dumps(tool_output)
                if isinstance(tool_output, (dict, list))
                else str(tool_output)
            )
            # Truncate very long outputs
            if len(output_str) > 1000:
                output_str = output_str[:1000] + "..."
            span.set_attribute("tool.output", output_str)

            # End the span
            span.end()

            # Remove from active spans
            if tool_id:
                del tool_spans[tool_id]
                current_tool_spans.set(tool_spans)

        # Log to console
        logger.info(f"  ✅ Tool completed: {tool_name}")

        # Add event to parent span
        parent_span = current_session_span.get()
        if parent_span:
            parent_span.add_event(f"Tool completed: {tool_name}")

        return {}

    @safe_span_operation
    async def on_message_complete(
        self,
        message: Any,
        context: Any,
    ) -> dict[str, Any]:
        """
        Hook called when assistant message is complete.

        Updates metrics with token counts.
        """
        # Extract token usage if available
        if hasattr(message, "usage"):
            metrics = session_metrics.get()
            if metrics:
                input_tokens = getattr(message.usage, "input_tokens", 0)
                output_tokens = getattr(message.usage, "output_tokens", 0)

                metrics["input_tokens"] += input_tokens
                metrics["output_tokens"] += output_tokens
                metrics["total_tokens"] = (
                    metrics["input_tokens"] + metrics["output_tokens"]
                )
                metrics["turns"] += 1

                # Update parent span
                span = current_session_span.get()
                if span:
                    span.set_attribute("input_tokens", metrics["input_tokens"])
                    span.set_attribute("output_tokens", metrics["output_tokens"])
                    span.set_attribute("total_tokens", metrics["total_tokens"])
                    span.set_attribute("turns", metrics["turns"])

        # Store assistant message for Logfire
        if hasattr(message, "content"):
            self.messages.append({"role": "assistant", "content": message.content})

        return {}

    @safe_span_operation
    def complete_session(self) -> None:
        """
        Complete the telemetry session.

        Closes the parent span with final metrics.
        """
        span = current_session_span.get()
        if not span:
            return

        metrics = session_metrics.get()
        if metrics:
            # Get metrics
            model = metrics.get("model", "unknown")
            input_tokens = metrics.get("input_tokens", 0)
            output_tokens = metrics.get("output_tokens", 0)

            # Set final attributes
            span.set_attribute("tools_used", metrics.get("tools_used", 0))

            # Format span for Logfire if configured
            if self.is_logfire:
                format_for_logfire_llm(
                    span,
                    model=model,
                    messages=self.messages,
                    response=self.messages[-1]["content"]
                    if self.messages and self.messages[-1]["role"] == "assistant"
                    else None,
                    tools_used=self.tools_used,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    cost_usd=None,  # Let the API provide cost if available
                )

            # Add completion event
            span.add_event("🎉 Agent completed")

            # Log final metrics to console
            duration = time.time() - metrics.get("start_time", time.time())
            logger.info("  🎉 Agent completed")
            logger.info(
                f"\nSession completed - "
                f"Tokens: {input_tokens} in, {output_tokens} out, "
                f"Tools called: {metrics.get('tools_used', 0)}, "
                f"Duration: {duration:.1f}s"
            )

        # End the span
        span.end()

        # Clear context
        current_session_span.set(None)
        session_metrics.set(None)
        current_tool_spans.set(None)

        # Reset state
        self.messages = []
        self.tools_used = []
