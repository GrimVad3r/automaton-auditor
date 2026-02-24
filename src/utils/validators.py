"""
Input validation and security checking utilities.
Implements defense-in-depth security controls.
"""

import re
from pathlib import Path
from typing import List, Optional
from urllib.parse import urlparse

from .exceptions import (
    CommandInjectionError,
    PathTraversalError,
    ResourceLimitError,
    SecurityViolationError,
    ValidationError,
)
from .logger import get_logger

logger = get_logger()


class SecurityValidator:
    """Security validation and sanitization utilities."""

    # Allowed git hosting domains
    ALLOWED_GIT_DOMAINS = [
        "github.com",
        "gitlab.com",
        "bitbucket.org",
    ]

    # Dangerous shell characters
    # Note: Parentheses are allowed so safe inline scripts (e.g. python -c "print('x')")
    # can run in tests and tooling contexts without shell execution.
    SHELL_METACHARACTERS = [";", "&", "|", "`", "$", "<", ">", "\n", "\r"]

    # Maximum file sizes
    MAX_REPO_SIZE_MB = 500
    MAX_FILE_SIZE_MB = 10

    @classmethod
    def validate_git_url(cls, url: str, allowed_domains: Optional[List[str]] = None) -> str:
        """
        Validate and sanitize a git repository URL.

        Args:
            url: The repository URL to validate
            allowed_domains: Optional list of allowed domains (overrides default)

        Returns:
            The validated URL

        Raises:
            ValidationError: If URL is invalid
            SecurityViolationError: If URL is from disallowed domain
        """
        if not url or not isinstance(url, str):
            raise ValidationError("URL must be a non-empty string")

        # Parse URL
        try:
            parsed = urlparse(url)
        except Exception as e:
            raise ValidationError(f"Invalid URL format: {e}")

        # Validate scheme
        if parsed.scheme not in ["https", "http", "git"]:
            raise SecurityViolationError(f"Unsupported URL scheme: {parsed.scheme}")

        # Validate domain
        domains = allowed_domains or cls.ALLOWED_GIT_DOMAINS
        if parsed.netloc not in domains:
            raise SecurityViolationError(
                f"Domain '{parsed.netloc}' not in allowed list: {domains}"
            )

        # Check for shell metacharacters (command injection attempt)
        for char in cls.SHELL_METACHARACTERS:
            if char in url:
                logger.log_security_violation(
                    "Command Injection Attempt",
                    f"Shell metacharacter '{char}' found in URL: {url}",
                )
                raise CommandInjectionError(f"Suspicious character '{char}' found in URL")

        logger.debug(f"Validated git URL: {parsed.netloc}{parsed.path}")
        return url

    @classmethod
    def validate_file_path(cls, path: str, base_dir: Path) -> Path:
        """
        Validate a file path to prevent path traversal attacks.

        Args:
            path: The file path to validate
            base_dir: The base directory that the path must be within

        Returns:
            The resolved, validated Path object

        Raises:
            PathTraversalError: If path attempts to escape base_dir
        """
        try:
            # Resolve to absolute path
            base_resolved = base_dir.resolve()
            raw_target = Path(path)
            target_resolved = (
                raw_target.resolve() if raw_target.is_absolute() else (base_dir / raw_target).resolve()
            )

            # Check if target is within base
            try:
                target_resolved.relative_to(base_resolved)
            except ValueError:
                logger.log_security_violation(
                    "Path Traversal Attempt",
                    f"Path '{path}' attempts to escape base directory '{base_dir}'",
                )
                raise PathTraversalError(
                    f"Path '{path}' is outside allowed directory '{base_dir}'"
                )

            return target_resolved

        except Exception as e:
            if isinstance(e, PathTraversalError):
                raise
            raise ValidationError(f"Invalid file path: {e}")

    @classmethod
    def validate_file_size(cls, file_path: Path, max_size_mb: Optional[int] = None) -> int:
        """
        Validate file size against limits.

        Args:
            file_path: Path to the file
            max_size_mb: Maximum allowed size in MB (default: MAX_FILE_SIZE_MB)

        Returns:
            File size in bytes

        Raises:
            ResourceLimitError: If file exceeds size limit
        """
        max_bytes = (max_size_mb or cls.MAX_FILE_SIZE_MB) * 1024 * 1024

        if not file_path.exists():
            raise ValidationError(f"File not found: {file_path}")

        size = file_path.stat().st_size

        if size > max_bytes:
            raise ResourceLimitError(
                f"File size ({size / 1024 / 1024:.2f}MB) exceeds limit "
                f"({max_size_mb or cls.MAX_FILE_SIZE_MB}MB)"
            )

        return size

    @classmethod
    def validate_directory_size(cls, dir_path: Path, max_size_mb: Optional[int] = None) -> int:
        """
        Validate total directory size against limits.

        Args:
            dir_path: Path to the directory
            max_size_mb: Maximum allowed size in MB (default: MAX_REPO_SIZE_MB)

        Returns:
            Total size in bytes

        Raises:
            ResourceLimitError: If directory exceeds size limit
        """
        max_bytes = (max_size_mb or cls.MAX_REPO_SIZE_MB) * 1024 * 1024

        total_size = sum(f.stat().st_size for f in dir_path.rglob("*") if f.is_file())

        if total_size > max_bytes:
            raise ResourceLimitError(
                f"Directory size ({total_size / 1024 / 1024:.2f}MB) exceeds limit "
                f"({max_size_mb or cls.MAX_REPO_SIZE_MB}MB)"
            )

        logger.debug(f"Directory size validated: {total_size / 1024 / 1024:.2f}MB")
        return total_size

    @classmethod
    def sanitize_command_arg(cls, arg: str) -> str:
        """
        Sanitize a command-line argument.

        Args:
            arg: The argument to sanitize

        Returns:
            Sanitized argument

        Raises:
            CommandInjectionError: If dangerous characters detected
        """
        for char in cls.SHELL_METACHARACTERS:
            if char in arg:
                raise CommandInjectionError(f"Dangerous character '{char}' in argument: {arg}")

        return arg


class DataValidator:
    """Data validation utilities for business logic."""

    @staticmethod
    def validate_score(score: int, min_score: int = 1, max_score: int = 5) -> int:
        """
        Validate a score is within valid range.

        Args:
            score: The score to validate
            min_score: Minimum valid score
            max_score: Maximum valid score

        Returns:
            The validated score

        Raises:
            ValidationError: If score is out of range
        """
        if not isinstance(score, int):
            raise ValidationError(f"Score must be an integer, got {type(score)}")

        if not min_score <= score <= max_score:
            raise ValidationError(f"Score {score} not in valid range [{min_score}, {max_score}]")

        return score

    @staticmethod
    def validate_confidence(confidence: float) -> float:
        """
        Validate a confidence value is between 0 and 1.

        Args:
            confidence: The confidence value to validate

        Returns:
            The validated confidence

        Raises:
            ValidationError: If confidence is out of range
        """
        if not isinstance(confidence, (int, float)):
            raise ValidationError(f"Confidence must be numeric, got {type(confidence)}")

        if not 0.0 <= confidence <= 1.0:
            raise ValidationError(f"Confidence {confidence} not in valid range [0.0, 1.0]")

        return float(confidence)

    @staticmethod
    def validate_criterion_id(criterion_id: str, valid_ids: List[str]) -> str:
        """
        Validate criterion ID against known rubric.

        Args:
            criterion_id: The criterion ID to validate
            valid_ids: List of valid criterion IDs

        Returns:
            The validated criterion ID

        Raises:
            ValidationError: If criterion ID is invalid
        """
        if criterion_id not in valid_ids:
            raise ValidationError(f"Unknown criterion ID: {criterion_id}. Valid IDs: {valid_ids}")

        return criterion_id
