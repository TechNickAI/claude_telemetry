# Contributing to claude_telemetry

Thank you for your interest in contributing! 🎉 We appreciate your help in making this
project better.

## Code of Conduct

Be kind, respectful, and constructive. We're all here to build something useful
together! 💜

## Getting Started

### Development Setup

1. **Clone the repository**

   ```bash
   git clone https://github.com/TechNickAI/claude_telemetry.git
   cd claude_telemetry
   ```

2. **Create a virtual environment**

   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install development dependencies**

   ```bash
   pip install -r requirements/requirements-dev.txt
   pip install -e .
   ```

4. **Install pre-commit hooks**

   ```bash
   pre-commit install
   ```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=claude_telemetry --cov-report=term-missing

# Run specific test file
pytest tests/test_telemetry.py

# Run with verbose output
pytest -v
```

### Code Quality

We use several tools to maintain code quality:

- **Ruff** for linting and formatting
- **pytest** for testing
- **pre-commit** for automated checks

```bash
# Run linter
ruff check .

# Run formatter
ruff format .

# Run pre-commit checks manually
pre-commit run --all-files
```

## Making Changes

### Workflow

1. **Create a branch**

   ```bash
   git checkout -b feat/your-feature-name
   # or
   git checkout -b fix/your-bug-fix
   ```

2. **Make your changes**
   - Write code
   - Add tests
   - Update documentation

3. **Commit your changes**

   We follow conventional commit format:

   ```bash
   git commit -m "feat: add new telemetry feature"
   git commit -m "fix: resolve span closure issue"
   git commit -m "docs: update installation instructions"
   ```

   Commit types:
   - `feat:` New feature
   - `fix:` Bug fix
   - `docs:` Documentation changes
   - `test:` Test changes
   - `refactor:` Code refactoring
   - `chore:` Build/tooling changes

4. **Push and create PR**

   ```bash
   git push origin feat/your-feature-name
   ```

   Then create a Pull Request on GitHub.

### Pull Request Guidelines

- **Title**: Use conventional commit format
- **Description**: Explain what and why, not just how
- **Tests**: Add tests for new features or bug fixes
- **Documentation**: Update docs if needed
- **Pre-commit**: Ensure all checks pass

## Development Tips

### Adding New Features

1. **Start with tests** - Write tests first (TDD approach)
2. **Keep it simple** - Follow existing patterns
3. **Document it** - Update docstrings and README
4. **Consider backwards compatibility** - Don't break existing APIs

### Testing Telemetry

When developing telemetry features:

```python
# Use pytest fixtures for mocking spans
def test_my_feature(mocker):
    mock_span = mocker.MagicMock()
    # ... test your feature
```

See existing tests in `tests/` for examples.

### Adding Examples

If you add a feature, consider adding an example:

1. Create a new file in `examples/`
2. Follow the pattern of existing examples
3. Update `examples/README.md`

## Project Structure

```
claude_telemetry/
├── claude_telemetry/       # Main package code
│   ├── __init__.py         # Package exports
│   ├── cli.py              # CLI entry point
│   ├── hooks.py            # Telemetry hooks
│   ├── logfire_adapter.py  # Logfire integration
│   ├── runner.py           # Agent runner
│   ├── sync.py             # Sync wrappers
│   └── telemetry.py        # OTEL configuration
├── tests/                  # Test suite
├── examples/               # Usage examples
├── requirements/           # Dependency files
└── .github/workflows/      # CI/CD pipelines
```

## Questions?

- **Issues**: Open an issue on GitHub
- **Discussions**: Start a discussion for questions or ideas

## License

By contributing, you agree that your contributions will be licensed under the MIT
license.

---

Thank you for contributing! 💜 Your work helps the entire community! 🚀
