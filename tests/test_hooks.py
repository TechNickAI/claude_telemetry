"""Tests for telemetry hooks."""

import time

import pytest

from claude_telemetry.hooks import TelemetryHooks


@pytest.fixture
def hooks():
    """Create TelemetryHooks instance for testing."""
    return TelemetryHooks(tracer_name="test-tracer")


@pytest.fixture
def mock_span(mocker):
    """Create a mock OpenTelemetry span."""
    span = mocker.MagicMock()
    span.set_attribute = mocker.MagicMock()
    span.add_event = mocker.MagicMock()
    span.end = mocker.MagicMock()
    return span


@pytest.fixture
def mock_tracer(mocker, mock_span):
    """Mock the OpenTelemetry tracer."""
    tracer = mocker.MagicMock()
    tracer.start_span = mocker.MagicMock(return_value=mock_span)
    return tracer


class TestUserPromptSubmit:
    """Tests for on_user_prompt_submit hook."""

    @pytest.mark.asyncio
    async def test_creates_session_span(self, hooks, mocker, mock_tracer):
        """Test that user prompt creates a session span."""
        hooks.tracer = mock_tracer

        input_data = {
            "prompt": "Analyze my code",
            "session_id": "test-session-123",
        }
        ctx = {"options": {"model": "claude-3-5-sonnet-20241022"}}

        await hooks.on_user_prompt_submit(input_data, None, ctx)

        # Verify span was created
        mock_tracer.start_span.assert_called_once()
        assert hooks.session_span is not None

        # Verify span attributes
        call_args = mock_tracer.start_span.call_args
        assert "Analyze my code" in call_args[0][0]  # Span title contains prompt
        assert call_args[1]["attributes"]["prompt"] == "Analyze my code"
        assert call_args[1]["attributes"]["model"] == "claude-3-5-sonnet-20241022"

    @pytest.mark.asyncio
    async def test_initializes_metrics(self, hooks, mocker, mock_tracer):
        """Test that metrics are initialized correctly."""
        hooks.tracer = mock_tracer

        input_data = {"prompt": "Test prompt", "session_id": "test-session"}
        ctx = {"options": {"model": "opus"}}

        await hooks.on_user_prompt_submit(input_data, None, ctx)

        assert hooks.metrics["prompt"] == "Test prompt"
        assert hooks.metrics["model"] == "opus"
        assert hooks.metrics["input_tokens"] == 0
        assert hooks.metrics["output_tokens"] == 0
        assert hooks.metrics["tools_used"] == 0
        assert hooks.metrics["turns"] == 0
        assert "start_time" in hooks.metrics

    @pytest.mark.asyncio
    async def test_truncates_long_prompts_in_title(self, hooks, mocker, mock_tracer):
        """Test that long prompts are truncated in span title."""
        hooks.tracer = mock_tracer

        long_prompt = "A" * 100
        input_data = {"prompt": long_prompt, "session_id": "test-session"}
        ctx = {"options": {"model": "claude-3-5-sonnet-20241022"}}

        await hooks.on_user_prompt_submit(input_data, None, ctx)

        call_args = mock_tracer.start_span.call_args
        span_title = call_args[0][0]
        # Should be truncated to 60 chars + "..."
        assert len(span_title) < len(long_prompt) + 10
        assert "..." in span_title

    @pytest.mark.asyncio
    async def test_stores_message_history(self, hooks, mocker, mock_tracer):
        """Test that user message is stored in history."""
        hooks.tracer = mock_tracer

        input_data = {"prompt": "Test prompt", "session_id": "test-session"}
        ctx = {"options": {"model": "claude-3-5-sonnet-20241022"}}

        await hooks.on_user_prompt_submit(input_data, None, ctx)

        assert len(hooks.messages) == 1
        assert hooks.messages[0]["role"] == "user"
        assert hooks.messages[0]["content"] == "Test prompt"


class TestPreToolUse:
    """Tests for on_pre_tool_use hook."""

    @pytest.mark.asyncio
    async def test_creates_tool_span_when_enabled(self, hooks, mocker, mock_tracer):
        """Test that tool span is created when create_tool_spans=True."""
        hooks.create_tool_spans = True
        hooks.tracer = mock_tracer
        hooks.session_span = mocker.MagicMock()
        # No need to set metrics - __init__ handles it now

        input_data = {
            "tool_name": "Read",
            "tool_input": {"path": "/test/file.py"},
        }

        await hooks.on_pre_tool_use(input_data, "tool-123", {})

        # Verify child span was created
        mock_tracer.start_span.assert_called_once()
        call_args = mock_tracer.start_span.call_args
        assert "Read" in call_args[0][0]
        assert "tool-123" in hooks.tool_spans

    @pytest.mark.asyncio
    async def test_adds_event_when_spans_disabled(self, hooks, mocker):
        """Test that event is added when create_tool_spans=False."""
        hooks.create_tool_spans = False
        hooks.session_span = mocker.MagicMock()
        # No need to set metrics - __init__ handles it now

        input_data = {
            "tool_name": "Write",
            "tool_input": {"path": "/test/output.txt", "content": "Hello"},
        }

        await hooks.on_pre_tool_use(input_data, None, {})

        # Verify event was added to session span
        hooks.session_span.add_event.assert_called_once()
        call_args = hooks.session_span.add_event.call_args
        assert "Write" in call_args[0][0]
        assert "input.path" in call_args[0][1]
        assert call_args[0][1]["input.path"] == "/test/output.txt"

    @pytest.mark.asyncio
    async def test_tracks_tool_usage(self, hooks, mocker):
        """Test that tool usage is tracked."""
        hooks.session_span = mocker.MagicMock()
        hooks.create_tool_spans = False
        # No need to set metrics - __init__ handles it now

        input_data = {"tool_name": "Bash", "tool_input": {"command": "ls -la"}}

        await hooks.on_pre_tool_use(input_data, None, {})

        assert hooks.metrics["tools_used"] == 1
        assert "Bash" in hooks.tools_used

    @pytest.mark.asyncio
    async def test_raises_error_without_session_span(self, hooks):
        """Test that error is raised if no session span exists."""
        hooks.session_span = None

        input_data = {"tool_name": "Read", "tool_input": {}}

        with pytest.raises(RuntimeError, match="No active session span"):
            await hooks.on_pre_tool_use(input_data, None, {})


class TestPostToolUse:
    """Tests for on_post_tool_use hook."""

    @pytest.mark.asyncio
    async def test_adds_response_to_event_when_spans_disabled(self, hooks, mocker):
        """Test response is added as event when create_tool_spans=False."""
        hooks.create_tool_spans = False
        hooks.session_span = mocker.MagicMock()

        input_data = {
            "tool_name": "Read",
            "tool_response": {"content": "File contents here", "error": None},
        }

        await hooks.on_post_tool_use(input_data, None, {})

        # Verify event was added
        hooks.session_span.add_event.assert_called_once()
        call_args = hooks.session_span.add_event.call_args
        assert "Read" in call_args[0][0]
        assert call_args[0][1]["response.content"] == "File contents here"
        assert call_args[0][1]["status"] == "success"

    @pytest.mark.asyncio
    async def test_handles_error_responses(self, hooks, mocker):
        """Test that error responses are marked correctly."""
        hooks.create_tool_spans = False
        hooks.session_span = mocker.MagicMock()

        input_data = {
            "tool_name": "Write",
            "tool_response": {"error": "Permission denied", "isError": True},
        }

        await hooks.on_post_tool_use(input_data, None, {})

        call_args = hooks.session_span.add_event.call_args
        assert call_args[0][1]["status"] == "error"
        assert "Permission denied" in call_args[0][1]["error"]

    @pytest.mark.asyncio
    async def test_closes_tool_span_when_enabled(self, hooks, mocker, mock_span):
        """Test that tool span is closed when create_tool_spans=True."""
        hooks.create_tool_spans = True
        hooks.session_span = mocker.MagicMock()
        hooks.tool_spans["tool-123"] = mock_span

        input_data = {
            "tool_name": "Read",
            "tool_response": {"content": "Test content"},
        }

        await hooks.on_post_tool_use(input_data, "tool-123", {})

        # Verify span was ended
        mock_span.end.assert_called_once()
        # Verify span was removed from tracking
        assert "tool-123" not in hooks.tool_spans

    @pytest.mark.asyncio
    async def test_handles_missing_span_gracefully(self, hooks, mocker):
        """Test that missing span is handled without crashing."""
        hooks.create_tool_spans = True
        hooks.session_span = mocker.MagicMock()
        # No span in tool_spans dict

        input_data = {"tool_name": "Read", "tool_response": {"content": "Test"}}

        # Should not raise exception
        await hooks.on_post_tool_use(input_data, "missing-tool", {})


class TestMessageComplete:
    """Tests for on_message_complete hook."""

    @pytest.mark.asyncio
    async def test_updates_token_counts(self, hooks, mocker):
        """Test that token counts are updated correctly."""
        hooks.session_span = mocker.MagicMock()
        hooks.metrics = {
            "input_tokens": 100,
            "output_tokens": 200,
            "turns": 2,
        }

        # Mock message with usage
        message = mocker.MagicMock()
        message.usage.input_tokens = 50
        message.usage.output_tokens = 150

        await hooks.on_message_complete(message, {})

        assert hooks.metrics["input_tokens"] == 150
        assert hooks.metrics["output_tokens"] == 350
        assert hooks.metrics["turns"] == 3

    @pytest.mark.asyncio
    async def test_updates_span_attributes(self, hooks, mocker):
        """Test that span attributes are updated with token counts."""
        hooks.session_span = mocker.MagicMock()
        # No need to set metrics - __init__ handles it now

        message = mocker.MagicMock()
        message.usage.input_tokens = 100
        message.usage.output_tokens = 200

        await hooks.on_message_complete(message, {})

        # Verify span attributes were set
        hooks.session_span.set_attribute.assert_any_call(
            "gen_ai.usage.input_tokens", 100
        )
        hooks.session_span.set_attribute.assert_any_call(
            "gen_ai.usage.output_tokens", 200
        )
        hooks.session_span.set_attribute.assert_any_call("turns", 1)

    @pytest.mark.asyncio
    async def test_stores_assistant_message(self, hooks, mocker):
        """Test that assistant message is stored in history."""
        hooks.session_span = mocker.MagicMock()
        # No need to set metrics - __init__ handles it now

        message = mocker.MagicMock()
        message.usage.input_tokens = 100
        message.usage.output_tokens = 200
        message.content = "Here's my response"

        await hooks.on_message_complete(message, {})

        assert len(hooks.messages) == 1
        assert hooks.messages[0]["role"] == "assistant"
        assert hooks.messages[0]["content"] == "Here's my response"


class TestSessionCompletion:
    """Tests for session completion."""

    def test_sets_final_attributes(self, hooks, mocker):
        """Test that final attributes are set on span."""
        mock_span = mocker.MagicMock()
        hooks.session_span = mock_span
        # Update existing metrics rather than replacing the whole dict
        hooks.metrics["model"] = "claude-3-5-sonnet-20241022"
        hooks.metrics["tools_used"] = 3
        hooks.metrics["start_time"] = time.time()
        hooks.tools_used = ["Read", "Write", "Bash"]

        hooks.complete_session()

        # Check the captured mock span (hooks.session_span is now None)
        mock_span.set_attribute.assert_any_call(
            "gen_ai.request.model", "claude-3-5-sonnet-20241022"
        )
        mock_span.set_attribute.assert_any_call("tools_used", 3)
        # Check tool_names was set with all three tools (order doesn't matter)
        tool_names_calls = [
            call
            for call in mock_span.set_attribute.call_args_list
            if call[0][0] == "tool_names"
        ]
        assert len(tool_names_calls) == 1
        tool_names = set(tool_names_calls[0][0][1].split(","))
        assert tool_names == {"Read", "Write", "Bash"}

    def test_ends_span(self, hooks, mocker):
        """Test that span is ended."""
        mock_span = mocker.MagicMock()
        hooks.session_span = mock_span
        # Update existing metrics rather than replacing
        hooks.metrics["model"] = "test"
        hooks.metrics["start_time"] = time.time()

        hooks.complete_session()

        # Check the captured mock span (hooks.session_span is now None)
        mock_span.end.assert_called_once()

    def test_resets_state(self, hooks, mocker):
        """Test that internal state is reset after completion."""
        hooks.session_span = mocker.MagicMock()
        # Update existing metrics
        hooks.metrics["model"] = "test"
        hooks.metrics["start_time"] = time.time()
        hooks.metrics["tools_used"] = 1
        hooks.messages = [{"role": "user", "content": "test"}]
        hooks.tools_used = ["Read"]
        hooks.tool_spans = {"tool-1": mocker.MagicMock()}

        hooks.complete_session()

        assert hooks.session_span is None
        assert hooks.tool_spans == {}
        assert hooks.metrics == {}
        assert hooks.messages == []
        assert hooks.tools_used == []

    def test_raises_error_without_session_span(self, hooks):
        """Test that error is raised if no session span exists."""
        hooks.session_span = None

        with pytest.raises(RuntimeError, match="No active session span"):
            hooks.complete_session()


class TestContextCompaction:
    """Tests for context compaction hook."""

    @pytest.mark.asyncio
    async def test_adds_compaction_event(self, hooks, mocker):
        """Test that compaction event is added to span."""
        hooks.session_span = mocker.MagicMock()

        input_data = {
            "trigger": "token_limit",
            "custom_instructions": "Keep important context",
        }

        await hooks.on_pre_compact(input_data, None, {})

        hooks.session_span.add_event.assert_called_once()
        call_args = hooks.session_span.add_event.call_args
        assert "Context compaction" in call_args[0][0]
        assert call_args[0][1]["trigger"] == "token_limit"
        assert call_args[0][1]["has_custom_instructions"] is True
