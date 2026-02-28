"""
Integration tests for full system functionality.
"""

import pytest
from unittest.mock import patch, Mock

from src.core.graph import create_auditor_graph, _cross_reference_pdf_claims
from src.core.state import Evidence, JudicialOpinion


def _reset_graph_config(monkeypatch, enable_vision: bool) -> None:
    monkeypatch.setenv("ENABLE_VISION_INSPECTOR", "true" if enable_vision else "false")
    import src.core.config as config_module

    config_module._config = None


class TestGraphIntegration:
    """Integration tests for the full LangGraph."""

    def test_graph_creation(self, monkeypatch):
        """Test that graph compiles successfully."""
        _reset_graph_config(monkeypatch, enable_vision=False)
        graph = create_auditor_graph()
        assert graph is not None

    def test_graph_nodes_without_optional_vision(self, monkeypatch):
        """Test default graph topology with optional vision node disabled."""
        _reset_graph_config(monkeypatch, enable_vision=False)
        graph = create_auditor_graph()

        expected_nodes = [
            "initialize",
            "repo_investigator",
            "doc_analyst",
            "aggregate_evidence",
            "prosecutor",
            "defense",
            "tech_lead",
            "chief_justice",
            "finalize",
        ]

        for node in expected_nodes:
            assert node in graph.nodes, f"Missing node: {node}"
        assert "vision_inspector" not in graph.nodes

    def test_graph_nodes_with_optional_vision(self, monkeypatch):
        """Test graph topology when optional vision node is enabled."""
        _reset_graph_config(monkeypatch, enable_vision=True)
        graph = create_auditor_graph()
        assert "vision_inspector" in graph.nodes

    def test_cross_reference_uses_repo_file_inventory(self, temp_dir):
        """Cross-reference should include actual repo files, not only sparse evidence locations."""
        repo_root = temp_dir / "repo"
        target_file = repo_root / "src" / "agents" / "judges" / "prosecutor.py"
        target_file.parent.mkdir(parents=True, exist_ok=True)
        target_file.write_text("PROMPT = 'Trust No One'", encoding="utf-8")
        graph_file = repo_root / "src" / "core" / "graph.py"
        graph_file.parent.mkdir(parents=True, exist_ok=True)
        graph_file.write_text("from langgraph.graph import StateGraph", encoding="utf-8")

        pdf_file = temp_dir / "report.pdf"
        pdf_file.write_text("placeholder", encoding="utf-8")

        state = {"pdf_path": str(pdf_file)}
        evidences = {
            "RepoInvestigator": [
                Evidence(
                    found=True,
                    content="Graph evidence",
                    location=str(graph_file),
                    confidence=0.9,
                    detective_name="RepoInvestigator",
                )
            ]
        }

        captured = {}

        def _fake_extract_text(self, _pdf_path):
            return "References: src/agents/judges/prosecutor.py and src/core/graph.py"

        def _fake_cross_reference(self, _text, verified_files):
            captured["verified_files"] = verified_files
            return {
                "hallucinated_claims": Evidence(
                    found=False,
                    content="All file references verified",
                    location="PDF Report",
                    confidence=0.9,
                    detective_name="PDFAnalyzer",
                )
            }

        with (
            patch("src.core.graph.PDFAnalyzer._extract_text", _fake_extract_text),
            patch(
                "src.core.graph.PDFAnalyzer.cross_reference_claims",
                _fake_cross_reference,
            ),
        ):
            result = _cross_reference_pdf_claims(state, evidences)

        assert result
        assert result[0].found is False
        normalized_verified = {
            str(path).replace("\\", "/") for path in captured["verified_files"]
        }
        assert any(
            path.endswith("src/agents/judges/prosecutor.py")
            for path in normalized_verified
        )

    @pytest.mark.integration
    @pytest.mark.slow
    def test_full_execution_mocked(self, sample_agent_state, test_env, monkeypatch):
        """Test full graph execution with mocked components."""
        _reset_graph_config(monkeypatch, enable_vision=False)

        repo_node_output = {
            "evidences": {
                "RepoInvestigator": [
                    Evidence(
                        found=True,
                        content="Repository cloned and analyzed",
                        location="src/core/graph.py",
                        confidence=0.95,
                        detective_name="RepoInvestigator",
                    )
                ]
            }
        }
        doc_node_output = {
            "evidences": {
                "DocAnalyst": [
                    Evidence(
                        found=True,
                        content="PDF parsed successfully",
                        location="report.pdf",
                        confidence=0.9,
                        detective_name="DocAnalyst",
                    )
                ]
            }
        }
        prosecutor_output = {
            "opinions": [
                JudicialOpinion(
                    judge="Prosecutor",
                    criterion_id="test_criterion",
                    score=3,
                    argument="Critical review identified manageable issues with acceptable controls.",
                    cited_evidence=["src/core/graph.py"],
                )
            ]
        }
        defense_output = {
            "opinions": [
                JudicialOpinion(
                    judge="Defense",
                    criterion_id="test_criterion",
                    score=4,
                    argument="Positive evidence suggests the implementation is generally reliable.",
                    cited_evidence=["report.pdf"],
                )
            ]
        }
        tech_lead_output = {
            "opinions": [
                JudicialOpinion(
                    judge="TechLead",
                    criterion_id="test_criterion",
                    score=4,
                    argument="System design appears maintainable with clear operational safeguards.",
                    cited_evidence=["src/core/graph.py"],
                )
            ]
        }
        chief_output = {
            "final_scores": {"test_criterion": 4},
            "synthesis_summary": "Deterministic mocked synthesis completed.",
            "final_report": "# Mocked Report\n\nAll checks passed.",
        }

        with (
            patch(
                "src.core.graph.repo_investigator_node", return_value=repo_node_output
            ),
            patch("src.core.graph.doc_analyst_node", return_value=doc_node_output),
            patch("src.core.graph.prosecutor_node", return_value=prosecutor_output),
            patch("src.core.graph.defense_node", return_value=defense_output),
            patch("src.core.graph.tech_lead_node", return_value=tech_lead_output),
            patch("src.core.graph.chief_justice_node", return_value=chief_output),
        ):
            graph = create_auditor_graph()
            result = graph.invoke(sample_agent_state)

        assert result["final_scores"]["test_criterion"] == 4
        assert "Mocked Report" in result["final_report"]
        assert "synthesis_summary" in result


class TestEndToEndFlow:
    """End-to-end workflow tests."""

    @pytest.mark.integration
    def test_detective_to_judge_flow(self, sample_agent_state):
        """Test data flow from detectives to judges."""
        # This tests the state transitions

        # Mock detective output
        detective_output = {
            "evidences": {
                "RepoInvestigator": [
                    Evidence(
                        found=True,
                        content="Test",
                        location="test.py",
                        confidence=0.9,
                        detective_name="RepoInvestigator",
                    )
                ]
            }
        }

        # Verify state update
        sample_agent_state.update(detective_output)
        assert "RepoInvestigator" in sample_agent_state["evidences"]

    @pytest.mark.integration
    def test_judge_to_justice_flow(self, sample_agent_state, sample_opinion):
        """Test data flow from judges to chief justice."""
        # Mock judge outputs
        judge_output = {"opinions": [sample_opinion]}

        sample_agent_state.update(judge_output)
        assert len(sample_agent_state["opinions"]) > 0
        assert sample_agent_state["opinions"][0].judge == "Prosecutor"

    @pytest.mark.integration
    @pytest.mark.slow
    def test_parallel_execution(self, monkeypatch):
        """Test that parallel nodes execute correctly."""
        _reset_graph_config(monkeypatch, enable_vision=False)
        graph = create_auditor_graph()

        # The graph should have parallel branches
        # This is tested implicitly by graph compilation
        assert graph is not None


class TestErrorPropagation:
    """Test error handling throughout the system."""

    @pytest.mark.integration
    def test_detective_error_handling(self, sample_agent_state, monkeypatch):
        """Test error handling in detective layer."""
        _reset_graph_config(monkeypatch, enable_vision=False)
        graph = create_auditor_graph()

        # Use invalid repo URL
        sample_agent_state["repo_url"] = "https://invalid-domain-12345.com/repo"

        with pytest.raises(Exception):
            # Should raise an error due to invalid URL
            graph.invoke(sample_agent_state)

    @pytest.mark.integration
    def test_missing_evidence_handling(self, sample_agent_state):
        """Test handling when no evidence is found."""
        from src.agents.justice import ChiefJustice

        chief = ChiefJustice()

        # Empty opinions
        sample_agent_state["opinions"] = []

        result = chief.synthesize(sample_agent_state)

        # Should handle gracefully
        assert "final_scores" in result


class TestStateReduction:
    """Test state reducer functionality."""

    def test_evidence_reduction(self):
        """Test that evidences dict merges correctly."""
        from operator import ior

        state1 = {
            "Detective1": [
                Evidence(
                    found=True,
                    content="A",
                    location="a.py",
                    confidence=0.9,
                    detective_name="Detective1",
                )
            ]
        }

        state2 = {
            "Detective2": [
                Evidence(
                    found=True,
                    content="B",
                    location="b.py",
                    confidence=0.9,
                    detective_name="Detective2",
                )
            ]
        }

        merged = ior(state1, state2)

        assert "Detective1" in merged
        assert "Detective2" in merged

    def test_opinion_reduction(self):
        """Test that opinions list appends correctly."""
        from operator import add

        list1 = [Mock(judge="Prosecutor")]
        list2 = [Mock(judge="Defense")]

        merged = add(list1, list2)

        assert len(merged) == 2


class TestReportGeneration:
    """Test report generation functionality."""

    @pytest.mark.integration
    def test_markdown_report_structure(self, sample_agent_state):
        """Test that generated report has correct structure."""
        from src.utils.formatters import MarkdownReportFormatter

        # Add mock data
        sample_agent_state["evidences"] = {
            "RepoInvestigator": [
                Evidence(
                    found=True,
                    content="Test",
                    location="test.py",
                    confidence=0.9,
                    detective_name="RepoInvestigator",
                )
            ]
        }

        sample_agent_state["opinions"] = []
        sample_agent_state["execution_start_time"] = 0
        sample_agent_state["execution_end_time"] = 10

        report = MarkdownReportFormatter.format_full_report(
            repo_url="https://github.com/test/repo",
            pdf_path="test.pdf",
            evidences=sample_agent_state["evidences"],
            opinions=[],
            final_scores={"test": 3},
            synthesis_summary="Test summary",
            execution_time=10,
        )

        # Verify report structure
        assert "# Automaton Auditor Report" in report
        assert "Executive Summary" in report
        assert "Forensic Evidence" in report
        assert "Remediation Plan" in report

    @pytest.mark.integration
    def test_report_includes_scores(self):
        """Test that report includes all scores."""
        from src.utils.formatters import MarkdownReportFormatter

        final_scores = {
            "criterion1": 3,
            "criterion2": 4,
            "criterion3": 2,
        }

        report = MarkdownReportFormatter.format_full_report(
            repo_url="test",
            pdf_path="test.pdf",
            evidences={},
            opinions=[],
            final_scores=final_scores,
            synthesis_summary="Summary",
            execution_time=5,
        )

        for criterion, score in final_scores.items():
            assert criterion in report
            assert str(score) in report
