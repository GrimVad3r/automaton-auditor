"""
Security utilities for safe tool execution.
Provides sandboxed environments for potentially dangerous operations.
"""

import subprocess
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Generator, List, Optional, Tuple

from ..core.config import get_config
from ..utils.exceptions import CommandInjectionError, ResourceLimitError, TimeoutError
from ..utils.logger import get_logger
from ..utils.validators import SecurityValidator

logger = get_logger()


class SandboxedExecutor:
    """
    Execute commands in isolated, temporary environments.
    Implements defense-in-depth security controls.
    """

    @staticmethod
    @contextmanager
    def temporary_directory() -> Generator[Path, None, None]:
        """
        Create a temporary directory that is automatically cleaned up.

        Yields:
            Path to temporary directory
        """
        with tempfile.TemporaryDirectory(prefix="auditor_") as tmpdir:
            path = Path(tmpdir)
            logger.debug(f"Created temporary directory: {path}")
            try:
                yield path
            finally:
                logger.debug(f"Cleaning up temporary directory: {path}")

    @staticmethod
    def run_command(
        command: List[str],
        cwd: Optional[Path] = None,
        timeout: Optional[int] = None,
        capture_output: bool = True,
    ) -> Tuple[int, str, str]:
        """
        Execute a command with security controls.

        Args:
            command: Command and arguments as list (NOT shell string)
            cwd: Working directory
            timeout: Timeout in seconds
            capture_output: Whether to capture stdout/stderr

        Returns:
            Tuple of (return_code, stdout, stderr)

        Raises:
            CommandInjectionError: If command contains suspicious characters
            TimeoutError: If command exceeds timeout
        """
        config = get_config()
        timeout = timeout or config.git_clone_timeout

        # Validate command arguments
        for arg in command:
            SecurityValidator.sanitize_command_arg(str(arg))

        logger.debug(f"Executing command: {' '.join(command)}")

        try:
            result = subprocess.run(
                command,
                cwd=cwd,
                timeout=timeout,
                capture_output=capture_output,
                text=True,
                check=False,  # Don't raise on non-zero exit
                shell=False,  # CRITICAL: Never use shell=True
            )

            logger.debug(
                f"Command completed with return code {result.returncode} "
                f"in {timeout}s timeout window"
            )

            return result.returncode, result.stdout, result.stderr

        except subprocess.TimeoutExpired as e:
            logger.error(f"Command timed out after {timeout}s: {command}")
            raise TimeoutError(f"Command exceeded timeout of {timeout}s")

        except Exception as e:
            logger.error(f"Command execution failed: {e}", exc_info=True)
            raise

    @staticmethod
    def run_git_command(
        git_args: List[str],
        cwd: Optional[Path] = None,
        timeout: Optional[int] = None,
    ) -> Tuple[int, str, str]:
        """
        Execute a git command with additional safety checks.

        Args:
            git_args: Git command arguments (without 'git' prefix)
            cwd: Working directory
            timeout: Timeout in seconds

        Returns:
            Tuple of (return_code, stdout, stderr)
        """
        # Prepend 'git' to the command
        command = ["git"] + git_args

        # Execute with standard safety controls
        return SandboxedExecutor.run_command(command, cwd=cwd, timeout=timeout)


class RepositorySandbox:
    """
    Manage sandboxed repository operations.
    Provides automatic cleanup and size validation.
    """

    def __init__(self):
        self.config = get_config(require_llm_keys=False)
        self.sandbox_root = Path(self.config.sandbox_dir)
        self.sandbox_root.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def clone_repository(
        self, repo_url: str
    ) -> Generator[Tuple[bool, Optional[Path], Optional[str]], None, None]:
        """
        Clone a repository into a temporary sandbox.

        Args:
            repo_url: URL of the repository to clone

        Yields:
            Tuple of (success, repo_path, error_message)

        Example:
            with sandbox.clone_repository(url) as (success, path, error):
                if success:
                    # Work with repository at path
                    pass
        """
        # Validate URL
        try:
            SecurityValidator.validate_git_url(
                repo_url, allowed_domains=self.config.get_allowed_domains()
            )
        except Exception as e:
            logger.error(f"URL validation failed: {e}")
            yield (False, None, str(e))
            return

        with SandboxedExecutor.temporary_directory() as tmpdir:
            repo_path = tmpdir / "repo"

            try:
                # Clone with safety parameters
                logger.info(f"Cloning repository: {repo_url}")
                return_code, stdout, stderr = SandboxedExecutor.run_git_command(
                    [
                        "clone",
                        "--depth",
                        "1",  # Shallow clone
                        "--single-branch",  # Only main branch
                        repo_url,
                        str(repo_path),
                    ],
                    cwd=tmpdir,
                    timeout=self.config.git_clone_timeout,
                )

                if return_code != 0:
                    error_msg = f"Git clone failed: {stderr}"
                    logger.error(error_msg)
                    yield (False, None, error_msg)
                    return

                # Validate repository size
                try:
                    size_bytes = SecurityValidator.validate_directory_size(
                        repo_path, max_size_mb=self.config.max_repo_size_mb
                    )
                    logger.info(f"Repository cloned successfully ({size_bytes / 1024 / 1024:.2f}MB)")
                except ResourceLimitError as e:
                    logger.error(f"Repository size validation failed: {e}")
                    yield (False, None, str(e))
                    return

                # Success
                yield (True, repo_path, None)

            except TimeoutError as e:
                yield (False, None, f"Clone operation timed out: {e}")

            except Exception as e:
                logger.error(f"Unexpected error during clone: {e}", exc_info=True)
                yield (False, None, f"Clone failed: {e}")

    def analyze_git_history(self, repo_path: Path) -> Tuple[bool, Optional[List[dict]], Optional[str]]:
        """
        Analyze git commit history.

        Args:
            repo_path: Path to cloned repository

        Returns:
            Tuple of (success, commits_list, error_message)
        """
        try:
            return_code, stdout, stderr = SandboxedExecutor.run_git_command(
                ["log", "--oneline", "--reverse"],
                cwd=repo_path,
                timeout=30,
            )

            if return_code != 0:
                return (False, None, f"Git log failed: {stderr}")

            # Parse commit history
            commits = []
            for line in stdout.strip().split("\n"):
                if line:
                    parts = line.split(" ", 1)
                    commits.append(
                        {
                            "hash": parts[0],
                            "message": parts[1] if len(parts) > 1 else "",
                        }
                    )

            logger.debug(f"Analyzed {len(commits)} commits")
            return (True, commits, None)

        except Exception as e:
            logger.error(f"Git history analysis failed: {e}", exc_info=True)
            return (False, None, str(e))
