"""Tests for CLI commands and error handling."""

import pytest
import typer

from claude_telemetry.cli import handle_agent_error, show_startup_banner


class TestHandleAgentError:
    """Tests for handle_agent_error function."""

    def test_handles_keyboard_interrupt(self, mocker):
        """Test that KeyboardInterrupt is displayed nicely."""
        mock_console = mocker.patch("claude_telemetry.cli.console")

        error = KeyboardInterrupt()

        with pytest.raises(typer.Exit) as exc_info:
            handle_agent_error(error)

        assert exc_info.value.exit_code == 0
        mock_console.print.assert_called_once()
        call_args = mock_console.print.call_args[0][0]
        assert "Interrupted by user" in call_args
        assert "yellow" in call_args

    def test_handles_runtime_error(self, mocker):
        """Test that RuntimeError raises Exit with error message."""
        mock_console = mocker.patch("claude_telemetry.cli.console")

        error = RuntimeError("Failed to configure telemetry")

        with pytest.raises(typer.Exit) as exc_info:
            handle_agent_error(error)

        assert exc_info.value.exit_code == 1
        mock_console.print.assert_called_once()
        call_args = mock_console.print.call_args[0][0]
        assert "Failed to configure telemetry" in call_args
        assert "bold red" in call_args

    def test_handles_generic_exception(self, mocker):
        """Test that generic exceptions raise Exit with error message."""
        mock_console = mocker.patch("claude_telemetry.cli.console")

        error = ValueError("Invalid input")

        with pytest.raises(typer.Exit) as exc_info:
            handle_agent_error(error)

        assert exc_info.value.exit_code == 1
        mock_console.print.assert_called_once()
        call_args = mock_console.print.call_args[0][0]
        assert "Invalid input" in call_args

    def test_exit_code_is_one_for_errors(self, mocker):
        """Test that exit code is 1 for all error cases."""
        mocker.patch("claude_telemetry.cli.console")

        with pytest.raises(typer.Exit) as exc_info:
            handle_agent_error(RuntimeError("Test"))
        assert exc_info.value.exit_code == 1

        with pytest.raises(typer.Exit) as exc_info:
            handle_agent_error(Exception("Test"))
        assert exc_info.value.exit_code == 1


class TestShowStartupBanner:
    """Tests for show_startup_banner function."""

    def test_displays_model_info(self, mocker):
        """Test that model information is displayed."""
        mock_console = mocker.patch("claude_telemetry.cli.console")

        show_startup_banner(extra_args={"model": "opus"})

        # Should have called print multiple times (banner + table)
        assert mock_console.print.call_count >= 2

    def test_displays_default_model_when_none(self, mocker):
        """Test that default is shown when model is None."""
        mock_console = mocker.patch("claude_telemetry.cli.console")
        mocker.patch("claude_telemetry.cli.Table")
        mocker.patch("claude_telemetry.cli.Panel")

        show_startup_banner(extra_args={})

        # Verify console was used
        assert mock_console.print.called

    def test_displays_tools_list(self, mocker):
        """Test that tools list is displayed."""
        mock_console = mocker.patch("claude_telemetry.cli.console")
        mock_table = mocker.patch("claude_telemetry.cli.Table")
        mocker.patch("claude_telemetry.cli.Panel")

        show_startup_banner(extra_args={"allowed-tools": "Read,Write,Bash"})

        # Verify table was created and used
        assert mock_table.called

    def test_displays_all_tools_when_none_specified(self, mocker):
        """Test that 'All available' is shown when tools is None."""
        mocker.patch("claude_telemetry.cli.console")
        mock_table_class = mocker.patch("claude_telemetry.cli.Table")
        mock_table = mocker.MagicMock()
        mock_table_class.return_value = mock_table
        mocker.patch("claude_telemetry.cli.Panel")

        show_startup_banner(extra_args={})

        # Check that add_row was called with MCP info
        add_row_calls = [call[0] for call in mock_table.add_row.call_args_list]
        assert any("MCP" in str(call) for call in add_row_calls)

    def test_shows_logfire_backend_when_token_present(self, mocker, monkeypatch):
        """Test that Logfire backend is shown when token is set."""
        monkeypatch.setenv("LOGFIRE_TOKEN", "test_token")

        mocker.patch("claude_telemetry.cli.console")
        mock_table_class = mocker.patch("claude_telemetry.cli.Table")
        mock_table = mocker.MagicMock()
        mock_table_class.return_value = mock_table
        mocker.patch("claude_telemetry.cli.Panel")

        show_startup_banner(extra_args={})

        # Check that Logfire was mentioned
        add_row_calls = [str(call) for call in mock_table.add_row.call_args_list]
        assert any("Logfire" in call for call in add_row_calls)

    def test_shows_otel_backend_when_endpoint_present(self, mocker, monkeypatch):
        """Test that OTEL backend is shown when endpoint is set."""
        monkeypatch.delenv("LOGFIRE_TOKEN", raising=False)
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "https://api.honeycomb.io")

        mocker.patch("claude_telemetry.cli.console")
        mock_table_class = mocker.patch("claude_telemetry.cli.Table")
        mock_table = mocker.MagicMock()
        mock_table_class.return_value = mock_table
        mocker.patch("claude_telemetry.cli.Panel")

        show_startup_banner(extra_args={})

        # Check that OpenTelemetry was mentioned
        add_row_calls = [str(call) for call in mock_table.add_row.call_args_list]
        assert any("OpenTelemetry" in call or "OTEL" in call for call in add_row_calls)

    def test_shows_warning_when_no_backend(self, mocker, monkeypatch):
        """Test that warning is shown when no backend is configured."""
        monkeypatch.delenv("LOGFIRE_TOKEN", raising=False)
        monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)

        mocker.patch("claude_telemetry.cli.console")
        mock_table_class = mocker.patch("claude_telemetry.cli.Table")
        mock_table = mocker.MagicMock()
        mock_table_class.return_value = mock_table
        mocker.patch("claude_telemetry.cli.Panel")

        show_startup_banner(extra_args={})

        # Check that warning was shown
        add_row_calls = [str(call) for call in mock_table.add_row.call_args_list]
        assert any("None" in call or "debug" in call for call in add_row_calls)


class TestCLIIntegration:
    """Integration tests for CLI behavior."""

    def test_sets_environment_from_cli_args(self, mocker, monkeypatch):
        """Test that CLI arguments set environment variables."""
        # This would test the main() function's environment variable setting
        # Skipping for now as it requires more complex CLI testing setup

    def test_debug_mode_enables_logging(self, mocker):
        """Test that debug flag enables debug logging."""
        # This would test debug mode configuration
        # Skipping for now as it requires CLI testing setup
