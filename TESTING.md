# Test Suite Documentation

## Overview

The Automaton Auditor test suite provides comprehensive coverage of all system components with over **150 test cases** organized into modular test files.

## Test Structure

```
tests/
├── conftest.py                    # Shared fixtures and configuration
├── test_utils_validators.py      # Security validator tests (25 tests)
├── test_utils_logger.py           # Logging system tests (10 tests)
├── test_utils_exceptions.py       # Exception hierarchy tests (15 tests)
├── test_utils_formatters.py       # Report formatting tests (12 tests)
├── test_core_state.py             # State model tests (20 tests)
├── test_core_config.py            # Configuration tests (18 tests)
├── test_tools_security.py         # Sandboxed execution tests (15 tests)
├── test_tools_ast.py              # AST analysis tests (12 tests)
├── test_tools_pdf.py              # PDF parsing tests (10 tests)
├── test_agents.py                 # Agent implementation tests (25 tests)
└── test_integration.py            # Integration tests (15 tests)
```

## Running Tests

### Quick Start

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test file
pytest tests/test_utils_validators.py

# Run tests matching pattern
pytest -k "security"
```

### Using Test Runner Script

```bash
# Make executable
chmod +x run_tests.sh

# Run different test suites
./run_tests.sh all              # All tests
./run_tests.sh unit             # Unit tests only
./run_tests.sh integration      # Integration tests
./run_tests.sh security         # Security tests
./run_tests.sh coverage         # With coverage report
./run_tests.sh parallel         # Parallel execution
./run_tests.sh watch            # Watch mode
```

## Test Categories

### 1. Unit Tests (Fast, Isolated)
**Marker:** `@pytest.mark.unit` (implicit for unmarked tests)

Tests individual functions and classes in isolation.

**Examples:**
- State model validation
- Security validators
- Configuration parsing
- Exception handling

**Run:** `./run_tests.sh unit`

### 2. Integration Tests
**Marker:** `@pytest.mark.integration`

Tests component interactions and full workflows.

**Examples:**
- Full graph execution
- Detective → Judge → Justice flow
- State reduction across parallel nodes
- Report generation pipeline

**Run:** `./run_tests.sh integration`

### 3. Security Tests
**Marker:** `@pytest.mark.security`

Tests security controls and vulnerability prevention.

**Examples:**
- Path traversal detection
- Command injection prevention
- URL validation
- API key redaction

**Run:** `./run_tests.sh security`

### 4. Slow Tests
**Marker:** `@pytest.mark.slow`

Tests that involve network, disk I/O, or API calls.

**Examples:**
- Git repository cloning
- LLM API calls
- Large file processing

**Skip:** `pytest -m "not slow"`

### 5. API-Dependent Tests
**Marker:** `@pytest.mark.requires_api`

Tests requiring valid API keys.

**Examples:**
- LLM invocations
- Judge opinion generation
- Structured output validation

**Skip:** `pytest -m "not requires_api"`

## Test Fixtures

### Shared Fixtures (conftest.py)

```python
# Environment setup
test_env              # Sets up test environment variables

# Temporary resources
temp_dir              # Temporary directory for tests
mock_git_repo         # Mock repository structure
mock_pdf_file         # Mock PDF file

# Sample data
sample_evidence       # Sample Evidence object
sample_opinion        # Sample JudicialOpinion
sample_rubric         # Sample rubric configuration
sample_agent_state    # Sample AgentState

# Security testing
malicious_urls        # URLs for injection testing
path_traversal_attempts  # Path traversal patterns
```

### Using Fixtures

```python
def test_example(temp_dir, sample_evidence):
    """Test using fixtures."""
    # temp_dir and sample_evidence are automatically provided
    file_path = temp_dir / "test.txt"
    assert sample_evidence.confidence == 0.95
```

## Coverage Requirements

- **Minimum Coverage:** 60%
- **Current Coverage:** ~75%
- **Target Coverage:** 85%

### Coverage by Module

| Module | Coverage | Status |
|--------|----------|--------|
| utils/validators.py | 95% | ✅ Excellent |
| utils/logger.py | 85% | ✅ Good |
| core/state.py | 90% | ✅ Excellent |
| core/config.py | 80% | ✅ Good |
| tools/security.py | 85% | ✅ Good |
| tools/ast_tools.py | 75% | ⚠️ Acceptable |
| tools/pdf_tools.py | 70% | ⚠️ Acceptable |
| agents/* | 65% | ⚠️ Acceptable |

### Viewing Coverage

```bash
# Generate HTML coverage report
pytest --cov=src --cov-report=html

# Open report
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
```

## Test Patterns

### 1. Testing Security Validators

```python
@pytest.mark.security
def test_command_injection_prevention():
    """Test command injection is prevented."""
    with pytest.raises(CommandInjectionError):
        SecurityValidator.sanitize_command_arg("test; rm -rf /")
```

### 2. Testing State Models

```python
def test_evidence_validation():
    """Test Pydantic model validation."""
    # Valid evidence
    evidence = Evidence(
        found=True,
        location="test.py",
        confidence=0.95,
        detective_name="TestDetective"
    )
    assert evidence.confidence == 0.95
    
    # Invalid confidence (out of range)
    with pytest.raises(ValidationError):
        Evidence(
            found=True,
            location="test.py",
            confidence=1.5,  # Invalid
            detective_name="Test"
        )
```

### 3. Testing with Mocks

```python
@patch('src.agents.detectives.repo_investigator.GitAnalyzer')
def test_investigate_with_mock(mock_git):
    """Test investigation with mocked dependencies."""
    # Setup mock
    mock_git.return_value.analyze_repository.return_value = {
        "test": Evidence(...)
    }
    
    # Test
    detective = RepoInvestigator()
    result = detective.investigate(state)
    
    # Verify
    assert "evidences" in result
```

### 4. Testing Async Code

```python
@pytest.mark.asyncio
async def test_async_function():
    """Test asynchronous functionality."""
    result = await some_async_function()
    assert result is not None
```

## Continuous Integration

### GitHub Actions Workflow

The project includes a CI/CD workflow that:

1. **Runs on:** Push to main/develop, Pull Requests
2. **Tests across:**
   - OS: Ubuntu, macOS, Windows
   - Python: 3.11, 3.12
3. **Checks:**
   - Linting (ruff, black)
   - Type checking (mypy)
   - Unit tests with coverage
   - Security scanning (bandit, pip-audit)

### Workflow File

`.github/workflows/unittests.yml`

## Common Testing Scenarios

### Testing Error Handling

```python
def test_error_propagation():
    """Test errors propagate correctly."""
    with pytest.raises(NodeExecutionError) as exc_info:
        failing_node(state)
    
    assert exc_info.value.node_name == "FailingNode"
    assert isinstance(exc_info.value.original_error, ValueError)
```

### Testing File Operations

```python
def test_file_creation(temp_dir):
    """Test file creation in sandboxed environment."""
    test_file = temp_dir / "test.txt"
    test_file.write_text("content")
    
    assert test_file.exists()
    assert test_file.read_text() == "content"
```

### Testing Security Controls

```python
@pytest.mark.security
def test_path_validation(temp_dir, path_traversal_attempts):
    """Test path traversal prevention."""
    for attempt in path_traversal_attempts:
        with pytest.raises(PathTraversalError):
            SecurityValidator.validate_file_path(attempt, temp_dir)
```

## Debugging Tests

### Verbose Output

```bash
pytest -vv  # Extra verbose
pytest -s   # Show print statements
pytest --tb=long  # Detailed tracebacks
```

### Running Single Test

```bash
pytest tests/test_core_state.py::TestEvidence::test_valid_evidence -v
```

### Using pdb Debugger

```python
def test_with_debugger():
    """Test with breakpoint."""
    import pdb; pdb.set_trace()
    # Execution pauses here
    assert True
```

### Pytest Debugging Options

```bash
pytest --pdb  # Drop into debugger on failure
pytest -x     # Stop on first failure
pytest --lf   # Run last failed tests
pytest --ff   # Run failed tests first
```

## Performance Testing

### Test Execution Time

```bash
# Show slowest tests
pytest --durations=10

# Profile test execution
pytest --profile
```

### Parallel Execution

```bash
# Install pytest-xdist
pip install pytest-xdist

# Run tests in parallel
pytest -n auto  # Auto-detect CPU count
pytest -n 4     # Use 4 workers
```

## Best Practices

### ✅ Do's

1. **Use descriptive test names**
   ```python
   def test_validate_score_rejects_out_of_range_values()
   ```

2. **One assertion per test (when possible)**
   ```python
   def test_evidence_found_flag():
       evidence = Evidence(...)
       assert evidence.found is True
   ```

3. **Use fixtures for setup**
   ```python
   @pytest.fixture
   def configured_analyzer():
       return ASTAnalyzer(Path.cwd())
   ```

4. **Test both success and failure cases**
   ```python
   def test_validator_accepts_valid_url():
       # Test success
       
   def test_validator_rejects_invalid_url():
       # Test failure
   ```

5. **Use markers for categorization**
   ```python
   @pytest.mark.slow
   @pytest.mark.security
   def test_git_clone_security():
       ...
   ```

### ❌ Don'ts

1. **Don't use hardcoded paths**
   ```python
   # Bad
   path = "/home/user/test.txt"
   
   # Good
   path = temp_dir / "test.txt"
   ```

2. **Don't test implementation details**
   ```python
   # Bad - tests internal variable
   assert obj._internal_state == "value"
   
   # Good - tests behavior
   assert obj.get_state() == "value"
   ```

3. **Don't share state between tests**
   ```python
   # Bad - shared state
   shared_list = []
   
   # Good - use fixtures
   @pytest.fixture
   def fresh_list():
       return []
   ```

## Troubleshooting

### Tests Failing Locally

1. **Clear pytest cache**
   ```bash
   pytest --cache-clear
   ```

2. **Check environment variables**
   ```bash
   echo $OPENAI_API_KEY
   ```

3. **Reinstall dependencies**
   ```bash
   uv sync --frozen --extra dev
   ```

### Import Errors

```bash
# Install package in development mode
uv sync --frozen --extra dev

# Verify installation
uv run python -c "import src; print('OK')"
```

### Coverage Not Working

```bash
# Reinstall pytest-cov
pip install --force-reinstall pytest-cov

# Run with coverage
pytest --cov=src
```

## Adding New Tests

### 1. Create Test File

```python
# tests/test_new_module.py
"""
Tests for new module.
"""
import pytest
from src.new_module import NewClass

class TestNewClass:
    """Tests for NewClass."""
    
    def test_initialization(self):
        """Test class initialization."""
        obj = NewClass()
        assert obj is not None
```

### 2. Add Fixtures if Needed

```python
# tests/conftest.py
@pytest.fixture
def new_class_instance():
    """Create NewClass instance."""
    return NewClass()
```

### 3. Run New Tests

```bash
pytest tests/test_new_module.py -v
```

## Test Metrics

### Current Statistics

- **Total Tests:** 150+
- **Test Files:** 12
- **Fixtures:** 15+
- **Coverage:** ~75%
- **Execution Time:** ~2 minutes (all tests)
- **Fast Tests Only:** ~15 seconds

### Test Distribution

- Unit Tests: 70%
- Integration Tests: 20%
- Security Tests: 10%

## Resources

- [Pytest Documentation](https://docs.pytest.org/)
- [pytest-cov Documentation](https://pytest-cov.readthedocs.io/)
- [Testing Best Practices](https://docs.pytest.org/en/latest/goodpractices.html)

## Support

For test-related issues:
1. Check this documentation
2. Review test examples in `tests/`
3. Check CI logs in GitHub Actions
4. Open an issue with test failure details
