"""Claude SDK hooks for telemetry capture."""

from typing import Any
import json
import time

from opentelemetry import trace

from claude_telemetry.helpers.logger import logger
from claude_telemetry.logfire_adapter import get_logfire


def _truncate_for_display(text: str, max_length: int = 200) -> str:
    """Truncate text for display with ellipsis if needed."""
    if len(text) <= max_length:
        return text
    return text[:max_length] + "..."


def _smart_truncate_value(value: Any, max_length: int = 150) -> str:  # noqa: PLR0911
    """
    Truncate a value intelligently for display.

    - For strings: truncate with ellipsis
    - For lists: show first few items
    - For dicts: show truncated version
    - For other types: convert to string
    """
    if isinstance(value, str):
        if len(value) <= max_length:
            return value
        return value[:max_length] + "..."

    if isinstance(value, list):
        if len(value) == 0:
            return "[]"
        if len(value) <= 3:
            # Show all items if small list
            items_str = ", ".join(
                _smart_truncate_value(item, max_length // 3) for item in value
            )
            if len(items_str) <= max_length:
                return f"[{items_str}]"
        # Show first few items
        first_items = ", ".join(
            _smart_truncate_value(item, max_length // 4) for item in value[:2]
        )
        return f"[{first_items}, ... ({len(value)} items)]"

    if isinstance(value, dict):
        if len(value) == 0:
            return "{}"
        # Show first few keys
        items = []
        for i, (k, v) in enumerate(value.items()):
            if i >= 2:  # Show max 2 keys
                items.append(f"... ({len(value)} keys)")
                break
            v_str = _smart_truncate_value(v, max_length // 3)
            items.append(f"{k}: {v_str}")
        return "{" + ", ".join(items) + "}"

    # For other types (int, bool, None, etc)
    return str(value)


def _format_tool_input_for_console(tool_input: dict[str, Any]) -> str:
    """
    Format tool input for console display with smart truncation.

    Returns a nicely formatted, readable string that shows the structure
    without being overwhelming.
    """
    if not tool_input:
        return "{}"

    lines = []
    for key, value in tool_input.items():
        # Format value with smart truncation
        value_str = _smart_truncate_value(value, max_length=200)
        lines.append(f'  "{key}": {value_str}')

    return "{\n" + ",\n".join(lines) + "\n}"


def _format_tool_response_for_console(tool_response: Any) -> str:  # noqa: PLR0911
    """
    Format tool response for console display with smart truncation.

    Provides useful information about what the tool returned without
    overwhelming the console.
    """
    if tool_response is None:
        return "None"

    response_type = type(tool_response).__name__

    if isinstance(tool_response, dict):
        keys = list(tool_response.keys())

        # If the whole dict is small, just show it all
        full_str = str(tool_response)
        if len(full_str) <= 250:
            return f"dict with {len(keys)} key(s): {full_str}"

        # Dict is large - show structure and prioritize interesting fields
        result = f"dict with {len(keys)} key(s): {keys}\n"

        # Show interesting fields first (errors, results, content)
        interesting_keys = [
            "error",
            "stderr",
            "stdout",
            "result",
            "content",
            "message",
            "output",
        ]
        shown_keys = []
        for key in interesting_keys:
            if key in tool_response:
                value_str = _smart_truncate_value(tool_response[key], max_length=300)
                result += f"   • {key}: {value_str}\n"
                shown_keys.append(key)

        # If no interesting fields found, show first few keys
        if not shown_keys:
            for key in keys[:3]:
                value_str = _smart_truncate_value(tool_response[key], max_length=200)
                result += f"   • {key}: {value_str}\n"

        return result.rstrip()

    if isinstance(tool_response, list):
        count = len(tool_response)
        result = f"list with {count} item(s)"
        if count > 0:
            first_item = _smart_truncate_value(tool_response[0], max_length=200)
            result += f"\n   • First item: {first_item}"
            if count > 1:
                result += f"\n   • ... and {count - 1} more"
        return result

    if isinstance(tool_response, str):
        if len(tool_response) <= 300:
            return f'"{tool_response}"'
        return f'"{tool_response[:300]}..."'

    # For other types
    return f"{response_type}: {_smart_truncate_value(tool_response, max_length=300)}"


def create_tool_title(
    tool_name: str, tool_input: dict[str, Any] | None = None, max_length: int = 100
) -> str:
    """
    Create an informative title for a tool execution.

    Includes key arguments in the title for better DX when scanning logs.

    Args:
        tool_name: Name of the tool
        tool_input: Input arguments to the tool
        max_length: Maximum length for the title (default 100)

    Returns:
        Title like "Bash - ls -l" or "gmail - action=search, query=inbox"
    """
    if not tool_input:
        return tool_name

    # Build summary of key args (max 3 params for brevity)
    summary_parts = []
    for key, value in tool_input.items():
        if len(summary_parts) >= 3:
            break

        if isinstance(value, str):
            if len(value) < 30:
                # Short string - show in quotes if it looks like a command/path
                if "/" in value or value.startswith("-") or " " in value:
                    summary_parts.append(f'"{value}"')
                else:
                    summary_parts.append(f"{key}={value}")
            else:
                # Long string - truncate
                summary_parts.append(f'{key}="{value[:30]}..."')
        elif isinstance(value, (int, bool, type(None))):
            summary_parts.append(f"{key}={value}")
        elif isinstance(value, dict):
            summary_parts.append(f"{key}={{...{len(value)}}}")
        elif isinstance(value, list):
            summary_parts.append(f"{key}=[...{len(value)}]")

    if not summary_parts:
        return tool_name

    summary = ", ".join(summary_parts)
    title = f"{tool_name} - {summary}"

    # Truncate if too long
    if len(title) > max_length:
        title = title[: max_length - 3] + "..."

    return title


def create_completion_title(
    tool_name: str, tool_response: Any, max_length: int = 100
) -> str:
    """
    Create an informative title for a tool completion.

    Includes key response info for better DX when scanning logs.

    Args:
        tool_name: Name of the tool
        tool_response: Response from the tool
        max_length: Maximum length for the title (default 100)

    Returns:
        Title like "Bash → Success" or "gmail → 100 emails found"
    """
    if tool_response is None:
        return f"{tool_name} → None"

    # Build short response summary
    summary = None

    if isinstance(tool_response, dict):
        # Check for error first
        if "error" in tool_response and tool_response["error"]:
            error_msg = str(tool_response["error"])[:40]
            summary = f"Error: {error_msg}"
        elif "isError" in tool_response and tool_response["isError"]:
            summary = "Error"
        # Look for interesting result fields
        elif "result" in tool_response:
            result = str(tool_response["result"])[:40]
            summary = f"result={result}"
        elif "content" in tool_response:
            content = str(tool_response["content"])[:40]
            summary = f"{content}"
        elif "message" in tool_response:
            message = str(tool_response["message"])[:40]
            summary = f"{message}"
        else:
            # Just show count of keys
            summary = f"{len(tool_response)} fields"

    elif isinstance(tool_response, list):
        count = len(tool_response)
        summary = f"{count} item{'s' if count != 1 else ''}"

    elif isinstance(tool_response, str):
        if len(tool_response) < 50:
            summary = tool_response[:50]
        else:
            summary = f"{tool_response[:50]}..."

    else:
        summary = str(tool_response)[:50]

    title = f"{tool_name} → {summary}"

    # Truncate if too long
    if len(title) > max_length:
        title = title[: max_length - 3] + "..."

    return title


def create_event_data(
    tool_name: str, tool_input: dict[str, Any] | None = None
) -> dict[str, Any]:
    """
    Create structured event data for OpenTelemetry that's both searchable and readable.

    Works with any OTEL backend (Logfire, Honeycomb, Grafana, etc.)

    Returns a dict with:
    - tool_name for easy filtering
    - flattened input parameters as individual fields for searchability
    - summary field with key parameters for quick reading
    """
    event_data = {"tool_name": tool_name}

    if not tool_input:
        return event_data

    # Add input summary - a human-readable one-liner
    summary_parts = []
    for key, value in tool_input.items():
        if (
            isinstance(value, str)
            and len(value) < 50
            or isinstance(value, (int, bool, type(None)))
        ):
            summary_parts.append(f"{key}={value}")
        elif isinstance(value, dict):
            summary_parts.append(f"{key}={{...{len(value)} keys}}")
        elif isinstance(value, list):
            summary_parts.append(f"{key}=[...{len(value)} items]")

    if summary_parts:
        event_data["input_summary"] = ", ".join(summary_parts[:5])

    # Add individual input fields as separate attributes for searchability
    for key, value in tool_input.items():
        value_str = str(value)
        # Keep under Logfire's attribute size limits
        if len(value_str) < 2000:
            event_data[f"input.{key}"] = value_str
        else:
            # For very large values, add a truncated version plus size info
            truncated = (
                f"{value_str[:1900]}... (truncated, full size: {len(value_str)} chars)"
            )
            event_data[f"input.{key}"] = truncated

    return event_data


def add_response_to_event_data(  # noqa: PLR0915
    event_data: dict[str, Any], tool_response: Any
) -> None:
    """
    Add response information to OpenTelemetry event data.

    Works with any OTEL backend (Logfire, Honeycomb, Grafana, etc.)

    Modifies event_data in place to add:
    - status (success/error)
    - response summary
    - individual response fields for searchability
    """
    if tool_response is None:
        event_data["status"] = "success"
        event_data["response_summary"] = "None"
        return

    # Add response type and basic info
    event_data["response_type"] = type(tool_response).__name__

    # Handle different response types
    if isinstance(tool_response, dict):
        # Check for errors
        has_error = ("error" in tool_response and tool_response["error"]) or (
            "isError" in tool_response and tool_response["isError"]
        )

        event_data["status"] = "error" if has_error else "success"

        # Create summary
        if has_error:
            error_msg = str(tool_response.get("error", "Unknown error"))[:200]
            event_data["response_summary"] = f"Error: {error_msg}"
        else:
            # Summarize key fields
            summary_parts = []
            for key in ["result", "content", "message", "output", "stdout"]:
                if key in tool_response:
                    val = str(tool_response[key])
                    if len(val) < 100:
                        summary_parts.append(f"{key}={val}")
                    else:
                        summary_parts.append(f"{key}=...({len(val)} chars)")

            if summary_parts:
                event_data["response_summary"] = ", ".join(summary_parts[:3])
            else:
                keys = list(tool_response.keys())
                event_data["response_summary"] = f"{len(keys)} fields: {keys[:5]}"

        # Add individual response fields
        for key, value in tool_response.items():
            value_str = str(value)
            if len(value_str) < 2000:
                event_data[f"response.{key}"] = value_str
            else:
                truncated = (
                    f"{value_str[:1900]}... "
                    f"(truncated, full size: {len(value_str)} chars)"
                )
                event_data[f"response.{key}"] = truncated

    elif isinstance(tool_response, list):
        event_data["status"] = "success"
        count = len(tool_response)
        event_data["response_summary"] = f"List with {count} items"
        event_data["response.count"] = count
        if count > 0:
            first_str = str(tool_response[0])[:200]
            event_data["response.first_item"] = first_str

    elif isinstance(tool_response, str):
        event_data["status"] = "success"
        if len(tool_response) < 200:
            event_data["response_summary"] = tool_response
        else:
            event_data["response_summary"] = tool_response[:200] + "..."
        if len(tool_response) > 2000:
            event_data["response"] = tool_response[:2000]
        else:
            event_data["response"] = tool_response

    else:
        event_data["status"] = "success"
        response_str = str(tool_response)
        event_data["response_summary"] = response_str[:200]
        if len(response_str) > 2000:
            event_data["response"] = response_str[:2000]
        else:
            event_data["response"] = response_str


class TelemetryHooks:
    """Hooks for capturing Claude agent telemetry."""

    def __init__(
        self,
        tracer_name: str = "claude-telemetry",
        create_tool_spans: bool = False,
    ):
        """
        Initialize hooks with a tracer.

        Args:
            tracer_name: Name for the OpenTelemetry tracer
            create_tool_spans: If True, create child spans for each tool.
                              If False (default), add tool data as events only.
        """
        self.tracer = trace.get_tracer(tracer_name)
        self.session_span = None
        self.tool_spans = {}
        # Initialize metrics with all required keys so methods can safely access them
        self.metrics = {
            "prompt": "",
            "model": "unknown",
            "input_tokens": 0,
            "output_tokens": 0,
            "tools_used": 0,
            "turns": 0,
            "start_time": 0.0,
        }
        self.messages = []
        self.tools_used = []
        self.create_tool_spans = create_tool_spans

    async def on_user_prompt_submit(
        self,
        input_data: dict[str, Any],
        tool_use_id: str | None,
        ctx: Any,
    ) -> dict[str, Any]:
        """
        Hook called when user submits a prompt.

        Opens the parent span and logs the initial prompt.
        """
        # Extract prompt from input
        prompt = input_data["prompt"]
        # Extract model from context - NO default, let it be None if not set
        model = (
            ctx["options"]["model"]
            if "options" in ctx and "model" in ctx["options"]
            else "unknown"
        )

        # Initialize metrics
        self.metrics = {
            "prompt": prompt,
            "model": model,
            "input_tokens": 0,
            "output_tokens": 0,
            "tools_used": 0,
            "turns": 0,
            "start_time": time.time(),
        }

        # Create span title with prompt preview
        prompt_preview = prompt[:60] + "..." if len(prompt) > 60 else prompt
        span_title = f"🤖 {prompt_preview}"

        # Start session span
        self.session_span = self.tracer.start_span(
            span_title,
            attributes={
                "prompt": prompt,
                "model": model,
                "session_id": input_data["session_id"],
            },
        )

        # Add user prompt event
        self.session_span.add_event("👤 User prompt submitted", {"prompt": prompt})

        # Store message
        self.messages.append({"role": "user", "content": prompt})

        logger.debug(f"🎯 Span created: {span_title}")

        return {}

    async def on_pre_tool_use(
        self,
        input_data: dict[str, Any],
        tool_use_id: str | None,
        ctx: Any,
    ) -> dict[str, Any]:
        """Hook called before tool execution."""
        tool_name = input_data["tool_name"]
        tool_input = input_data.get("tool_input", {})

        if not self.session_span:
            msg = "No active session span"
            raise RuntimeError(msg)

        # Track usage
        self.tools_used.append(tool_name)
        self.metrics["tools_used"] += 1

        # Console logging with smart formatting
        tool_title = create_tool_title(tool_name, tool_input)
        logger.info(f"🔧 Tool: {tool_title}")
        if tool_input:
            formatted_input = _format_tool_input_for_console(tool_input)
            logger.info(f"   Input:\n{formatted_input}")

        if self.create_tool_spans:
            # Create child span for tool
            ctx_token = trace.set_span_in_context(self.session_span)
            tool_span = self.tracer.start_span(
                f"🔧 {tool_title}",
                attributes={"tool.name": tool_name},
                context=ctx_token,
            )

            # Add tool input as attributes
            if tool_input:
                for key, val in tool_input.items():
                    if isinstance(val, str) and len(val) < 100:
                        tool_span.set_attribute(f"tool.input.{key}", val)
                tool_span.add_event("Tool input", {"input": str(tool_input)[:500]})

            # Store span
            tool_id = tool_use_id or f"{tool_name}_{time.time()}"
            self.tool_spans[tool_id] = tool_span
        else:
            # Just add event to session span (no child span)
            event_data = create_event_data(tool_name, tool_input)
            self.session_span.add_event(f"🔧 Tool started: {tool_title}", event_data)

        return {}

    async def on_post_tool_use(  # noqa: PLR0915
        self,
        input_data: dict[str, Any],
        tool_use_id: str | None,
        ctx: Any,
    ) -> dict[str, Any]:
        """Hook called after tool execution."""
        tool_name = input_data["tool_name"]
        tool_response = input_data.get("tool_response")

        # Console logging with smart formatting
        completion_title = create_completion_title(tool_name, tool_response)
        logger.info(f"✅ Tool completed: {completion_title}")
        formatted_response = _format_tool_response_for_console(tool_response)
        logger.info(f"   {formatted_response}")

        if not self.create_tool_spans:
            # No child spans - add response data as event to session span
            event_data = {"tool_name": tool_name}
            add_response_to_event_data(event_data, tool_response)

            event_title = f"✅ Tool completed: {completion_title}"
            self.session_span.add_event(event_title, event_data)
            return {}

        # Child span mode - find and close the span
        span = None
        span_id = None

        if tool_use_id and tool_use_id in self.tool_spans:
            span = self.tool_spans[tool_use_id]
            span_id = tool_use_id
        else:
            # Fall back to name matching for most recent
            for tid, s in reversed(list(self.tool_spans.items())):
                if tid.startswith(f"{tool_name}_") or tid == tool_use_id:
                    span = s
                    span_id = tid
                    break

        if not span:
            logger.error(f"❌ No span found for tool: {tool_name} (id: {tool_use_id})")
            logger.error(f"   Active spans: {list(self.tool_spans.keys())}")
            logger.error("   Span was never created or already closed!")
            return {}

        # Wrap span operations in try/finally to ALWAYS close the span
        try:
            # Add response as span attributes for visibility in Logfire
            if tool_response is not None:
                # Handle dict responses properly - extract key fields
                if isinstance(tool_response, dict):
                    # Set individual fields as attributes for better visibility
                    for key, value in tool_response.items():
                        # Limit attribute size to avoid OTEL limits
                        value_str = str(value)
                        if len(value_str) < 10000:
                            span.set_attribute(f"tool.response.{key}", value_str)

                    # Check for errors - crash loudly if malformed
                    if "error" in tool_response and tool_response["error"]:
                        error_msg = str(tool_response["error"])
                        span.set_attribute("tool.error", error_msg)
                        span.set_attribute("tool.status", "error")
                        logger.error(f"❌ Tool error: {tool_name}")
                        logger.error(f"   Error: {error_msg}")
                    elif "isError" in tool_response and tool_response["isError"]:
                        span.set_attribute("tool.is_error", True)
                        span.set_attribute("tool.status", "error")
                        logger.error(f"❌ Tool failed: {tool_name}")
                    else:
                        span.set_attribute("tool.status", "success")
                else:
                    # Non-dict response - treat as string
                    response_str = str(tool_response)
                    span.set_attribute("tool.response", response_str[:10000])
                    span.set_attribute("tool.status", "success")

                # Add full response as event for timeline view
                try:
                    response_json = (
                        json.dumps(tool_response, indent=2)
                        if isinstance(tool_response, (dict, list))
                        else str(tool_response)
                    )
                    if len(response_json) > 2000:
                        span.add_event(
                            "Tool response", {"response": response_json[:2000] + "..."}
                        )
                    else:
                        span.add_event("Tool response", {"response": response_json})
                except Exception:
                    span.add_event(
                        "Tool response", {"response": str(tool_response)[:2000]}
                    )
        finally:
            # ALWAYS end the span, even if there was an error
            try:
                span.end()
                logger.debug(f"   Span closed for {tool_name}")
            except Exception as e:
                logger.error(f"   Error closing span for {tool_name}: {e}")

            # Remove from tracking dict
            if span_id and span_id in self.tool_spans:
                del self.tool_spans[span_id]

        # Add event to session span
        if self.session_span:
            self.session_span.add_event(f"Tool completed: {completion_title}")

        return {}

    async def on_message_complete(
        self,
        message: Any,
        ctx: Any,
    ) -> dict[str, Any]:
        """Hook called when assistant message is complete - updates token counts."""
        # Extract token usage
        if hasattr(message, "usage"):
            input_tokens = getattr(message.usage, "input_tokens", 0)
            output_tokens = getattr(message.usage, "output_tokens", 0)

            self.metrics["input_tokens"] += input_tokens
            self.metrics["output_tokens"] += output_tokens
            self.metrics["turns"] += 1

            # Update span with cumulative token usage
            if self.session_span:
                self.session_span.set_attribute(
                    "gen_ai.usage.input_tokens", self.metrics["input_tokens"]
                )
                self.session_span.set_attribute(
                    "gen_ai.usage.output_tokens", self.metrics["output_tokens"]
                )
                self.session_span.set_attribute("turns", self.metrics["turns"])

                # Add event for this turn with incremental tokens
                self.session_span.add_event(
                    "Turn completed",
                    {
                        "turn": self.metrics["turns"],
                        "input_tokens": input_tokens,
                        "output_tokens": output_tokens,
                    },
                )

        # Store message
        if hasattr(message, "content"):
            self.messages.append({"role": "assistant", "content": message.content})

        return {}

    async def on_pre_compact(
        self,
        input_data: dict[str, Any],
        tool_use_id: str | None,
        ctx: Any,
    ) -> dict[str, Any]:
        """Hook called before context window compaction."""
        trigger = input_data.get("trigger", "unknown")
        custom_instructions = input_data.get("custom_instructions")

        if self.session_span:
            self.session_span.add_event(
                "Context compaction",
                {
                    "trigger": trigger,
                    "has_custom_instructions": custom_instructions is not None,
                },
            )

        return {}

    def complete_session(self) -> None:
        """Complete and flush the telemetry session."""
        if not self.session_span:
            msg = "No active session span"
            raise RuntimeError(msg)

        # Set final attributes
        self.session_span.set_attribute("gen_ai.request.model", self.metrics["model"])
        self.session_span.set_attribute("gen_ai.response.model", self.metrics["model"])
        self.session_span.set_attribute("tools_used", self.metrics["tools_used"])

        if self.tools_used:
            self.session_span.set_attribute(
                "tool_names", ",".join(set(self.tools_used))
            )

        # Add completion event
        self.session_span.add_event("🎉 Completed")

        # End span
        self.session_span.end()

        # Flush
        logfire = get_logfire()
        if logfire:
            logfire.force_flush()
        else:
            tracer_provider = trace.get_tracer_provider()
            if hasattr(tracer_provider, "force_flush"):
                tracer_provider.force_flush()

        # Log summary
        duration = time.time() - self.metrics["start_time"]
        logger.info(
            f"✅ Session completed | {self.metrics['input_tokens']} in, "
            f"{self.metrics['output_tokens']} out | "
            f"{self.metrics['tools_used']} tools | {duration:.1f}s"
        )

        # Reset
        self.session_span = None
        self.tool_spans = {}
        self.metrics = {}
        self.messages = []
        self.tools_used = []
