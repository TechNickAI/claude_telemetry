"""MCP server configuration loader."""

import json
from pathlib import Path
from typing import Any

from loguru import logger


def load_mcp_config(config_path: Path | None = None) -> dict[str, Any] | None:
    """
    Load MCP server configuration from .mcp.json file.

    Converts from user format to Claude SDK format:
    - "transport" -> "type"
    - Preserves all other fields

    Args:
        config_path: Path to .mcp.json file (defaults to current directory)

    Returns:
        SDK-formatted MCP configuration dict or None if not found
    """
    if config_path is None:
        config_path = Path.cwd() / ".mcp.json"

    if not config_path.exists():
        logger.debug(f"No MCP config found at {config_path}")
        return None

    try:
        with config_path.open() as f:
            config = json.load(f)

        # Extract mcpServers section
        mcp_servers = config.get("mcpServers", {})

        if not mcp_servers:
            logger.warning("MCP config file exists but has no servers defined")
            return None

        # Convert to SDK format
        sdk_config = {}
        for name, server_config in mcp_servers.items():
            # Copy server config
            sdk_server = dict(server_config)

            # Convert transport -> type for SDK
            if "transport" in sdk_server:
                sdk_server["type"] = sdk_server.pop("transport")

            sdk_config[name] = sdk_server

    except json.JSONDecodeError:
        logger.exception("Invalid JSON in MCP config")
        return None
    except Exception:
        logger.exception("Failed to load MCP config")
        return None
    else:
        logger.info(f"Loaded {len(sdk_config)} MCP server(s) from {config_path}")
        return sdk_config


def validate_mcp_server(server_config: dict[str, Any]) -> bool:
    """
    Validate an MCP server configuration.

    Args:
        server_config: Server configuration dict

    Returns:
        True if valid, False otherwise
    """
    # Check required fields based on type
    server_type = server_config.get("type")

    if server_type == "http":
        # HTTP servers need URL
        if not server_config.get("url"):
            logger.warning("HTTP MCP server missing required 'url' field")
            return False

    elif server_type == "stdio":
        # Stdio servers need command
        if not server_config.get("command"):
            logger.warning("Stdio MCP server missing required 'command' field")
            return False

    else:
        logger.warning(f"Unknown MCP server type: {server_type}")
        return False

    return True
