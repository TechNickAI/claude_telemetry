"""Tests for telemetry configuration."""

import pytest

from claude_telemetry.telemetry import configure_telemetry


class TestTelemetryConfiguration:
    """Tests for configure_telemetry function."""

    def test_uses_provided_tracer_provider(self, mocker):
        """Test that provided tracer provider is used directly."""
        custom_provider = mocker.MagicMock()
        mock_set_tracer = mocker.patch(
            "claude_telemetry.telemetry.trace.set_tracer_provider"
        )

        result = configure_telemetry(tracer_provider=custom_provider)

        assert result == custom_provider
        mock_set_tracer.assert_called_once_with(custom_provider)

    def test_configures_logfire_when_token_set(self, mocker, monkeypatch):
        """Test Logfire configuration when LOGFIRE_TOKEN is set."""
        monkeypatch.setenv("LOGFIRE_TOKEN", "test_token_12345")

        mock_provider = mocker.MagicMock()
        mock_configure_logfire = mocker.patch(
            "claude_telemetry.logfire_adapter.configure_logfire",
            return_value=mock_provider,
        )

        result = configure_telemetry()

        mock_configure_logfire.assert_called_once_with("claude-agents")
        assert result == mock_provider

    def test_raises_error_when_logfire_not_installed(self, mocker, monkeypatch):
        """Test error when LOGFIRE_TOKEN set but logfire not installed."""
        monkeypatch.setenv("LOGFIRE_TOKEN", "test_token")

        # Use MagicMock explicitly to avoid async mock warnings
        mock_configure = mocker.MagicMock(
            side_effect=ImportError("No module named 'logfire'")
        )
        mocker.patch(
            "claude_telemetry.logfire_adapter.configure_logfire",
            mock_configure,
        )

        with pytest.raises(RuntimeError, match="logfire package not installed"):
            configure_telemetry()

    def test_configures_otel_when_endpoint_set(self, mocker, monkeypatch):
        """Test OTEL configuration when OTEL_EXPORTER_OTLP_ENDPOINT is set."""
        monkeypatch.delenv("LOGFIRE_TOKEN", raising=False)
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "https://api.honeycomb.io")
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_HEADERS", "x-honeycomb-team=test_key")

        mock_provider = mocker.MagicMock()
        mock_configure_otel = mocker.patch(
            "claude_telemetry.telemetry._configure_otel",
            return_value=mock_provider,
        )

        result = configure_telemetry()

        mock_configure_otel.assert_called_once_with(
            "https://api.honeycomb.io", "claude-agents"
        )
        assert result == mock_provider

    def test_uses_debug_mode_when_env_set(self, mocker, monkeypatch):
        """Test console exporter when CLAUDE_TELEMETRY_DEBUG is set."""
        monkeypatch.delenv("LOGFIRE_TOKEN", raising=False)
        monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
        monkeypatch.setenv("CLAUDE_TELEMETRY_DEBUG", "1")

        mock_provider = mocker.MagicMock()
        mock_configure_console = mocker.patch(
            "claude_telemetry.telemetry._configure_console_exporter",
            return_value=mock_provider,
        )

        result = configure_telemetry()

        mock_configure_console.assert_called_once_with("claude-agents")
        assert result == mock_provider

    def test_raises_error_when_no_backend_configured(self, monkeypatch):
        """Test error when no telemetry backend is configured."""
        monkeypatch.delenv("LOGFIRE_TOKEN", raising=False)
        monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
        monkeypatch.delenv("CLAUDE_TELEMETRY_DEBUG", raising=False)

        with pytest.raises(RuntimeError, match="No telemetry backend configured"):
            configure_telemetry()

    def test_uses_custom_service_name(self, mocker, monkeypatch):
        """Test that custom service name is passed through."""
        monkeypatch.setenv("LOGFIRE_TOKEN", "test_token")

        mock_configure_logfire = mocker.patch(
            "claude_telemetry.logfire_adapter.configure_logfire"
        )

        configure_telemetry(service_name="my-custom-service")

        mock_configure_logfire.assert_called_once_with("my-custom-service")

    def test_configuration_precedence(self, mocker, monkeypatch):
        """Test that configuration precedence is: provider > logfire > otel > debug."""
        # Set all possible configurations
        monkeypatch.setenv("LOGFIRE_TOKEN", "test_token")
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "https://example.com")
        monkeypatch.setenv("CLAUDE_TELEMETRY_DEBUG", "1")

        custom_provider = mocker.MagicMock()
        mock_set_tracer = mocker.patch(
            "claude_telemetry.telemetry.trace.set_tracer_provider"
        )
        mock_configure_logfire = mocker.patch(
            "claude_telemetry.logfire_adapter.configure_logfire"
        )

        # Provided tracer should win
        configure_telemetry(tracer_provider=custom_provider)
        mock_set_tracer.assert_called_with(custom_provider)
        mock_configure_logfire.assert_not_called()


class TestOTELConfiguration:
    """Tests for OTEL exporter configuration."""

    def test_appends_v1_traces_to_endpoint(self, mocker, monkeypatch):
        """Test that /v1/traces is appended if not present."""
        from claude_telemetry.telemetry import _configure_otel  # noqa: PLC0415

        monkeypatch.setenv("OTEL_EXPORTER_OTLP_HEADERS", "")

        mock_exporter = mocker.patch("claude_telemetry.telemetry.OTLPSpanExporter")
        mock_provider = mocker.patch("claude_telemetry.telemetry.TracerProvider")
        mocker.patch("claude_telemetry.telemetry.trace.set_tracer_provider")

        _configure_otel("https://api.honeycomb.io", "test-service")

        # Verify endpoint has /v1/traces
        call_args = mock_exporter.call_args
        assert call_args[1]["endpoint"] == "https://api.honeycomb.io/v1/traces"

    def test_does_not_double_append_v1_traces(self, mocker, monkeypatch):
        """Test that /v1/traces is not doubled if already present."""
        from claude_telemetry.telemetry import _configure_otel  # noqa: PLC0415

        monkeypatch.setenv("OTEL_EXPORTER_OTLP_HEADERS", "")

        mock_exporter = mocker.patch("claude_telemetry.telemetry.OTLPSpanExporter")
        mocker.patch("claude_telemetry.telemetry.TracerProvider")
        mocker.patch("claude_telemetry.telemetry.trace.set_tracer_provider")

        _configure_otel("https://api.honeycomb.io/v1/traces", "test-service")

        call_args = mock_exporter.call_args
        assert call_args[1]["endpoint"] == "https://api.honeycomb.io/v1/traces"

    def test_parses_headers_from_env(self, mocker, monkeypatch):
        """Test that OTEL headers are parsed correctly."""
        from claude_telemetry.telemetry import _configure_otel  # noqa: PLC0415

        monkeypatch.setenv(
            "OTEL_EXPORTER_OTLP_HEADERS",
            "x-honeycomb-team=test_key,x-honeycomb-dataset=prod",
        )

        mock_exporter = mocker.patch("claude_telemetry.telemetry.OTLPSpanExporter")
        mocker.patch("claude_telemetry.telemetry.TracerProvider")
        mocker.patch("claude_telemetry.telemetry.trace.set_tracer_provider")

        _configure_otel("https://api.honeycomb.io", "test-service")

        call_args = mock_exporter.call_args
        headers = call_args[1]["headers"]
        assert headers["x-honeycomb-team"] == "test_key"
        assert headers["x-honeycomb-dataset"] == "prod"

    def test_sets_service_name_in_resource(self, mocker, monkeypatch):
        """Test that service name is set in OTEL resource."""
        from claude_telemetry.telemetry import _configure_otel  # noqa: PLC0415

        monkeypatch.setenv("OTEL_EXPORTER_OTLP_HEADERS", "")

        mock_resource = mocker.patch("claude_telemetry.telemetry.Resource.create")
        mocker.patch("claude_telemetry.telemetry.OTLPSpanExporter")
        mocker.patch("claude_telemetry.telemetry.TracerProvider")
        mocker.patch("claude_telemetry.telemetry.trace.set_tracer_provider")

        _configure_otel("https://example.com", "my-service")

        mock_resource.assert_called_once_with({"service.name": "my-service"})


class TestConsoleExporter:
    """Tests for console exporter configuration."""

    def test_configures_console_exporter(self, mocker):
        """Test that console exporter is configured for debug mode."""
        from claude_telemetry.telemetry import (  # noqa: PLC0415
            _configure_console_exporter,
        )

        mock_console_exporter = mocker.patch(
            "claude_telemetry.telemetry.ConsoleSpanExporter"
        )
        mock_provider = mocker.patch("claude_telemetry.telemetry.TracerProvider")
        mocker.patch("claude_telemetry.telemetry.trace.set_tracer_provider")

        _configure_console_exporter("debug-service")

        mock_console_exporter.assert_called_once()
        mock_provider.assert_called_once()
