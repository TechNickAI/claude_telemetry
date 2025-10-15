"""Shared pytest fixtures for claude_telemetry tests."""

from opentelemetry import trace
from opentelemetry.trace import ProxyTracerProvider
import pytest


@pytest.fixture(autouse=True)
def reset_environment(monkeypatch):
    """
    Reset environment variables before each test.

    This ensures tests don't interfere with each other through
    environment state.
    """
    # Clear telemetry-related env vars
    monkeypatch.delenv("LOGFIRE_TOKEN", raising=False)
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_HEADERS", raising=False)
    monkeypatch.delenv("CLAUDE_TELEMETRY_DEBUG", raising=False)


@pytest.fixture(autouse=True)
def reset_tracer_provider():
    """
    Reset the global tracer provider before each test.

    This prevents state from Logfire's pytest plugin or previous tests
    from interfering with test isolation.
    """
    # Reset to a fresh ProxyTracerProvider
    trace._TRACER_PROVIDER = None
    trace.set_tracer_provider(ProxyTracerProvider())
    yield
    # Clean up after test
    trace._TRACER_PROVIDER = None
    trace.set_tracer_provider(ProxyTracerProvider())


@pytest.fixture
def mock_tracer_provider(mocker):
    """Create a mock TracerProvider for testing."""
    provider = mocker.MagicMock()
    provider.get_tracer = mocker.MagicMock()
    provider.force_flush = mocker.MagicMock()
    return provider


@pytest.fixture
def mock_span(mocker):
    """Create a mock OpenTelemetry span."""
    span = mocker.MagicMock()
    span.set_attribute = mocker.MagicMock()
    span.add_event = mocker.MagicMock()
    span.end = mocker.MagicMock()
    span.set_status = mocker.MagicMock()
    return span


@pytest.fixture
def mock_tracer(mocker, mock_span):
    """Create a mock OpenTelemetry tracer."""
    tracer = mocker.MagicMock()
    tracer.start_span = mocker.MagicMock(return_value=mock_span)
    return tracer


@pytest.fixture
def sample_claude_message(mocker):
    """Create a sample Claude SDK message for testing."""
    message = mocker.MagicMock()
    message.content = "This is a test response from Claude"
    message.usage.input_tokens = 100
    message.usage.output_tokens = 200
    return message


@pytest.fixture
def sample_tool_input():
    """Sample tool input data."""
    return {
        "tool_name": "Read",
        "tool_input": {
            "path": "/test/file.py",
        },
    }


@pytest.fixture
def sample_tool_response():
    """Sample tool response data."""
    return {
        "content": "def hello():\n    return 'world'",
        "error": None,
        "isError": False,
    }


@pytest.fixture
def mock_console(mocker):
    """Mock Rich Console for testing CLI output."""
    console = mocker.MagicMock()
    console.print = mocker.MagicMock()
    return console
