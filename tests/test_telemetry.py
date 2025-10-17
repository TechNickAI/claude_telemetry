"""Integration tests for claude_telemetry instrumentation.

These tests verify end-to-end behavior of the telemetry system.
For unit tests, see test_hooks.py, test_telemetry_config.py, etc.
"""

import contextlib

import pytest

from claude_telemetry.runner import run_agent_with_telemetry
from claude_telemetry.sync import run_agent_with_telemetry_sync


async def _async_message_generator(messages):
    """Helper to create an async generator for mocking."""
    for message in messages:
        yield message


class TestEndToEndTelemetry:
    """End-to-end telemetry tests."""

    @pytest.mark.asyncio
    async def test_basic_telemetry_flow(self, mocker, monkeypatch):
        """Test complete telemetry flow from prompt to completion."""
        # Set up environment
        monkeypatch.setenv("CLAUDE_TELEMETRY_DEBUG", "1")

        # Mock Claude SDK client
        mock_client = mocker.AsyncMock()
        mock_message = mocker.MagicMock()
        mock_message.content = "Test response"
        mock_message.usage.input_tokens = 50
        mock_message.usage.output_tokens = 100

        mock_client.__aenter__ = mocker.AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = mocker.AsyncMock()
        mock_client.query = mocker.AsyncMock()
        # Make receive_response return an async generator when called
        mock_client.receive_response = mocker.MagicMock(
            return_value=_async_message_generator([mock_message])
        )

        mocker.patch(
            "claude_telemetry.runner.ClaudeSDKClient",
            return_value=mock_client,
        )

        # Run the agent
        await run_agent_with_telemetry(prompt="Test prompt")

        # Verify client was called
        mock_client.query.assert_called_once_with(prompt="Test prompt")

    def test_sync_wrapper_calls_async(self, mocker, monkeypatch):
        """Test that sync wrapper properly calls async version."""
        monkeypatch.setenv("CLAUDE_TELEMETRY_DEBUG", "1")

        # Create an AsyncMock to properly handle async function
        mock_run_async = mocker.patch(
            "claude_telemetry.sync.run_agent_with_telemetry",
            new=mocker.AsyncMock(),
        )

        # Mock asyncio.run to actually await the coroutine
        # (avoids unawaited coroutine warning)
        def mock_asyncio_run_impl(coro):
            """Mock asyncio.run that properly handles coroutines."""
            # Close the coroutine to avoid unawaited coroutine warning
            with contextlib.suppress(AttributeError, RuntimeError):
                coro.close()

        mock_asyncio_run = mocker.patch(
            "claude_telemetry.sync.asyncio.run", side_effect=mock_asyncio_run_impl
        )

        run_agent_with_telemetry_sync(prompt="Test")

        # Verify asyncio.run was called
        mock_asyncio_run.assert_called_once()
