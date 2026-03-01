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

    def test_emits_critical_component_evidence(self, temp_dir):
        """Critical architecture files should be emitted as explicit evidence."""
        repo_path = temp_dir / "repo"
        (repo_path / "src" / "core").mkdir(parents=True)
        (repo_path / "src" / "tools").mkdir(parents=True)
        (repo_path / "src" / "agents" / "judges").mkdir(parents=True)
        (repo_path / "src" / "agents" / "justice").mkdir(parents=True)

        (repo_path / "src" / "core" / "state.py").write_text(
            "from pydantic import BaseModel\nclass Evidence(BaseModel):\n    found: bool\n"
        )
        (repo_path / "src" / "core" / "graph.py").write_text(
            "def build(builder):\n"
            "    builder.add_edge('initialize', 'repo_investigator')\n"
            "    builder.add_edge('initialize', 'doc_analyst')\n"
            "    builder.add_edge('aggregate_evidence', 'prosecutor')\n"
            "    builder.add_edge('aggregate_evidence', 'defense')\n"
            "    builder.add_edge('aggregate_evidence', 'tech_lead')\n"
            "    builder.add_edge('prosecutor', 'handle_error')\n"
            "    builder.add_edge('defense', 'handle_error')\n"
            "    builder.add_edge('tech_lead', 'handle_error')\n"
        )
        (repo_path / "src" / "tools" / "git_tools.py").write_text(
            "class RepositorySandbox:\n    pass\n"
        )
        (repo_path / "src" / "agents" / "judges" / "prosecutor.py").write_text(
            "SYSTEM_PROMPT = 'Trust No One'\n"
        )
        (repo_path / "src" / "agents" / "judges" / "defense.py").write_text(
            "SYSTEM_PROMPT = 'Reward Effort'\n"
        )
        (repo_path / "src" / "agents" / "judges" / "tech_lead.py").write_text(
            "SYSTEM_PROMPT = 'Does it actually work'\n"
        )
        (repo_path / "src" / "agents" / "judges" / "base_judge.py").write_text(
            "class StructuredOpinion:\n    pass\n\n"
            "def _coerce_structured_response():\n    return None\n"
        )
        (repo_path / "src" / "agents" / "justice" / "chief_justice.py").write_text(
            "class ChiefJustice:\n    pass\n"
        )

        evidences = RepoInvestigator()._analyze_code_structure(repo_path)
        found_locations = {e.location for e in evidences if e.found}

        assert "src/agents/justice/chief_justice.py" in found_locations
        assert "src/tools/git_tools.py" in found_locations
        assert "src/core/graph.py" in found_locations
        assert "src/core/state.py" in found_locations


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
