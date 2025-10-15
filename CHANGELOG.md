# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and
this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

### Changed

### Fixed

## [0.2.0] - 2025-10-15

### Changed

- **Major CLI Refactor**: Simplified argument parsing using Typer's variadic arguments
  - Reduced parsing logic from ~200+ lines to ~50 lines
  - Removed complex custom prompt extraction that was prone to bugs
  - Simple heuristic: last non-option argument is the prompt
  - Proper handling of `--flag=value`, `--flag value`, and `--flag` (boolean) formats
- Improved test suite with proper mocking following pytest standards
  - Added 20 new CLI parsing tests
  - Mock external dependencies instead of calling Claude CLI during tests
  - Faster test execution (0.30s for full suite)

### Fixed

- Fixed argument parsing bugs where flags were incorrectly treated as prompts
- Fixed test for KeyboardInterrupt handling to properly expect `typer.Exit`

## [0.1.2] - 2025-01-XX

### Added

- Initial public release! 🎉
- OpenTelemetry instrumentation for Claude agents
- Comprehensive telemetry capture (prompts, tool calls, tokens, costs)
- Logfire integration with LLM-specific UI features
- Support for any OTEL-compatible backend
- CLI tool (`claudia`) for quick agent execution
- Interactive and non-interactive agent modes
- MCP server support (HTTP and stdio)
- Comprehensive test suite
- Pre-commit hooks for code quality
- CI/CD pipeline with GitHub Actions

### Features

- 🤖 Captures every prompt, tool call, token count, and cost as structured OTEL spans
- 📊 Works with Logfire, Datadog, Honeycomb, Grafana, and any OTEL collector
- 🔧 Hook-based telemetry (no monkey-patching required)
- 💡 Enhanced Logfire features with LLM-specific UI tagging
- 🎨 Beautiful console output with emoji indicators
- ⚡ Async-first API with sync convenience wrappers
- 🔌 Extensible and maintainable architecture

## Release History

<!-- Versions will be added here as they are released -->

---

**Note**: This project uses [setuptools-scm](https://github.com/pypa/setuptools-scm) for
automatic version management from git tags.
