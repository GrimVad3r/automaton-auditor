"""
Tests for custom exception hierarchy.
"""

import pytest

from src.utils.exceptions import (
    AutomatonAuditorException,
    ConfigurationError,
    SecurityViolationError,
    PathTraversalError,
    CommandInjectionError,
    ResourceLimitError,
    RepositoryError,
    CloneError,
    RepositorySizeError,
    ParsingError,
    ASTParsingError,
    PDFParsingError,
    ValidationError,
    EvidenceValidationError,
    JudicialOpinionValidationError,
    GraphExecutionError,
    NodeExecutionError,
    TimeoutError,
    LLMError,
    HallucinationDetectedError,
)


class TestExceptionHierarchy:
    """Tests for exception inheritance."""

    def test_base_exception(self):
        """Test base exception."""
        exc = AutomatonAuditorException("Test error")
        assert str(exc) == "Test error"
        assert isinstance(exc, Exception)

    def test_configuration_error(self):
        """Test configuration error inheritance."""
        exc = ConfigurationError("Config error")
        assert isinstance(exc, AutomatonAuditorException)
        assert isinstance(exc, Exception)

    def test_security_error_hierarchy(self):
        """Test security error inheritance."""
        exc = SecurityViolationError("Security error")
        assert isinstance(exc, AutomatonAuditorException)

        # Specific security errors
        path_exc = PathTraversalError("Path error")
        assert isinstance(path_exc, SecurityViolationError)

        cmd_exc = CommandInjectionError("Command error")
        assert isinstance(cmd_exc, SecurityViolationError)

    def test_resource_error_hierarchy(self):
        """Test resource error inheritance."""
        exc = ResourceLimitError("Resource error")
        assert isinstance(exc, AutomatonAuditorException)

        # Specific resource errors
        size_exc = RepositorySizeError("Size error")
        assert isinstance(size_exc, ResourceLimitError)

    def test_repository_error_hierarchy(self):
        """Test repository error inheritance."""
        exc = RepositoryError("Repo error")
        assert isinstance(exc, AutomatonAuditorException)

        clone_exc = CloneError("Clone error")
        assert isinstance(clone_exc, RepositoryError)

    def test_parsing_error_hierarchy(self):
        """Test parsing error inheritance."""
        exc = ParsingError("Parse error")
        assert isinstance(exc, AutomatonAuditorException)

        ast_exc = ASTParsingError("AST error")
        assert isinstance(ast_exc, ParsingError)

        pdf_exc = PDFParsingError("PDF error")
        assert isinstance(pdf_exc, ParsingError)

    def test_validation_error_hierarchy(self):
        """Test validation error inheritance."""
        exc = ValidationError("Validation error")
        assert isinstance(exc, AutomatonAuditorException)

        evidence_exc = EvidenceValidationError("Evidence error")
        assert isinstance(evidence_exc, ValidationError)

        opinion_exc = JudicialOpinionValidationError("Opinion error")
        assert isinstance(opinion_exc, ValidationError)

    def test_graph_error_hierarchy(self):
        """Test graph execution error inheritance."""
        exc = GraphExecutionError("Graph error")
        assert isinstance(exc, AutomatonAuditorException)

        node_exc = NodeExecutionError("TestNode", ValueError("Test"))
        assert isinstance(node_exc, GraphExecutionError)
        assert "TestNode" in str(node_exc)


class TestNodeExecutionError:
    """Tests for NodeExecutionError with context."""

    def test_node_error_with_context(self):
        """Test node error includes context."""
        original = ValueError("Original error")
        exc = NodeExecutionError("TestNode", original)

        assert exc.node_name == "TestNode"
        assert exc.original_error is original
        assert "TestNode" in str(exc)
        assert "Original error" in str(exc)

    def test_node_error_attributes(self):
        """Test node error attributes are accessible."""
        exc = NodeExecutionError("DetectiveNode", RuntimeError("Failed"))

        assert exc.node_name == "DetectiveNode"
        assert isinstance(exc.original_error, RuntimeError)


class TestExceptionRaising:
    """Tests for raising and catching exceptions."""

    def test_catch_specific_exception(self):
        """Test catching specific exception types."""
        with pytest.raises(PathTraversalError):
            raise PathTraversalError("Path error")

    def test_catch_base_exception(self):
        """Test catching base exception."""
        with pytest.raises(AutomatonAuditorException):
            raise PathTraversalError("Specific error")

    def test_multiple_exception_types(self):
        """Test catching multiple exception types."""
        with pytest.raises((PathTraversalError, CommandInjectionError)):
            raise CommandInjectionError("Command error")

    def test_exception_with_formatting(self):
        """Test exception message formatting."""
        exc = ValidationError(f"Score {6} not in valid range [1, 5]")
        assert "Score 6" in str(exc)
        assert "[1, 5]" in str(exc)


class TestExceptionInContext:
    """Tests for exceptions in typical usage contexts."""

    def test_security_exception_in_validator(self):
        """Test security exceptions in validation context."""
        from src.utils.validators import SecurityValidator

        with pytest.raises(SecurityViolationError):
            SecurityValidator.validate_git_url("https://evil.com/repo")

    def test_validation_exception_in_validator(self):
        """Test validation exceptions in validator context."""
        from src.utils.validators import DataValidator

        with pytest.raises(ValidationError):
            DataValidator.validate_score(10)

    def test_node_exception_propagation(self):
        """Test exception propagation from nodes."""
        def failing_node():
            raise ValueError("Node failed")

        with pytest.raises(ValueError):
            failing_node()
