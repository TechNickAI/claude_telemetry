"""Tests for Logfire adapter."""

import pytest


class TestConfigureLogfire:
    """Tests for configure_logfire function."""

    def test_configures_with_token(self, mocker, monkeypatch):
        """Test Logfire configuration with valid token."""
        monkeypatch.setenv("LOGFIRE_TOKEN", "test_token_12345")

        mock_logfire = mocker.MagicMock()
        mock_logfire.configure = mocker.MagicMock()
        mocker.patch.dict("sys.modules", {"logfire": mock_logfire})

        mock_provider = mocker.MagicMock()
        mocker.patch(
            "claude_telemetry.logfire_adapter.trace.get_tracer_provider",
            return_value=mock_provider,
        )

        from claude_telemetry.logfire_adapter import configure_logfire  # noqa: PLC0415

        result = configure_logfire(service_name="test-service")

        mock_logfire.configure.assert_called_once_with(
            service_name="test-service",
            send_to_logfire=True,
        )
        assert result == mock_provider

    def test_raises_error_without_token(self, mocker, monkeypatch):
        """Test that error is raised when LOGFIRE_TOKEN is not set."""
        monkeypatch.delenv("LOGFIRE_TOKEN", raising=False)

        mock_logfire = mocker.MagicMock()
        mocker.patch.dict("sys.modules", {"logfire": mock_logfire})

        from claude_telemetry.logfire_adapter import configure_logfire  # noqa: PLC0415

        with pytest.raises(ValueError, match="LOGFIRE_TOKEN"):
            configure_logfire()

    def test_uses_default_service_name(self, mocker, monkeypatch):
        """Test that default service name is used."""
        monkeypatch.setenv("LOGFIRE_TOKEN", "test_token")

        mock_logfire = mocker.MagicMock()
        mock_logfire.configure = mocker.MagicMock()
        mocker.patch.dict("sys.modules", {"logfire": mock_logfire})

        mocker.patch("claude_telemetry.logfire_adapter.trace.get_tracer_provider")

        from claude_telemetry.logfire_adapter import configure_logfire  # noqa: PLC0415

        configure_logfire()

        call_kwargs = mock_logfire.configure.call_args[1]
        assert call_kwargs["service_name"] == "claude-agents"

    def test_propagates_configuration_errors(self, mocker, monkeypatch):
        """Test that Logfire configuration errors are propagated."""
        monkeypatch.setenv("LOGFIRE_TOKEN", "invalid_token")

        mock_logfire = mocker.MagicMock()
        mock_logfire.configure = mocker.MagicMock(
            side_effect=Exception("Invalid token")
        )
        mocker.patch.dict("sys.modules", {"logfire": mock_logfire})

        from claude_telemetry.logfire_adapter import configure_logfire  # noqa: PLC0415

        with pytest.raises(Exception, match="Invalid token"):
            configure_logfire()


class TestGetLogfire:
    """Tests for get_logfire function."""

    def test_returns_logfire_when_imported(self, mocker):
        """Test that logfire module is returned when imported."""
        mock_logfire = mocker.MagicMock()
        mocker.patch.dict("sys.modules", {"logfire": mock_logfire})

        from claude_telemetry.logfire_adapter import get_logfire  # noqa: PLC0415

        result = get_logfire()

        assert result == mock_logfire

    def test_returns_none_when_not_imported(self, mocker):
        """Test that None is returned when logfire not imported."""
        # Ensure logfire is not in sys.modules
        mocker.patch.dict("sys.modules", {"logfire": None}, clear=False)

        from claude_telemetry.logfire_adapter import get_logfire  # noqa: PLC0415

        result = get_logfire()

        assert result is None

    def test_does_not_import_logfire(self, mocker):
        """Test that get_logfire doesn't import logfire itself."""
        # This function should only check sys.modules, not import
        mock_import = mocker.patch("builtins.__import__")
        mocker.patch.dict("sys.modules", {}, clear=True)

        from claude_telemetry.logfire_adapter import get_logfire  # noqa: PLC0415

        get_logfire()

        # Should not have attempted to import
        assert not any(call[0][0] == "logfire" for call in mock_import.call_args_list)
