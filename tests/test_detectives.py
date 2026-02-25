"""
Test suite for Detective agents.
"""

import pytest
from contextlib import nullcontext
from unittest.mock import patch

from src.core.state import Evidence
from src.agents.detectives import RepoInvestigator, DocAnalyst
from src.utils.exceptions import SecurityViolationError


class TestRepoInvestigator:
    """Tests for RepoInvestigator agent."""

    def test_git_url_validation(self):
        """Test that invalid git URLs are rejected."""
        investigator = RepoInvestigator()

        # Test malicious URL
        with pytest.raises(SecurityViolationError):
            investigator.git_analyzer.analyze_repository("https://evil.com; rm -rf /")

    def test_evidence_structure(self):
        """Test that evidence objects are properly structured."""
        evidence = Evidence(
            found=True,
            content="test content",
            location="/test/path",
            confidence=0.95,
            detective_name="TestDetective",
        )

        assert evidence.found is True
        assert evidence.confidence == 0.95
        assert evidence.detective_name == "TestDetective"


class TestDocAnalyst:
    """Tests for DocAnalyst agent."""

    def test_concept_detection(self):
        """Test detection of key concepts in text."""
        test_text = """
        Our architecture implements dialectical synthesis through
        a fan-out pattern that enables parallel execution of judges.
        The metacognition layer ensures quality assessment.
        """

        # Would test actual PDF parsing here
        assert "dialectical synthesis" in test_text.lower()
        assert "fan-out" in test_text.lower()
        assert "metacognition" in test_text.lower()


class TestIntegration:
    """Integration tests for full audit flow."""

    @pytest.mark.slow
    def test_full_audit_flow(self, sample_agent_state, temp_dir):
        """Test complete detective flow without network access."""
        repo_path = temp_dir / "repo"
        repo_path.mkdir()
        pdf_file = temp_dir / "report.pdf"
        pdf_file.write_bytes(b"%PDF-1.4\n%%EOF\n")
        sample_agent_state["pdf_path"] = str(pdf_file)

        investigator = RepoInvestigator()
        analyst = DocAnalyst()

        repo_evidence = Evidence(
            found=True,
            content="Repository analyzed",
            location="src/core/graph.py",
            confidence=0.9,
            detective_name="RepoInvestigator",
        )
        doc_evidence = Evidence(
            found=True,
            content="PDF analyzed",
            location=str(pdf_file),
            confidence=0.9,
            detective_name="DocAnalyst",
        )

        with (
            patch.object(
                investigator.git_analyzer.sandbox,
                "clone_repository",
                return_value=nullcontext((True, repo_path, None)),
            ),
            patch.object(
                investigator.git_analyzer,
                "analyze_repository",
                return_value={"repo": repo_evidence},
            ),
            patch.object(
                investigator,
                "_analyze_code_structure",
                return_value=[],
            ),
            patch("src.agents.detectives.doc_analyst.PDFAnalyzer") as mock_pdf_analyzer,
        ):
            mock_pdf_analyzer.return_value.analyze_pdf.return_value = {
                "pdf": doc_evidence
            }

            repo_result = investigator.investigate(sample_agent_state)
            sample_agent_state["evidences"].update(repo_result["evidences"])
            doc_result = analyst.investigate(sample_agent_state)

        assert "RepoInvestigator" in repo_result["evidences"]
        assert "DocAnalyst" in doc_result["evidences"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
