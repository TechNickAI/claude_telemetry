"""Tests for formatting functions."""

from claude_telemetry.hooks import (
    _format_tool_input_for_console,
    _format_tool_response_for_console,
    _smart_truncate_value,
    add_response_to_event_data,
    create_completion_title,
    create_event_data,
    create_tool_title,
)


class TestSmartTruncateValue:
    """Tests for _smart_truncate_value function."""

    def test_short_string_unchanged(self):
        """Short strings should not be truncated."""
        result = _smart_truncate_value("short", max_length=100)
        assert result == "short"

    def test_long_string_truncated(self):
        """Long strings should be truncated with ellipsis."""
        long_str = "a" * 200
        result = _smart_truncate_value(long_str, max_length=50)
        assert len(result) == 53  # 50 + "..."
        assert result.endswith("...")

    def test_empty_list(self):
        """Empty lists should return []."""
        result = _smart_truncate_value([])
        assert result == "[]"

    def test_small_list(self):
        """Small lists should show all items."""
        result = _smart_truncate_value([1, 2, 3])
        assert "1" in result
        assert "2" in result
        assert "3" in result

    def test_large_list_truncated(self):
        """Large lists should show count."""
        large_list = list(range(100))
        result = _smart_truncate_value(large_list, max_length=100)
        assert "100 items" in result

    def test_empty_dict(self):
        """Empty dicts should return {}."""
        result = _smart_truncate_value({})
        assert result == "{}"

    def test_small_dict(self):
        """Small dicts should show key-value pairs."""
        result = _smart_truncate_value({"key": "value"})
        assert "key" in result
        assert "value" in result

    def test_large_dict_shows_count(self):
        """Large dicts should show key count."""
        large_dict = {f"key{i}": f"value{i}" for i in range(10)}
        result = _smart_truncate_value(large_dict, max_length=50)
        assert "keys" in result

    def test_int_converted_to_string(self):
        """Integers should be converted to strings."""
        result = _smart_truncate_value(42)
        assert result == "42"

    def test_bool_converted_to_string(self):
        """Booleans should be converted to strings."""
        result = _smart_truncate_value(True)
        assert result == "True"

    def test_none_converted_to_string(self):
        """None should be converted to string."""
        result = _smart_truncate_value(None)
        assert result == "None"


class TestFormatToolInputForConsole:
    """Tests for _format_tool_input_for_console function."""

    def test_empty_input(self):
        """Empty input should return {}."""
        result = _format_tool_input_for_console({})
        assert result == "{}"

    def test_simple_input(self):
        """Simple input should be formatted nicely."""
        result = _format_tool_input_for_console({"path": "/test/file.py"})
        assert '"path"' in result
        assert "/test/file.py" in result
        assert result.startswith("{")
        assert result.endswith("}")

    def test_multiple_fields(self):
        """Multiple fields should each be on their own line."""
        input_data = {"action": "search", "query": "test", "limit": 10}
        result = _format_tool_input_for_console(input_data)
        assert '"action"' in result
        assert '"query"' in result
        assert '"limit"' in result
        assert result.count("\n") >= 3  # At least 3 lines for 3 fields

    def test_nested_dict_truncated(self):
        """Nested dicts should be truncated intelligently."""
        input_data = {"params": {"nested": "value", "another": "field"}}
        result = _format_tool_input_for_console(input_data)
        assert '"params"' in result
        # Should show truncated version of nested dict
        assert "nested" in result or "keys" in result


class TestFormatToolResponseForConsole:
    """Tests for _format_tool_response_for_console function."""

    def test_none_response(self):
        """None response should return 'None'."""
        result = _format_tool_response_for_console(None)
        assert result == "None"

    def test_small_dict_shows_full(self):
        """Small dicts (≤250 chars) should show full content."""
        small_dict = {"status": "success", "result": "Done"}
        result = _format_tool_response_for_console(small_dict)
        assert "dict with 2 key(s)" in result
        assert "success" in result
        assert "Done" in result

    def test_large_dict_shows_keys_list(self):
        """Large dicts should show key list and interesting fields."""
        large_dict = {
            "timestamp": "2024-10-17T12:00:00",
            "request_id": "abc123",
            "api_version": "v2",
            "metadata": {"key": "value" * 50},  # Make it large
            "result": "Success!",
        }
        result = _format_tool_response_for_console(large_dict)
        assert "dict with" in result
        assert "key(s)" in result
        # Should show result since it's in interesting_keys
        assert "result" in result.lower() or "Success" in result

    def test_dict_with_error_field(self):
        """Dicts with error field should show it."""
        error_dict = {
            "error": "Permission denied",
            "status": "failed",
            "other_field": "x" * 1000,  # Make it large enough
        }
        result = _format_tool_response_for_console(error_dict)
        assert "error" in result.lower()
        assert "Permission denied" in result

    def test_list_response(self):
        """List responses should show count and first item."""
        list_response = [{"id": 1}, {"id": 2}, {"id": 3}]
        result = _format_tool_response_for_console(list_response)
        assert "list with 3 item(s)" in result
        assert "First item" in result

    def test_empty_list_response(self):
        """Empty list should show count."""
        result = _format_tool_response_for_console([])
        assert "list with 0 item(s)" in result

    def test_short_string_response(self):
        """Short strings should be shown in full with quotes."""
        result = _format_tool_response_for_console("Short message")
        assert result == '"Short message"'

    def test_long_string_response(self):
        """Long strings should be truncated."""
        long_str = "x" * 500
        result = _format_tool_response_for_console(long_str)
        assert len(result) < len(long_str)
        assert result.endswith('..."')


class TestCreateEventData:
    """Tests for create_event_data function."""

    def test_tool_name_included(self):
        """Event data should always include tool_name."""
        result = create_event_data("test_tool")
        assert result["tool_name"] == "test_tool"

    def test_no_input(self):
        """Event data with no input should only have tool_name."""
        result = create_event_data("test_tool", None)
        assert result == {"tool_name": "test_tool"}

    def test_empty_input(self):
        """Event data with empty input should only have tool_name."""
        result = create_event_data("test_tool", {})
        assert result == {"tool_name": "test_tool"}

    def test_simple_input_creates_summary(self):
        """Simple input should create input_summary."""
        result = create_event_data("test_tool", {"action": "search"})
        assert "input_summary" in result
        assert "action=search" in result["input_summary"]

    def test_input_fields_flattened(self):
        """Input fields should be flattened with input. prefix."""
        result = create_event_data("test_tool", {"path": "/test", "mode": "read"})
        assert "input.path" in result
        assert result["input.path"] == "/test"
        assert "input.mode" in result
        assert result["input.mode"] == "read"

    def test_large_input_truncated(self):
        """Large input values should be truncated."""
        large_value = "x" * 3000
        result = create_event_data("test_tool", {"data": large_value})
        assert "input.data" in result
        assert len(result["input.data"]) < len(large_value)
        assert "truncated" in result["input.data"]

    def test_dict_and_list_in_summary(self):
        """Dicts and lists should show structure in summary."""
        result = create_event_data(
            "test_tool", {"config": {"a": 1, "b": 2}, "items": [1, 2, 3]}
        )
        assert "input_summary" in result
        assert "config" in result["input_summary"]
        assert "items" in result["input_summary"]


class TestAddResponseToEventData:
    """Tests for add_response_to_event_data function."""

    def test_none_response(self):
        """None response should set success status."""
        event_data = {}
        add_response_to_event_data(event_data, None)
        assert event_data["status"] == "success"
        assert event_data["response_summary"] == "None"

    def test_dict_success_response(self):
        """Dict response without error should be marked success."""
        event_data = {}
        add_response_to_event_data(event_data, {"result": "Done"})
        assert event_data["status"] == "success"
        assert "response_type" in event_data
        assert event_data["response_type"] == "dict"

    def test_dict_error_response(self):
        """Dict response with error field should be marked error."""
        event_data = {}
        add_response_to_event_data(event_data, {"error": "Failed", "result": None})
        assert event_data["status"] == "error"
        assert "Failed" in event_data["response_summary"]

    def test_dict_is_error_response(self):
        """Dict response with isError=True should be marked error."""
        event_data = {}
        add_response_to_event_data(event_data, {"isError": True, "message": "Failed"})
        assert event_data["status"] == "error"

    def test_response_fields_flattened(self):
        """Response fields should be flattened with response. prefix."""
        event_data = {}
        add_response_to_event_data(event_data, {"status": "ok", "value": 42})
        assert "response.status" in event_data
        assert event_data["response.status"] == "ok"
        assert "response.value" in event_data
        assert event_data["response.value"] == "42"

    def test_list_response(self):
        """List response should include count."""
        event_data = {}
        add_response_to_event_data(event_data, [1, 2, 3])
        assert event_data["status"] == "success"
        assert "response.count" in event_data
        assert event_data["response.count"] == 3

    def test_string_response(self):
        """String response should be included."""
        event_data = {}
        add_response_to_event_data(event_data, "Success message")
        assert event_data["status"] == "success"
        assert event_data["response"] == "Success message"

    def test_large_response_truncated(self):
        """Large response values should be truncated."""
        event_data = {}
        large_value = "x" * 3000
        add_response_to_event_data(event_data, {"data": large_value})
        assert "response.data" in event_data
        assert len(event_data["response.data"]) < len(large_value)
        assert "truncated" in event_data["response.data"]


class TestCreateToolTitle:
    """Tests for create_tool_title function."""

    def test_no_input_returns_tool_name(self):
        """With no input, should just return tool name."""
        result = create_tool_title("Bash")
        assert result == "Bash"

    def test_empty_input_returns_tool_name(self):
        """With empty input, should just return tool name."""
        result = create_tool_title("Bash", {})
        assert result == "Bash"

    def test_command_shown_in_quotes(self):
        """Command-like strings should be shown in quotes."""
        result = create_tool_title("Bash", {"command": "ls -l"})
        assert '"ls -l"' in result
        assert "Bash" in result

    def test_path_shown_in_quotes(self):
        """Paths should be shown in quotes."""
        result = create_tool_title("Read", {"path": "/Users/nick/code.py"})
        assert '"/Users/nick/code.py"' in result

    def test_key_value_params(self):
        """Simple key-value params should be shown."""
        result = create_tool_title("mcp__gmail", {"action": "search", "query": "inbox"})
        assert "action=search" in result
        assert "query=inbox" in result
        assert "mcp__gmail" in result

    def test_max_three_params(self):
        """Should show max 3 parameters."""
        result = create_tool_title(
            "test_tool", {"a": "1", "b": "2", "c": "3", "d": "4", "e": "5"}
        )
        # Count how many params shown
        param_count = sum(1 for x in ["a=", "b=", "c=", "d=", "e="] if x in result)
        assert param_count <= 3

    def test_long_string_truncated(self):
        """Long string values should be truncated."""
        long_value = "x" * 100
        result = create_tool_title("test_tool", {"data": long_value})
        assert len(result) < len(long_value) + 20
        assert "..." in result

    def test_dict_param_shows_count(self):
        """Dict parameters should show key count."""
        result = create_tool_title("test_tool", {"params": {"a": 1, "b": 2, "c": 3}})
        assert "{...3}" in result

    def test_list_param_shows_count(self):
        """List parameters should show item count."""
        result = create_tool_title("TodoWrite", {"todos": [1, 2, 3]})
        assert "[...3]" in result

    def test_max_length_enforced(self):
        """Title should not exceed max_length."""
        long_tool_name = "very_long_tool_name" * 5
        long_param = "x" * 100
        result = create_tool_title(long_tool_name, {"param": long_param}, max_length=50)
        assert len(result) <= 50

    def test_int_bool_none_params(self):
        """Int, bool, and None params should be shown."""
        result = create_tool_title(
            "test_tool", {"count": 42, "enabled": True, "value": None}
        )
        assert "count=42" in result
        assert "enabled=True" in result
        assert "value=None" in result


class TestCreateCompletionTitle:
    """Tests for create_completion_title function."""

    def test_none_response(self):
        """None response should show → None."""
        result = create_completion_title("test_tool", None)
        assert result == "test_tool → None"

    def test_dict_with_error(self):
        """Dict with error should show error message."""
        result = create_completion_title("Bash", {"error": "Permission denied"})
        assert "Error: Permission denied" in result
        assert "Bash" in result

    def test_dict_with_is_error(self):
        """Dict with isError=True should show Error."""
        result = create_completion_title("test_tool", {"isError": True})
        assert "Error" in result

    def test_dict_with_result(self):
        """Dict with result field should show it."""
        result = create_completion_title("test_tool", {"result": "Success!"})
        assert "result=Success!" in result

    def test_dict_with_content(self):
        """Dict with content field should show it."""
        result = create_completion_title("Read", {"content": "File contents"})
        assert "File contents" in result

    def test_dict_with_message(self):
        """Dict with message field should show it."""
        result = create_completion_title("test_tool", {"message": "Done"})
        assert "Done" in result

    def test_dict_with_no_interesting_fields(self):
        """Dict with no interesting fields should show field count."""
        result = create_completion_title(
            "test_tool", {"timestamp": "123", "id": "abc", "status": "ok"}
        )
        assert "3 fields" in result

    def test_list_response_singular(self):
        """List with 1 item should use singular form."""
        result = create_completion_title("test_tool", [{"id": 1}])
        assert "1 item" in result
        assert "items" not in result

    def test_list_response_plural(self):
        """List with multiple items should use plural form."""
        result = create_completion_title("gmail", [1, 2, 3, 4, 5])
        assert "5 items" in result

    def test_empty_list_response(self):
        """Empty list should show 0 items."""
        result = create_completion_title("test_tool", [])
        assert "0 items" in result

    def test_short_string_response(self):
        """Short string should be shown in full."""
        result = create_completion_title("test_tool", "Success")
        assert "Success" in result

    def test_long_string_response_truncated(self):
        """Long string should be truncated."""
        long_str = "x" * 100
        result = create_completion_title("test_tool", long_str)
        assert len(result) < len(long_str) + 20
        assert "..." in result

    def test_max_length_enforced(self):
        """Completion title should not exceed max_length."""
        long_response = "x" * 200
        result = create_completion_title("test_tool", long_response, max_length=50)
        assert len(result) <= 50

    def test_arrow_separator_used(self):
        """Should use → separator between tool name and summary."""
        result = create_completion_title("test_tool", "result")
        assert "→" in result

    def test_long_error_truncated(self):
        """Long error messages should be truncated."""
        long_error = "x" * 100
        result = create_completion_title("test_tool", {"error": long_error})
        assert len(result) < len(long_error) + 30
