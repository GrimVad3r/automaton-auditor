"""
Git repository analysis tools.
All operations are sandboxed and validated for security.
"""

from pathlib import Path
from typing import Dict, List, Optional

from ..core.state import Evidence
from ..utils.exceptions import CloneError, RepositoryError
from ..utils.logger import get_logger
from ..utils.validators import SecurityValidator
from .security import RepositorySandbox

logger = get_logger()


class GitAnalyzer:
    """
    Analyze git repositories for forensic evidence.
    Uses sandboxed operations for security.
    """

    def __init__(self):
        self.sandbox = RepositorySandbox()

    def analyze_repository(self, repo_url: str) -> Dict[str, Evidence]:
        """
        Perform comprehensive analysis of a git repository.

        Args:
            repo_url: URL of the repository to analyze

        Returns:
            Dictionary mapping evidence keys to Evidence objects
        """
        logger.info(f"Starting repository analysis: {repo_url}")
        evidences: Dict[str, Evidence] = {}
        # URL validation is a security gate; propagate violations to callers.
        SecurityValidator.validate_git_url(
            repo_url, allowed_domains=self.sandbox.config.get_allowed_domains()
        )

        with self.sandbox.clone_repository(repo_url) as (success, repo_path, error):
            if not success:
                logger.error(f"Failed to clone repository: {error}")
                evidences["clone_status"] = Evidence(
                    found=False,
                    content=None,
                    location=repo_url,
                    confidence=1.0,
                    detective_name="GitAnalyzer",
                )
                return evidences

            # Repository cloned successfully
            evidences["clone_status"] = Evidence(
                found=True,
                content="Repository cloned successfully",
                location=repo_url,
                confidence=1.0,
                detective_name="GitAnalyzer",
            )

            # Analyze commit history
            history_evidence = self._analyze_commit_history(repo_path)
            evidences.update(history_evidence)

            # Analyze file structure
            structure_evidence = self._analyze_file_structure(repo_path)
            evidences.update(structure_evidence)

        return evidences

    def _analyze_commit_history(self, repo_path: Path) -> Dict[str, Evidence]:
        """
        Analyze git commit history for quality indicators.

        Args:
            repo_path: Path to the cloned repository

        Returns:
            Dictionary of evidence about commit history
        """
        evidences: Dict[str, Evidence] = {}

        success, commits, error = self.sandbox.analyze_git_history(repo_path)

        if not success:
            logger.warning(f"Failed to analyze commit history: {error}")
            evidences["commit_history"] = Evidence(
                found=False,
                content=error,
                location=str(repo_path),
                confidence=0.0,
                detective_name="GitAnalyzer",
            )
            return evidences

        # Analyze commit patterns
        num_commits = len(commits) if commits else 0

        # Check for atomic vs monolithic development
        is_atomic = num_commits > 3
        confidence = min(num_commits / 10.0, 1.0)  # Higher confidence with more commits

        commit_summary = f"Found {num_commits} commits. "
        if is_atomic:
            commit_summary += "Development appears atomic with step-by-step progression."
        else:
            commit_summary += "Development appears monolithic (few commits)."

        evidences["commit_history"] = Evidence(
            found=True,
            content=commit_summary,
            location=f"{repo_path}/.git",
            confidence=confidence,
            detective_name="GitAnalyzer",
        )

        # Analyze commit messages for quality
        if commits:
            messages = [c["message"] for c in commits]
            has_descriptive_messages = any(len(msg) > 20 for msg in messages)

            evidences["commit_quality"] = Evidence(
                found=has_descriptive_messages,
                content=f"Sample messages: {messages[:3]}",
                location=f"{repo_path}/.git",
                confidence=0.8 if has_descriptive_messages else 0.4,
                detective_name="GitAnalyzer",
            )

        return evidences

    def _analyze_file_structure(self, repo_path: Path) -> Dict[str, Evidence]:
        """
        Analyze repository file structure for expected patterns.

        Args:
            repo_path: Path to the cloned repository

        Returns:
            Dictionary of evidence about file structure
        """
        evidences: Dict[str, Evidence] = {}

        # Check for common source directories
        source_dirs = ["src", "lib", "app"]
        found_dirs = [d for d in source_dirs if (repo_path / d).exists()]

        if found_dirs:
            evidences["source_structure"] = Evidence(
                found=True,
                content=f"Found source directories: {', '.join(found_dirs)}",
                location=str(repo_path),
                confidence=0.9,
                detective_name="GitAnalyzer",
            )
        else:
            evidences["source_structure"] = Evidence(
                found=False,
                content="No standard source directories found",
                location=str(repo_path),
                confidence=0.7,
                detective_name="GitAnalyzer",
            )

        # Check for configuration files
        config_files = [
            "pyproject.toml",
            "requirements.txt",
            "package.json",
            ".env.example",
        ]
        found_configs = [f for f in config_files if (repo_path / f).exists()]

        evidences["configuration_files"] = Evidence(
            found=len(found_configs) > 0,
            content=f"Found config files: {', '.join(found_configs)}" if found_configs else None,
            location=str(repo_path),
            confidence=0.85 if found_configs else 0.3,
            detective_name="GitAnalyzer",
        )

        # Check for documentation
        doc_files = ["README.md", "README.rst", "docs"]
        found_docs = [d for d in doc_files if (repo_path / d).exists()]

        evidences["documentation"] = Evidence(
            found=len(found_docs) > 0,
            content=f"Found documentation: {', '.join(found_docs)}" if found_docs else None,
            location=str(repo_path),
            confidence=0.8 if found_docs else 0.3,
            detective_name="GitAnalyzer",
        )

        return evidences

    def find_file(self, repo_path: Path, filename: str) -> Optional[Path]:
        """
        Search for a specific file in the repository.

        Args:
            repo_path: Path to the repository
            filename: Name of file to find

        Returns:
            Path to file if found, None otherwise
        """
        try:
            # Search recursively
            matches = list(repo_path.rglob(filename))
            if matches:
                logger.debug(f"Found file {filename} at {matches[0]}")
                return matches[0]
            return None
        except Exception as e:
            logger.error(f"Error searching for file {filename}: {e}")
            return None
