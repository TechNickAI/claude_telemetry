"""Claude SDK hooks for telemetry capture."""

import json
import time
from typing import Any

from opentelemetry import trace

from claude_telemetry.helpers.logger import logger
from claude_telemetry.logfire_adapter import get_logfire


class TelemetryHooks:
    """Hooks for capturing Claude agent telemetry."""

    def __init__(self, tracer_name: str = "claude-telemetry"):
        """Initialize hooks with a tracer."""
        self.tracer = trace.get_tracer(tracer_name)
        self.session_span = None
        self.tool_spans = {}
        self.metrics = {}
        self.messages = []
        self.tools_used = []

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

        # Create tool span as child
        with trace.use_span(self.session_span, end_on_exit=False):
            tool_span = self.tracer.start_span(
                f"🔧 {tool_name}",
                attributes={"tool.name": tool_name},
            )

        # Log tool input as event (with key parameters as attributes)
        if tool_input:
            # Add simplified input params as span attributes (strings only)
            for key, val in tool_input.items():
                if isinstance(val, str) and len(val) < 100:
                    tool_span.set_attribute(f"tool.input.{key}", val)

            # Add full input as event
            tool_span.add_event("Tool input", {"input": str(tool_input)[:500]})

        # Store span WITH THE ACTUAL tool_use_id from SDK
        tool_id = tool_use_id or f"{tool_name}_{time.time()}"
        self.tool_spans[tool_id] = tool_span

        # Track usage
        self.tools_used.append(tool_name)
        self.metrics["tools_used"] += 1

        # Add event to parent
        self.session_span.add_event(f"Tool started: {tool_name}")

        # Console logging
        logger.info(f"🔧 Tool: {tool_name}")
        if tool_input:
            logger.debug(f"   Input: {tool_input}")

        return {"tool_id": tool_id}

    async def on_post_tool_use(  # noqa: PLR0915
        self,
        input_data: dict[str, Any],
        tool_use_id: str | None,
        ctx: Any,
    ) -> dict[str, Any]:
        """Hook called after tool execution."""
        tool_name = input_data["tool_name"]
        tool_response = input_data.get("tool_response")

        # ALWAYS log that we're here
        logger.info(f"📥 POST_TOOL: {tool_name}")
        logger.info(f"   Keys: {list(input_data.keys())}")
        logger.info(f"   Has response: {tool_response is not None}")
        logger.info(f"   Response type: {type(tool_response)}")
        logger.info(f"   Response: {str(tool_response)[:200]}")

        # Find span using tool_use_id first, then fall back to name matching
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

        if span:
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

                    # Check for errors
                    if "error" in tool_response:
                        error_msg = str(tool_response["error"])
                        span.set_attribute("tool.error", error_msg)
                        logger.error(f"❌ Tool error: {tool_name}")
                        logger.error(f"   Error: {error_msg}")
                    if "isError" in tool_response and tool_response["isError"]:
                        span.set_attribute("tool.is_error", True)
                        logger.error(f"❌ Tool failed: {tool_name}")

                    # Console logging - show structured response
                    logger.info(f"✅ Tool response: {tool_name}")
                    for key, value in tool_response.items():
                        value_str = str(value)
                        if len(value_str) > 200:
                            logger.info(f"   {key}: {value_str[:200]}...")
                        else:
                            logger.info(f"   {key}: {value_str}")
                else:
                    # Non-dict response - treat as string
                    response_str = str(tool_response)
                    span.set_attribute("tool.response", response_str)
                    logger.info(f"✅ Tool response: {tool_name}")
                    logger.info(f"   Response: {response_str[:500]}")

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

            span.end()
            if span_id:
                del self.tool_spans[span_id]

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
