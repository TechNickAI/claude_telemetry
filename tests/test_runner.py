"""Tests for agent runner functions."""

import pytest

from claude_telemetry.runner import extract_message_text, run_agent_with_telemetry


async def _empty_async_generator():
    """Helper to create an empty async generator for mocking."""
    return
    yield  # Make it a generator (unreachable)


class TestExtractMessageText:
    """Tests for extract_message_text function."""

    def test_extracts_string_content(self, mocker):
        """Test extraction from string content."""
        message = mocker.MagicMock()
        message.content = "This is a simple string response"

        result = extract_message_text(message)

        assert result == "This is a simple string response"

    def test_extracts_from_text_blocks(self, mocker):
        """Test extraction from list of text blocks."""
        block1 = mocker.MagicMock()
        block1.text = "First part "
        block2 = mocker.MagicMock()
        block2.text = "Second part"

        message = mocker.MagicMock()
        message.content = [block1, block2]

        result = extract_message_text(message)

        assert result == "First part Second part"

    def test_ignores_blocks_without_text(self, mocker):
        """Test that blocks without text attribute are ignored."""
        block1 = mocker.MagicMock()
        block1.text = "Valid text"
        block2 = mocker.MagicMock(spec=[])  # No text attribute

        message = mocker.MagicMock()
        message.content = [block1, block2]

        result = extract_message_text(message)

        assert result == "Valid text"

    def test_handles_empty_list(self, mocker):
        """Test that empty content list returns empty string."""
        message = mocker.MagicMock()
        message.content = []

        result = extract_message_text(message)

        assert result == ""

    def test_handles_empty_string(self, mocker):
        """Test that empty string content is preserved."""
        message = mocker.MagicMock()
        message.content = ""

        result = extract_message_text(message)

        assert result == ""

    def test_handles_missing_content_attribute(self, mocker):
        """Test that missing content attribute returns empty string."""
        message = mocker.MagicMock(spec=[])  # No content attribute

        result = extract_message_text(message)

        assert result == ""

    def test_converts_other_types_to_string(self, mocker):
        """Test that other content types are converted to string."""
        message = mocker.MagicMock()
        message.content = {"type": "special", "data": "value"}

        result = extract_message_text(message)

        assert isinstance(result, str)
        assert "special" in result or "value" in result

    def test_handles_multiple_text_blocks(self, mocker):
        """Test extraction from multiple text blocks."""
        blocks = [mocker.MagicMock() for _ in range(5)]
        for i, block in enumerate(blocks):
            block.text = f"Part {i} "

        message = mocker.MagicMock()
        message.content = blocks

        result = extract_message_text(message)

        assert result == "Part 0 Part 1 Part 2 Part 3 Part 4 "


class TestRunAgentWithTelemetry:
    """Tests for run_agent_with_telemetry function."""

    @pytest.mark.asyncio
    async def test_configures_telemetry_before_running(self, mocker):
        """Test that telemetry is configured before agent runs."""
        mock_configure = mocker.patch("claude_telemetry.runner.configure_telemetry")
        mock_client = mocker.AsyncMock()
        mock_client_class = mocker.patch(
            "claude_telemetry.runner.ClaudeSDKClient",
            return_value=mock_client,
        )
        mock_client.__aenter__ = mocker.AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = mocker.AsyncMock()
        mock_client.query = mocker.AsyncMock()
        # Make receive_response return an async generator when called
        mock_client.receive_response = mocker.MagicMock(
            return_value=_empty_async_generator()
        )

        await run_agent_with_telemetry(prompt="Test prompt")

        mock_configure.assert_called_once()

    @pytest.mark.asyncio
    async def test_sends_query_to_client(self, mocker):
        """Test that query is sent to Claude client."""
        mocker.patch("claude_telemetry.runner.configure_telemetry")
        mock_client = mocker.AsyncMock()
        mock_client_class = mocker.patch(
            "claude_telemetry.runner.ClaudeSDKClient",
            return_value=mock_client,
        )
        mock_client.__aenter__ = mocker.AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = mocker.AsyncMock()
        mock_client.query = mocker.AsyncMock()
        # Make receive_response return an async generator when called
        mock_client.receive_response = mocker.MagicMock(
            return_value=_empty_async_generator()
        )

        await run_agent_with_telemetry(prompt="Analyze my code")

        mock_client.query.assert_called_once_with(prompt="Analyze my code")

    @pytest.mark.asyncio
    async def test_completes_session_on_success(self, mocker):
        """Test that session is completed after successful execution."""
        mocker.patch("claude_telemetry.runner.configure_telemetry")
        mock_hooks = mocker.MagicMock()
        mock_hooks.session_span = mocker.MagicMock()
        mocker.patch(
            "claude_telemetry.runner.TelemetryHooks",
            return_value=mock_hooks,
        )

        mock_client = mocker.AsyncMock()
        mocker.patch(
            "claude_telemetry.runner.ClaudeSDKClient",
            return_value=mock_client,
        )
        mock_client.__aenter__ = mocker.AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = mocker.AsyncMock()
        mock_client.query = mocker.AsyncMock()
        # Make receive_response return an async generator when called
        mock_client.receive_response = mocker.MagicMock(
            return_value=_empty_async_generator()
        )

        await run_agent_with_telemetry(prompt="Test")

        mock_hooks.complete_session.assert_called_once()

    @pytest.mark.asyncio
    async def test_completes_session_on_error(self, mocker):
        """Test that session is completed even when error occurs."""
        mocker.patch("claude_telemetry.runner.configure_telemetry")
        mock_hooks = mocker.MagicMock()
        mock_hooks.session_span = mocker.MagicMock()
        mocker.patch(
            "claude_telemetry.runner.TelemetryHooks",
            return_value=mock_hooks,
        )

        # Create a proper async mock that raises on query
        mock_client = mocker.AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None

        async def mock_query_error(*args, **kwargs):
            raise Exception("Test error")

        mock_client.query = mock_query_error

        mocker.patch(
            "claude_telemetry.runner.ClaudeSDKClient",
            return_value=mock_client,
        )

        with pytest.raises(Exception, match="Test error"):
            await run_agent_with_telemetry(prompt="Test")

        # Session should still be completed
        mock_hooks.complete_session.assert_called_once()

    @pytest.mark.asyncio
    async def test_passes_model_to_options(self, mocker):
        """Test that model parameter is passed via extra_args."""
        mocker.patch("claude_telemetry.runner.configure_telemetry")
        mock_hooks = mocker.MagicMock()
        mock_hooks.session_span = mocker.MagicMock()
        mocker.patch("claude_telemetry.runner.TelemetryHooks", return_value=mock_hooks)

        mock_options = mocker.MagicMock()
        mock_options_class = mocker.patch(
            "claude_telemetry.runner.ClaudeAgentOptions",
            return_value=mock_options,
        )

        mock_client = mocker.AsyncMock()
        mocker.patch(
            "claude_telemetry.runner.ClaudeSDKClient",
            return_value=mock_client,
        )
        mock_client.__aenter__ = mocker.AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = mocker.AsyncMock()
        mock_client.query = mocker.AsyncMock()
        # Make receive_response return an async generator when called
        mock_client.receive_response = mocker.MagicMock(
            return_value=_empty_async_generator()
        )

        await run_agent_with_telemetry(prompt="Test", extra_args={"model": "opus"})

        # Verify extra_args was passed to options
        call_kwargs = mock_options_class.call_args[1]
        assert call_kwargs["extra_args"] == {"model": "opus"}

    @pytest.mark.asyncio
    async def test_passes_allowed_tools_to_options(self, mocker):
        """Test that allowed_tools parameter is passed via extra_args."""
        mocker.patch("claude_telemetry.runner.configure_telemetry")
        mock_hooks = mocker.MagicMock()
        mock_hooks.session_span = mocker.MagicMock()
        mocker.patch("claude_telemetry.runner.TelemetryHooks", return_value=mock_hooks)

        mock_options_class = mocker.patch("claude_telemetry.runner.ClaudeAgentOptions")

        mock_client = mocker.AsyncMock()
        mocker.patch(
            "claude_telemetry.runner.ClaudeSDKClient",
            return_value=mock_client,
        )
        mock_client.__aenter__ = mocker.AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = mocker.AsyncMock()
        mock_client.query = mocker.AsyncMock()
        # Make receive_response return an async generator when called
        mock_client.receive_response = mocker.MagicMock(
            return_value=_empty_async_generator()
        )

        await run_agent_with_telemetry(
            prompt="Test", extra_args={"allowed-tools": "Read,Write,Bash"}
        )

        # Verify extra_args was passed to options
        call_kwargs = mock_options_class.call_args[1]
        assert call_kwargs["extra_args"] == {"allowed-tools": "Read,Write,Bash"}
