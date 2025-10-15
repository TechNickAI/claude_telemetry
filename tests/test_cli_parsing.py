"""Tests for CLI argument parsing."""

import os
import sys

import pytest

from claude_telemetry.cli import _parse_flags, parse_args


class TestParseFlags:
    """Tests for _parse_flags function."""

    def test_parses_flag_with_equals(self):
        """Test parsing --flag=value format."""
        args = ["--model=opus", "--debug=api"]
        result = _parse_flags(args)

        assert result == {"model": "opus", "debug": "api"}

    def test_parses_flag_with_space(self):
        """Test parsing --flag value format."""
        args = ["--model", "opus", "--permission-mode", "bypassPermissions"]
        result = _parse_flags(args)

        assert result == {"model": "opus", "permission-mode": "bypassPermissions"}

    def test_parses_boolean_flag(self):
        """Test parsing boolean flag without value."""
        args = ["--debug", "--verbose"]
        result = _parse_flags(args)

        assert result == {"debug": None, "verbose": None}

    def test_parses_short_flags(self):
        """Test parsing short flags with -."""
        args = ["-m", "opus", "-d"]
        result = _parse_flags(args)

        assert result == {"m": "opus", "d": None}

    def test_parses_mixed_formats(self):
        """Test parsing mix of equals and space formats."""
        args = ["--model=opus", "--debug", "api", "-v"]
        result = _parse_flags(args)

        assert result == {"model": "opus", "debug": "api", "v": None}

    def test_handles_empty_list(self):
        """Test parsing empty args list."""
        args = []
        result = _parse_flags(args)

        assert result == {}


class TestParseArgs:
    """Tests for parse_args function."""

    def test_extracts_prompt_from_end(self, monkeypatch):
        """Test that prompt is extracted from the end."""
        monkeypatch.setattr(sys, "argv", ["claudia", "--model=opus", "hello world"])

        prompt, extra_args, debug = parse_args()

        assert prompt == "hello world"
        assert extra_args == {"model": "opus"}
        assert debug is False

    def test_extracts_prompt_with_flags_before(self, monkeypatch):
        """Test prompt extraction with flags before it."""
        monkeypatch.setattr(
            sys,
            "argv",
            ["claudia", "--permission-mode", "bypassPermissions", "analyze code"],
        )

        prompt, extra_args, debug = parse_args()

        assert prompt == "analyze code"
        assert extra_args == {"permission-mode": "bypassPermissions"}

    def test_handles_no_prompt_interactive_mode(self, monkeypatch):
        """Test that no prompt means interactive mode."""
        monkeypatch.setattr(sys, "argv", ["claudia", "--model=opus"])

        prompt, extra_args, debug = parse_args()

        assert prompt is None
        assert extra_args == {"model": "opus"}

    def test_extracts_claudia_specific_flags(self, monkeypatch, mocker):
        """Test that claudia-specific flags are extracted."""
        monkeypatch.setattr(
            sys, "argv", ["claudia", "--claudia-debug", "--model=opus", "test"]
        )
        mock_configure = mocker.patch("claude_telemetry.cli.configure_logger")

        prompt, extra_args, debug = parse_args()

        assert prompt == "test"
        assert extra_args == {"model": "opus"}
        assert debug is True
        mock_configure.assert_called_once_with(debug=True)

    def test_sets_environment_variables(self, monkeypatch):
        """Test that telemetry env vars are set with space format."""
        # Explicitly set to empty first to avoid side effects
        monkeypatch.setenv("LOGFIRE_TOKEN", "")
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "")
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_HEADERS", "")

        monkeypatch.setattr(
            sys,
            "argv",
            [
                "claudia",
                "--logfire-token",
                "test_token",
                "--otel-endpoint",
                "https://test.com",
                "--otel-headers",
                "auth=bearer",
                "test",
            ],
        )

        prompt, extra_args, debug = parse_args()

        assert os.getenv("LOGFIRE_TOKEN") == "test_token"
        assert os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT") == "https://test.com"
        assert os.getenv("OTEL_EXPORTER_OTLP_HEADERS") == "auth=bearer"

    def test_sets_environment_variables_with_equals_format(self, monkeypatch):
        """Test that telemetry env vars are set with --flag=value format."""
        # Explicitly set to empty first to avoid side effects
        monkeypatch.setenv("LOGFIRE_TOKEN", "")
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "")
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_HEADERS", "")

        monkeypatch.setattr(
            sys,
            "argv",
            [
                "claudia",
                "--logfire-token=test_token",
                "--otel-endpoint=https://test.com",
                "--otel-headers=auth=bearer",
                "test",
            ],
        )

        prompt, extra_args, debug = parse_args()

        assert os.getenv("LOGFIRE_TOKEN") == "test_token"
        assert os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT") == "https://test.com"
        assert os.getenv("OTEL_EXPORTER_OTLP_HEADERS") == "auth=bearer"

    def test_handles_version_flag(self, monkeypatch, mocker):
        """Test that --version exits."""
        monkeypatch.setattr(sys, "argv", ["claudia", "--version"])
        mock_console = mocker.patch("claude_telemetry.cli.console")

        with pytest.raises(SystemExit):
            parse_args()

        # Should print version
        assert mock_console.print.called

    def test_handles_config_command(self, monkeypatch, mocker):
        """Test that config command exits."""
        monkeypatch.setattr(sys, "argv", ["claudia", "config"])
        mocker.patch("claude_telemetry.cli.show_config")

        with pytest.raises(SystemExit):
            parse_args()

    def test_handles_help_flag(self, monkeypatch, mocker):
        """Test that --help exits."""
        monkeypatch.setattr(sys, "argv", ["claudia", "--help"])
        mocker.patch("claude_telemetry.cli.show_help")

        with pytest.raises(SystemExit):
            parse_args()

    def test_prompt_not_confused_with_flag_value_when_using_equals(self, monkeypatch):
        """Test that prompt is correctly identified when using = format."""
        monkeypatch.setattr(
            sys, "argv", ["claudia", "--model=opus", "--debug=api", "do something"]
        )

        prompt, extra_args, debug = parse_args()

        assert prompt == "do something"
        assert extra_args == {"model": "opus", "debug": "api"}
        assert debug is False

    def test_multiple_pass_through_flags(self, monkeypatch):
        """Test multiple Claude CLI flags pass through."""
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "claudia",
                "--model=opus",
                "--permission-mode=bypassPermissions",
                "--max-turns=5",
                "analyze",
            ],
        )

        prompt, extra_args, debug = parse_args()

        assert prompt == "analyze"
        assert extra_args == {
            "model": "opus",
            "permission-mode": "bypassPermissions",
            "max-turns": "5",
        }
