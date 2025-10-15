"""Claude SDK hooks for telemetry capture."""

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
        model = ctx.get("options", {}).get("model", "claude-sonnet-4-20250514")

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

        # Store span
        tool_id = f"{tool_name}_{time.time()}"
        self.tool_spans[tool_id] = tool_span

        # Track usage
        self.tools_used.append(tool_name)
        self.metrics["tools_used"] += 1

        # Add event to parent
        self.session_span.add_event(f"Tool started: {tool_name}")

        return {"tool_id": tool_id}

    async def on_post_tool_use(
        self,
        input_data: dict[str, Any],
        tool_use_id: str | None,
        ctx: Any,
    ) -> dict[str, Any]:
        """Hook called after tool execution."""
        tool_name = input_data["tool_name"]
        tool_response = input_data.get("tool_response")

        # Find and end tool span - use most recent for this tool name
        span = None
        tool_id = None
        for tid, s in reversed(list(self.tool_spans.items())):
            if tid.startswith(f"{tool_name}_"):
                span = s
                tool_id = tid
                break

        if span:
            # Add response as event (truncate if too long)
            if tool_response is not None:
                response_str = str(tool_response)
                if len(response_str) > 500:
                    response_str = response_str[:500] + "..."
                span.add_event("Tool response", {"response": response_str})

            span.end()
            if tool_id:
                del self.tool_spans[tool_id]

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
