"""
RepoInvestigator: The Code Detective
Forensically analyzes repository structure, git history, and code artifacts.
"""

import time
from pathlib import Path
from typing import Dict, List

from ...core.state import AgentState, DetectiveOutput, Evidence
from ...tools import ASTAnalyzer, GitAnalyzer
from ...utils.exceptions import NodeExecutionError
from ...utils.logger import get_logger

logger = get_logger()


class RepoInvestigator:
    """
    Detective agent that analyzes code repositories.
    Objective: Collect facts without subjective interpretation.
    """

    def __init__(self):
        self.git_analyzer = GitAnalyzer()

    def investigate(self, state: AgentState) -> Dict:
        """
        Execute forensic analysis of the repository.

        Args:
            state: Current graph state

        Returns:
            Dictionary with evidences key containing collected evidence
        """
        logger.log_node_start("RepoInvestigator")
        start_time = time.time()

        try:
            repo_url = state["repo_url"]
            logger.set_context(repo_url=repo_url)

            # Collect evidence
            evidence_list: List[Evidence] = []

            # Phase 1: Git-level forensics
            logger.info("Phase 1: Analyzing git repository structure")
            git_evidences = self.git_analyzer.analyze_repository(repo_url)
            evidence_list.extend(git_evidences.values())

            clone_status = git_evidences.get("clone_status")
            if clone_status and not clone_status.found:
                raise ValueError(f"Repository analysis failed for URL: {repo_url}")

            for key, evidence in git_evidences.items():
                logger.log_evidence_found(key, evidence.confidence)

            # Phase 2: Code-level forensics
            # We need to clone the repo again for AST analysis
            # (In a real implementation, we'd reuse the cloned repo)
            logger.info("Phase 2: Performing AST analysis on key files")

            with self.git_analyzer.sandbox.clone_repository(repo_url) as (
                success,
                repo_path,
                error,
            ):
                if success and repo_path:
                    code_evidences = self._analyze_code_structure(repo_path)
                    evidence_list.extend(code_evidences)

                    for evidence in code_evidences:
                        logger.log_evidence_found(evidence.location, evidence.confidence)

            duration = time.time() - start_time
            logger.log_node_complete("RepoInvestigator", duration)
            logger.clear_context()

            # Return in format expected by state reducer
            return {
                "evidences": {
                    "RepoInvestigator": evidence_list,
                }
            }

        except Exception as e:
            duration = time.time() - start_time
            logger.log_node_error("RepoInvestigator", e)
            logger.clear_context()

            raise NodeExecutionError("RepoInvestigator", e)

    def _analyze_code_structure(self, repo_path: Path) -> List[Evidence]:
        """
        Analyze code structure using AST.

        Args:
            repo_path: Path to cloned repository

        Returns:
            List of Evidence objects
        """
        evidences: List[Evidence] = []

        # Look for key files
        key_files = [
            "src/state.py",
            "src/graph.py",
            "src/core/state.py",
            "src/core/graph.py",
        ]

        ast_analyzer = ASTAnalyzer(repo_path)

        for file_pattern in key_files:
            file_path = repo_path / file_pattern

            if file_path.exists():
                logger.debug(f"Analyzing file: {file_pattern}")

                try:
                    file_evidences = ast_analyzer.analyze_file(file_path)
                    evidences.extend(file_evidences.values())

                    # Specifically check for LangGraph definition
                    if "graph" in file_pattern.lower():
                        graph_evidence = ast_analyzer.find_langgraph_definition(file_path)
                        if graph_evidence:
                            evidences.append(graph_evidence)

                except Exception as e:
                    logger.warning(f"Failed to analyze {file_pattern}: {e}")
                    evidences.append(
                        Evidence(
                            found=False,
                            content=f"Analysis failed: {str(e)}",
                            location=file_pattern,
                            confidence=0.5,
                            detective_name="RepoInvestigator",
                        )
                    )

        # Check for tools directory
        tools_dir = repo_path / "src" / "tools"
        if tools_dir.exists():
            # Analyze tool files for security patterns
            for tool_file in tools_dir.glob("*.py"):
                try:
                    tool_evidences = ast_analyzer.analyze_file(tool_file)

                    # Extract security-specific evidence
                    if "security_vulnerabilities" in tool_evidences:
                        evidences.append(tool_evidences["security_vulnerabilities"])

                except Exception as e:
                    logger.warning(f"Failed to analyze tool file {tool_file}: {e}")

        return evidences


# Node function for LangGraph
def repo_investigator_node(state: AgentState) -> Dict:
    """
    LangGraph node wrapper for RepoInvestigator.

    Args:
        state: Current graph state

    Returns:
        State updates
    """
    investigator = RepoInvestigator()
    return investigator.investigate(state)
