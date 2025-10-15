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

        # Console logging
        logger.info(f"🔧 Tool: {tool_name}")
        if tool_input:
            logger.info(f"   Input: {json.dumps(tool_input, indent=2)[:200]}")

        if self.create_tool_spans:
            # Create child span for tool
            ctx_token = trace.set_span_in_context(self.session_span)
            tool_span = self.tracer.start_span(
                f"🔧 {tool_name}",
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
            event_data = {"tool_name": tool_name}

            # Add input fields as separate structured attributes
            if tool_input:
                for key, value in tool_input.items():
                    # Add each input field as a separate attribute
                    value_str = str(value)
                    if len(value_str) < 2000:
                        event_data[f"input.{key}"] = value_str

            self.session_span.add_event(f"🔧 Tool started: {tool_name}", event_data)

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

        # ALWAYS log that we're here with full debugging info
        logger.info(f"✅ Tool completed: {tool_name}")
        logger.info(f"   Response type: {type(tool_response).__name__}")

        # Log response structure
        if isinstance(tool_response, dict):
            logger.info(f"   Response keys: {list(tool_response.keys())}")
            # Show key fields
            for key in ["stdout", "stderr", "error", "result", "content"]:
                if key in tool_response:
                    value = str(tool_response[key])[:200]
                    suffix = "..." if len(str(tool_response[key])) > 200 else ""
                    logger.info(f"   {key}: {value}{suffix}")
        else:
            logger.info(f"   Response: {str(tool_response)[:200]}")

        if not self.create_tool_spans:
            # No child spans - add response data as event to session span
            event_data = {"tool_name": tool_name}

            # Add response data
            if tool_response is not None:
                if isinstance(tool_response, dict):
                    # Add key fields as separate event attributes
                    for key, value in tool_response.items():
                        value_str = str(value)
                        if len(value_str) < 2000:
                            event_data[f"response.{key}"] = value_str

                    # Check for errors - crash loudly if malformed
                    if "error" in tool_response and tool_response["error"]:
                        event_data["status"] = "error"
                        event_data["error"] = str(tool_response["error"])[:500]
                    elif "isError" in tool_response and tool_response["isError"]:
                        event_data["status"] = "error"
                    else:
                        event_data["status"] = "success"
                else:
                    event_data["response"] = str(tool_response)[:2000]
                    event_data["status"] = "success"

            self.session_span.add_event(f"✅ Tool completed: {tool_name}", event_data)
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
            self.session_span.add_event(f"Tool completed: {tool_name}")

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
