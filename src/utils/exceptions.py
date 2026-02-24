"""
Custom exception classes for the Automaton Auditor system.
Provides granular error handling across all components.
"""


class AutomatonAuditorException(Exception):
    """Base exception for all Automaton Auditor errors."""

    pass


class ConfigurationError(AutomatonAuditorException):
    """Raised when configuration is invalid or missing."""

    pass


class SecurityViolationError(AutomatonAuditorException):
    """Raised when a security check fails."""

    pass


class PathTraversalError(SecurityViolationError):
    """Raised when a path traversal attempt is detected."""

    pass


class CommandInjectionError(SecurityViolationError):
    """Raised when command injection is detected."""

    pass


class ResourceLimitError(AutomatonAuditorException):
    """Raised when resource limits are exceeded."""

    pass


class RepositoryError(AutomatonAuditorException):
    """Base class for repository-related errors."""

    pass


class CloneError(RepositoryError):
    """Raised when git clone operation fails."""

    pass


class RepositorySizeError(ResourceLimitError):
    """Raised when repository exceeds size limits."""

    pass


class ParsingError(AutomatonAuditorException):
    """Base class for parsing-related errors."""

    pass


class ASTParsingError(ParsingError):
    """Raised when AST parsing fails."""

    pass


class PDFParsingError(ParsingError):
    """Raised when PDF parsing fails."""

    pass


class ValidationError(AutomatonAuditorException):
    """Raised when data validation fails."""

    pass


class EvidenceValidationError(ValidationError):
    """Raised when evidence object validation fails."""

    pass


class JudicialOpinionValidationError(ValidationError):
    """Raised when judicial opinion validation fails."""

    pass


class GraphExecutionError(AutomatonAuditorException):
    """Raised when LangGraph execution fails."""

    pass


class NodeExecutionError(GraphExecutionError):
    """Raised when a specific node fails."""

    def __init__(self, node_name: str, original_error: Exception):
        self.node_name = node_name
        self.original_error = original_error
        super().__init__(f"Node '{node_name}' failed: {str(original_error)}")


class TimeoutError(AutomatonAuditorException):
    """Raised when an operation times out."""

    pass


class LLMError(AutomatonAuditorException):
    """Raised when LLM invocation fails."""

    pass


class HallucinationDetectedError(AutomatonAuditorException):
    """Raised when LLM output appears to be hallucinated."""

    pass
