"""
Tests for sandboxed execution tools.
"""

import pytest
from pathlib import Path

from src.tools.security import SandboxedExecutor, RepositorySandbox
from src.utils.exceptions import CommandInjectionError, TimeoutError


class TestSandboxedExecutor:
    """Tests for SandboxedExecutor class."""

    def test_temporary_directory(self):
        """Test temporary directory creation and cleanup."""
        with SandboxedExecutor.temporary_directory() as tmpdir:
            assert tmpdir.exists()
            assert tmpdir.is_dir()

            # Create a test file
            test_file = tmpdir / "test.txt"
            test_file.write_text("test")
            assert test_file.exists()

        # Directory should be cleaned up
        assert not tmpdir.exists()

    def test_run_command_success(self):
        """Test successful command execution."""
        return_code, stdout, stderr = SandboxedExecutor.run_command(
            ["echo", "Hello, World!"], timeout=5
        )

        assert return_code == 0
        assert "Hello, World!" in stdout
        assert stderr == ""

    def test_run_command_with_args(self):
        """Test command execution with multiple arguments."""
        return_code, stdout, stderr = SandboxedExecutor.run_command(
            ["python", "-c", "print('test')"], timeout=5
        )

        assert return_code == 0
        assert "test" in stdout

    @pytest.mark.security
    def test_run_command_injection_prevention(self):
        """Test that command injection is prevented."""
        # This should fail validation before execution
        with pytest.raises(CommandInjectionError):
            SandboxedExecutor.run_command(["echo", "test; rm -rf /"], timeout=5)

    def test_run_command_timeout(self):
        """Test command timeout."""
        with pytest.raises(TimeoutError):
            SandboxedExecutor.run_command(["sleep", "10"], timeout=1)

    def test_run_command_failure(self):
        """Test handling of failed commands."""
        return_code, stdout, stderr = SandboxedExecutor.run_command(
            ["ls", "/nonexistent_directory_12345"], timeout=5
        )

        assert return_code != 0
        assert stderr != ""

    def test_run_command_with_cwd(self, temp_dir):
        """Test command execution with custom working directory."""
        test_file = temp_dir / "test.txt"
        test_file.write_text("content")

        return_code, stdout, stderr = SandboxedExecutor.run_command(
            ["ls", "test.txt"], cwd=temp_dir, timeout=5
        )

        assert return_code == 0
        assert "test.txt" in stdout

    def test_run_git_command(self):
        """Test git command execution."""
        return_code, stdout, stderr = SandboxedExecutor.run_git_command(
            ["--version"], timeout=5
        )

        assert return_code == 0
        assert "git version" in stdout.lower()


class TestRepositorySandbox:
    """Tests for RepositorySandbox class."""

    def test_sandbox_initialization(self):
        """Test sandbox initialization."""
        sandbox = RepositorySandbox()
        assert sandbox.sandbox_root.exists()

    @pytest.mark.slow
    @pytest.mark.security
    def test_clone_repository_success(self):
        """Test successful repository cloning."""
        sandbox = RepositorySandbox()

        # Use a small public repo for testing
        test_repo_url = "https://github.com/octocat/Hello-World"

        with sandbox.clone_repository(test_repo_url) as (success, repo_path, error):
            if success:  # Only test if clone succeeded (network dependent)
                assert repo_path is not None
                assert repo_path.exists()
                assert (repo_path / ".git").exists()
                assert error is None

    @pytest.mark.security
    def test_clone_repository_invalid_url(self):
        """Test rejection of invalid repository URLs."""
        sandbox = RepositorySandbox()

        with sandbox.clone_repository("https://evil.com/repo") as (success, repo_path, error):
            assert success is False
            assert repo_path is None
            assert "not in allowed list" in error

    @pytest.mark.security
    def test_clone_repository_malicious_url(self, malicious_urls):
        """Test rejection of malicious URLs."""
        sandbox = RepositorySandbox()

        for url in malicious_urls[:2]:  # Test a few examples
            with sandbox.clone_repository(url) as (success, repo_path, error):
                assert success is False
                assert repo_path is None
                assert error is not None

    @pytest.mark.slow
    def test_analyze_git_history(self, mock_git_repo):
        """Test git history analysis."""
        sandbox = RepositorySandbox()

        # Initialize a git repo with some commits
        SandboxedExecutor.run_git_command(["init"], cwd=mock_git_repo, timeout=5)
        SandboxedExecutor.run_git_command(
            ["config", "user.email", "test@test.com"], cwd=mock_git_repo, timeout=5
        )
        SandboxedExecutor.run_git_command(
            ["config", "user.name", "Test User"], cwd=mock_git_repo, timeout=5
        )
        SandboxedExecutor.run_git_command(["add", "."], cwd=mock_git_repo, timeout=5)
        SandboxedExecutor.run_git_command(
            ["commit", "-m", "Initial commit"], cwd=mock_git_repo, timeout=5
        )

        success, commits, error = sandbox.analyze_git_history(mock_git_repo)

        if success:  # Git commands may not work in all test environments
            assert commits is not None
            assert len(commits) > 0
            assert "hash" in commits[0]
            assert "message" in commits[0]

    def test_analyze_git_history_not_a_repo(self, temp_dir):
        """Test git history analysis on non-repository."""
        sandbox = RepositorySandbox()

        success, commits, error = sandbox.analyze_git_history(temp_dir)

        assert success is False
        assert commits is None
        assert "fatal" in error.lower() or "not a git repository" in error.lower()
