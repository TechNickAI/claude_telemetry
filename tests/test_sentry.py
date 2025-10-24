"""Tests for Sentry adapter."""

import pytest


class TestConfigureSentry:
    """Tests for configure_sentry function."""

    def test_configures_with_dsn(self, mocker, monkeypatch):
        """Test Sentry configuration with valid DSN."""
        monkeypatch.setenv("SENTRY_DSN", "https://test@sentry.io/123")

        mock_sentry = mocker.MagicMock()
        mock_sentry.init = mocker.MagicMock()

        mock_logging_integration = mocker.MagicMock()
        mock_span_processor = mocker.MagicMock()
        mocker.patch.dict(
            "sys.modules",
            {
                "sentry_sdk": mock_sentry,
                "sentry_sdk.integrations": mocker.MagicMock(),
                "sentry_sdk.integrations.logging": mocker.MagicMock(
                    LoggingIntegration=mock_logging_integration
                ),
                "sentry_sdk.integrations.opentelemetry": mocker.MagicMock(
                    SentrySpanProcessor=mock_span_processor
                ),
            },
        )

        mock_provider = mocker.MagicMock()
        mocker.patch(
            "claude_telemetry.sentry_adapter.TracerProvider",
            return_value=mock_provider,
        )
        mocker.patch("claude_telemetry.sentry_adapter.trace.set_tracer_provider")

        from claude_telemetry.sentry_adapter import configure_sentry  # noqa: PLC0415

        result = configure_sentry(service_name="test-service")

        mock_sentry.init.assert_called_once()
        call_kwargs = mock_sentry.init.call_args[1]
        assert call_kwargs["dsn"] == "https://test@sentry.io/123"
        assert call_kwargs["traces_sample_rate"] == 1.0
        assert call_kwargs["environment"] == "production"
        assert result == mock_provider

    def test_raises_error_without_dsn(self, mocker, monkeypatch):
        """Test that error is raised when SENTRY_DSN is not set."""
        monkeypatch.delenv("SENTRY_DSN", raising=False)

        mock_sentry = mocker.MagicMock()
        mock_logging_integration = mocker.MagicMock()
        mock_span_processor = mocker.MagicMock()
        mocker.patch.dict(
            "sys.modules",
            {
                "sentry_sdk": mock_sentry,
                "sentry_sdk.integrations": mocker.MagicMock(),
                "sentry_sdk.integrations.logging": mocker.MagicMock(
                    LoggingIntegration=mock_logging_integration
                ),
                "sentry_sdk.integrations.opentelemetry": mocker.MagicMock(
                    SentrySpanProcessor=mock_span_processor
                ),
            },
        )

        from claude_telemetry.sentry_adapter import configure_sentry  # noqa: PLC0415

        with pytest.raises(ValueError, match="SENTRY_DSN"):
            configure_sentry()

    def test_uses_custom_environment(self, mocker, monkeypatch):
        """Test that custom environment is used when set."""
        monkeypatch.setenv("SENTRY_DSN", "https://test@sentry.io/123")
        monkeypatch.setenv("SENTRY_ENVIRONMENT", "staging")

        mock_sentry = mocker.MagicMock()
        mock_sentry.init = mocker.MagicMock()

        mock_logging_integration = mocker.MagicMock()
        mock_span_processor = mocker.MagicMock()
        mocker.patch.dict(
            "sys.modules",
            {
                "sentry_sdk": mock_sentry,
                "sentry_sdk.integrations": mocker.MagicMock(),
                "sentry_sdk.integrations.logging": mocker.MagicMock(
                    LoggingIntegration=mock_logging_integration
                ),
                "sentry_sdk.integrations.opentelemetry": mocker.MagicMock(
                    SentrySpanProcessor=mock_span_processor
                ),
            },
        )

        mocker.patch("claude_telemetry.sentry_adapter.TracerProvider")
        mocker.patch("claude_telemetry.sentry_adapter.trace.set_tracer_provider")

        from claude_telemetry.sentry_adapter import configure_sentry  # noqa: PLC0415

        configure_sentry()

        call_kwargs = mock_sentry.init.call_args[1]
        assert call_kwargs["environment"] == "staging"

    def test_uses_custom_sample_rate(self, mocker, monkeypatch):
        """Test that custom sample rate is used when set."""
        monkeypatch.setenv("SENTRY_DSN", "https://test@sentry.io/123")
        monkeypatch.setenv("SENTRY_TRACES_SAMPLE_RATE", "0.5")

        mock_sentry = mocker.MagicMock()
        mock_sentry.init = mocker.MagicMock()

        mock_logging_integration = mocker.MagicMock()
        mock_span_processor = mocker.MagicMock()
        mocker.patch.dict(
            "sys.modules",
            {
                "sentry_sdk": mock_sentry,
                "sentry_sdk.integrations": mocker.MagicMock(),
                "sentry_sdk.integrations.logging": mocker.MagicMock(
                    LoggingIntegration=mock_logging_integration
                ),
                "sentry_sdk.integrations.opentelemetry": mocker.MagicMock(
                    SentrySpanProcessor=mock_span_processor
                ),
            },
        )

        mocker.patch("claude_telemetry.sentry_adapter.TracerProvider")
        mocker.patch("claude_telemetry.sentry_adapter.trace.set_tracer_provider")

        from claude_telemetry.sentry_adapter import configure_sentry  # noqa: PLC0415

        configure_sentry()

        call_kwargs = mock_sentry.init.call_args[1]
        assert call_kwargs["traces_sample_rate"] == 0.5

    def test_uses_default_service_name(self, mocker, monkeypatch):
        """Test that default service name is used."""
        monkeypatch.setenv("SENTRY_DSN", "https://test@sentry.io/123")

        mock_sentry = mocker.MagicMock()
        mock_sentry.init = mocker.MagicMock()

        mock_logging_integration = mocker.MagicMock()
        mock_span_processor = mocker.MagicMock()
        mocker.patch.dict(
            "sys.modules",
            {
                "sentry_sdk": mock_sentry,
                "sentry_sdk.integrations": mocker.MagicMock(),
                "sentry_sdk.integrations.logging": mocker.MagicMock(
                    LoggingIntegration=mock_logging_integration
                ),
                "sentry_sdk.integrations.opentelemetry": mocker.MagicMock(
                    SentrySpanProcessor=mock_span_processor
                ),
            },
        )

        mock_provider = mocker.MagicMock()
        mock_provider_class = mocker.patch(
            "claude_telemetry.sentry_adapter.TracerProvider",
            return_value=mock_provider,
        )
        mocker.patch("claude_telemetry.sentry_adapter.trace.set_tracer_provider")

        from claude_telemetry.sentry_adapter import configure_sentry  # noqa: PLC0415

        configure_sentry()

        # Check the Resource was created with default service name
        call_args = mock_provider_class.call_args[1]
        resource = call_args["resource"]
        assert resource.attributes["service.name"] == "claude-agents"


class TestGetSentry:
    """Tests for get_sentry function."""

    def test_returns_sentry_when_imported(self, mocker):
        """Test that sentry_sdk module is returned when imported."""
        mock_sentry = mocker.MagicMock()
        mocker.patch.dict(
            "sys.modules",
            {
                "sentry_sdk": mock_sentry,
                "sentry_sdk.integrations": mocker.MagicMock(),
                "sentry_sdk.integrations.logging": mocker.MagicMock(),
                "sentry_sdk.integrations.opentelemetry": mocker.MagicMock(),
            },
        )

        from claude_telemetry.sentry_adapter import get_sentry  # noqa: PLC0415

        result = get_sentry()

        assert result == mock_sentry

    def test_returns_none_when_not_imported(self, mocker):
        """Test that None is returned when sentry_sdk not imported."""
        mocker.patch.dict(
            "sys.modules",
            {
                "sentry_sdk": None,
                "sentry_sdk.integrations": None,
                "sentry_sdk.integrations.logging": None,
                "sentry_sdk.integrations.opentelemetry": None,
            },
            clear=False,
        )

        from claude_telemetry.sentry_adapter import get_sentry  # noqa: PLC0415

        result = get_sentry()

        assert result is None

    def test_does_not_import_sentry(self, mocker):
        """Test that get_sentry doesn't import sentry_sdk itself."""
        mock_import = mocker.patch("builtins.__import__")
        mocker.patch.dict("sys.modules", {}, clear=True)

        from claude_telemetry.sentry_adapter import get_sentry  # noqa: PLC0415

        get_sentry()

        # Should not have attempted to import
        assert not any(
            call[0][0] == "sentry_sdk" for call in mock_import.call_args_list
        )
