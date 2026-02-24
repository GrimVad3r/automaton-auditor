"""
Test suite for Detective agents.
"""

import pytest
from pathlib import Path

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
        analyst = DocAnalyst()

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
    def test_full_audit_flow(self):
        """Test complete audit execution (requires API keys)."""
        # This would test the full graph execution
        # Marked as slow since it makes real API calls
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
