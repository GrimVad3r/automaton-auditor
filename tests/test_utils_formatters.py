"""
Tests for report formatters.
"""

import pytest

from src.utils.formatters import MarkdownReportFormatter, JSONReportFormatter
from src.core.state import Evidence, JudicialOpinion


class TestMarkdownReportFormatter:
    """Tests for MarkdownReportFormatter."""

    @pytest.fixture
    def sample_data(self):
        """Create sample data for formatting."""
        evidences = {
            "RepoInvestigator": [
                Evidence(
                    found=True,
                    content="StateGraph definition found",
                    location="src/graph.py:15",
                    confidence=0.95,
                    detective_name="RepoInvestigator",
                )
            ],
            "DocAnalyst": [
                Evidence(
                    found=True,
                    content="Dialectical synthesis mentioned",
                    location="report.pdf:page 3",
                    confidence=0.85,
                    detective_name="DocAnalyst",
                )
            ],
        }

        opinions = [
            JudicialOpinion(
                judge="Prosecutor",
                criterion_id="langgraph_architecture",
                score=2,
                argument="Architecture is functional but lacks parallel execution patterns. Missing fan-out/fan-in structure.",
                cited_evidence=["RepoInvestigator:src/graph.py:15"],
            ),
            JudicialOpinion(
                judge="Defense",
                criterion_id="langgraph_architecture",
                score=4,
                argument="Code demonstrates solid understanding of LangGraph concepts. State management is well implemented.",
                cited_evidence=["RepoInvestigator:src/graph.py:15"],
            ),
            JudicialOpinion(
                judge="TechLead",
                criterion_id="langgraph_architecture",
                score=3,
                argument="Implementation is workable but could benefit from better orchestration. Meets basic requirements.",
                cited_evidence=["RepoInvestigator:src/graph.py:15"],
            ),
        ]

        final_scores = {
            "langgraph_architecture": 3,
            "forensic_accuracy_code": 4,
        }

        return evidences, opinions, final_scores

    def test_format_full_report(self, sample_data):
        """Test full report generation."""
        evidences, opinions, final_scores = sample_data

        report = MarkdownReportFormatter.format_full_report(
            repo_url="https://github.com/test/repo",
            pdf_path="test_report.pdf",
            evidences=evidences,
            opinions=opinions,
            final_scores=final_scores,
            synthesis_summary="Test summary",
            execution_time=15.5,
        )

        # Check structure
        assert "# Automaton Auditor Report" in report
        assert "Executive Summary" in report
        assert "Forensic Evidence" in report
        assert "Judicial Analysis" in report
        assert "Remediation Plan" in report

        # Check data presence
        assert "https://github.com/test/repo" in report
        assert "test_report.pdf" in report
        assert "15.5" in report or "15.50" in report

    def test_report_includes_evidences(self, sample_data):
        """Test that report includes all evidence."""
        evidences, opinions, final_scores = sample_data

        report = MarkdownReportFormatter.format_full_report(
            repo_url="test",
            pdf_path="test.pdf",
            evidences=evidences,
            opinions=opinions,
            final_scores=final_scores,
            synthesis_summary="Summary",
            execution_time=10,
        )

        assert "RepoInvestigator" in report
        assert "DocAnalyst" in report
        assert "StateGraph definition found" in report

    def test_report_includes_opinions(self, sample_data):
        """Test that report includes all opinions."""
        evidences, opinions, final_scores = sample_data

        report = MarkdownReportFormatter.format_full_report(
            repo_url="test",
            pdf_path="test.pdf",
            evidences=evidences,
            opinions=opinions,
            final_scores=final_scores,
            synthesis_summary="Summary",
            execution_time=10,
        )

        assert "Prosecutor" in report
        assert "Defense" in report
        assert "TechLead" in report

    def test_report_includes_scores(self, sample_data):
        """Test that report includes final scores."""
        evidences, opinions, final_scores = sample_data

        report = MarkdownReportFormatter.format_full_report(
            repo_url="test",
            pdf_path="test.pdf",
            evidences=evidences,
            opinions=opinions,
            final_scores=final_scores,
            synthesis_summary="Summary",
            execution_time=10,
        )

        for criterion, score in final_scores.items():
            assert criterion in report
            assert f"{score}/5" in report or f"{score}" in report

    def test_generate_remediation_low_scores(self, sample_data):
        """Test remediation generation for low scores."""
        evidences, opinions, final_scores = sample_data
        final_scores["test_criterion"] = 2

        opinions_by_criterion = {
            "test_criterion": [
                JudicialOpinion(
                    judge="Prosecutor",
                    criterion_id="test_criterion",
                    score=1,
                    argument="Critical security flaw detected. Code uses os.system without input validation.",
                    cited_evidence=[],
                ),
                JudicialOpinion(
                    judge="TechLead",
                    criterion_id="test_criterion",
                    score=2,
                    argument="Security issue must be addressed. Also improve error handling throughout.",
                    cited_evidence=[],
                ),
            ]
        }

        remediation = MarkdownReportFormatter._generate_remediation(
            final_scores, opinions_by_criterion
        )

        assert "test_criterion" in remediation
        assert "Critical" in remediation or "security" in remediation.lower()

    def test_generate_remediation_high_scores(self):
        """Test remediation when all scores are high."""
        final_scores = {
            "criterion1": 5,
            "criterion2": 4,
            "criterion3": 5,
        }

        remediation = MarkdownReportFormatter._generate_remediation(final_scores, {})

        assert "All criteria met expectations" in remediation or "No immediate remediation" in remediation

    def test_generate_dialectics_summary(self, sample_data):
        """Test dialectics summary generation."""
        evidences, opinions, final_scores = sample_data

        opinions_by_criterion = {
            "langgraph_architecture": opinions
        }

        summary = MarkdownReportFormatter._generate_dialectics_summary(opinions_by_criterion)

        assert "dialectical" in summary.lower()
        assert "langgraph_architecture" in summary


class TestJSONReportFormatter:
    """Tests for JSONReportFormatter."""

    def test_format_report(self, sample_evidence, sample_opinion):
        """Test JSON report formatting."""
        evidences = {"TestDetective": [sample_evidence]}
        opinions = [sample_opinion]
        final_scores = {"test_criterion": 3}

        report = JSONReportFormatter.format_report(
            repo_url="https://github.com/test/repo",
            evidences=evidences,
            opinions=opinions,
            final_scores=final_scores,
        )

        # Check structure
        assert "metadata" in report
        assert "scores" in report
        assert "evidences" in report
        assert "opinions" in report

        # Check data
        assert report["metadata"]["repo_url"] == "https://github.com/test/repo"
        assert report["scores"]["test_criterion"] == 3

    def test_json_serialization(self, sample_evidence, sample_opinion):
        """Test that report is JSON-serializable."""
        import json

        evidences = {"TestDetective": [sample_evidence]}
        opinions = [sample_opinion]
        final_scores = {"test_criterion": 3}

        report = JSONReportFormatter.format_report(
            repo_url="test",
            evidences=evidences,
            opinions=opinions,
            final_scores=final_scores,
        )

        # Should be serializable
        json_str = json.dumps(report)
        assert isinstance(json_str, str)

        # Should be deserializable
        deserialized = json.loads(json_str)
        assert deserialized["scores"]["test_criterion"] == 3

    def test_empty_data(self):
        """Test formatting with empty data."""
        report = JSONReportFormatter.format_report(
            repo_url="test",
            evidences={},
            opinions=[],
            final_scores={},
        )

        assert report["evidences"] == {}
        assert report["opinions"] == []
        assert report["scores"] == {}
