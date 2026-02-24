"""
Tests for agent implementations.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

from src.agents.detectives import RepoInvestigator, DocAnalyst
from src.agents.judges import Prosecutor, Defense, TechLead
from src.agents.judges.base_judge import StructuredOpinion
from src.agents.justice import ChiefJustice
from src.core.state import Evidence, JudicialOpinion


class TestRepoInvestigator:
    """Tests for RepoInvestigator detective."""

    def test_initialization(self):
        """Test detective initialization."""
        detective = RepoInvestigator()
        assert detective.git_analyzer is not None

    @pytest.mark.slow
    def test_investigate_structure(self, sample_agent_state):
        """Test investigation returns correct structure."""
        detective = RepoInvestigator()

        # Mock the git analyzer to avoid actual cloning
        with patch.object(detective.git_analyzer, "analyze_repository") as mock_analyze:
            mock_analyze.return_value = {
                "test_evidence": Evidence(
                    found=True,
                    content="Test",
                    location="test.py",
                    confidence=0.9,
                    detective_name="RepoInvestigator",
                )
            }

            result = detective.investigate(sample_agent_state)

            assert "evidences" in result
            assert "RepoInvestigator" in result["evidences"]

    def test_investigate_error_handling(self, sample_agent_state):
        """Test error handling during investigation."""
        detective = RepoInvestigator()

        # Force an error by using invalid URL
        sample_agent_state["repo_url"] = "invalid-url"

        with pytest.raises(Exception):
            detective.investigate(sample_agent_state)


class TestDocAnalyst:
    """Tests for DocAnalyst detective."""

    def test_initialization(self):
        """Test detective initialization."""
        detective = DocAnalyst()
        assert detective.pdf_analyzer is None  # Initialized per-investigation

    def test_investigate_structure(self, sample_agent_state, mock_pdf_file):
        """Test investigation returns correct structure."""
        detective = DocAnalyst()
        sample_agent_state["pdf_path"] = str(mock_pdf_file)

        # Mock PDF analyzer
        with patch("src.agents.detectives.doc_analyst.PDFAnalyzer") as MockAnalyzer:
            mock_instance = MockAnalyzer.return_value
            mock_instance.analyze_pdf.return_value = {
                "pdf_extracted": Evidence(
                    found=True,
                    content="Test PDF",
                    location=str(mock_pdf_file),
                    confidence=0.95,
                    detective_name="DocAnalyst",
                )
            }

            result = detective.investigate(sample_agent_state)

            assert "evidences" in result
            assert "DocAnalyst" in result["evidences"]

    def test_cross_reference_integration(self, sample_agent_state, mock_pdf_file):
        """Test cross-referencing with RepoInvestigator evidence."""
        detective = DocAnalyst()
        sample_agent_state["pdf_path"] = str(mock_pdf_file)

        # Add mock RepoInvestigator evidence
        sample_agent_state["evidences"] = {
            "RepoInvestigator": [
                Evidence(
                    found=True,
                    content="Test",
                    location="src/state.py",
                    confidence=0.9,
                    detective_name="RepoInvestigator",
                )
            ]
        }

        with patch("src.agents.detectives.doc_analyst.PDFAnalyzer") as MockAnalyzer:
            mock_instance = MockAnalyzer.return_value
            mock_instance.analyze_pdf.return_value = {}
            mock_instance._extract_text.return_value = "Test text"
            mock_instance.cross_reference_claims.return_value = {}

            result = detective.investigate(sample_agent_state)
            assert "evidences" in result


class TestProsecutor:
    """Tests for Prosecutor judge."""

    def test_initialization(self):
        """Test judge initialization."""
        judge = Prosecutor()
        assert judge.judge_name == "Prosecutor"
        assert judge.llm is not None

    def test_system_prompt(self):
        """Test prosecutor's system prompt."""
        judge = Prosecutor()
        prompt = judge.get_system_prompt()

        assert "PROSECUTOR" in prompt
        assert "Trust No One" in prompt
        assert "security" in prompt.lower()

    @pytest.mark.requires_api
    def test_evaluate_criteria_structure(self, sample_rubric):
        """Test evaluation returns correct structure."""
        judge = Prosecutor()

        # Mock LLM to avoid API calls
        with patch.object(judge, "llm") as mock_llm:
            mock_llm.invoke.return_value = Mock(
                criterion_id="test_criterion",
                score=2,
                argument="This is a test argument with sufficient length to pass validation.",
                cited_evidence=["evidence1"],
            )

            evidences = {
                "TestDetective": [
                    Evidence(
                        found=True,
                        content="Test",
                        location="test.py",
                        confidence=0.9,
                        detective_name="TestDetective",
                    )
                ]
            }

            opinions = judge.evaluate_all_criteria(sample_rubric, evidences)

            assert len(opinions) > 0
            assert all(isinstance(op, JudicialOpinion) for op in opinions)
            assert all(op.judge == "Prosecutor" for op in opinions)

    def test_tool_use_failure_falls_back_to_json(self, sample_rubric):
        """Test fallback to JSON response mode when tool/function calling fails."""
        judge = Prosecutor()
        criterion = sample_rubric["dimensions"][0]
        judge.llm = Mock()
        judge.llm.invoke.side_effect = Exception("tool_use_failed")
        judge.raw_llm = Mock()

        fallback_response = Mock(
            content=(
                '{"criterion_id":"test_criterion","score":3,'
                '"argument":"This fallback argument is intentionally long enough to satisfy '
                'the minimum character requirement for structured opinion validation.",'
                '"cited_evidence":["fallback_evidence"]}'
            )
        )
        judge.raw_llm.invoke.return_value = fallback_response
        opinion = judge.render_opinion(criterion, {})

        assert opinion.score == 3
        assert opinion.criterion_id == "test_criterion"
        assert "fallback" in opinion.argument.lower()

    def test_rate_limit_retry_then_success(self, sample_rubric):
        """Test retry behavior for transient rate-limit errors."""
        judge = Prosecutor()
        criterion = sample_rubric["dimensions"][0]
        judge.llm = Mock()
        judge.raw_llm = Mock()

        judge.llm.invoke.side_effect = [
            Exception("429 rate_limit_exceeded"),
            {
                "criterion_id": "test_criterion",
                "score": 4,
                "argument": (
                    "This retry result is intentionally long enough to satisfy the "
                    "minimum argument length while verifying rate-limit recovery."
                ),
                "cited_evidence": ["retry_evidence"],
            },
        ]

        with patch("src.agents.judges.base_judge.time.sleep", return_value=None):
            opinion = judge.render_opinion(criterion, {})

        assert opinion.score == 4
        assert opinion.criterion_id == "test_criterion"

    def test_opinion_grounding_removes_unverified_paths(self, sample_rubric):
        """Test that hallucinated file-path claims are removed from opinions."""
        judge = Prosecutor()
        criterion = sample_rubric["dimensions"][0]

        evidences = {
            "RepoInvestigator": [
                Evidence(
                    found=True,
                    content="State graph found",
                    location="src/core/graph.py",
                    confidence=0.95,
                    detective_name="RepoInvestigator",
                )
            ]
        }

        long_argument = (
            "The implementation references src/graph.py and claims parity with src/core/graph.py. "
            "This narrative is intentionally long enough to satisfy minimum length requirements."
        )
        grounded_response = StructuredOpinion(
            criterion_id="test_criterion",
            score=4,
            argument=long_argument,
            cited_evidence=["src/graph.py"],
        )

        with patch.object(judge, "_invoke_with_fallback", return_value=grounded_response):
            opinion = judge.render_opinion(criterion, evidences)

        assert "[UNVERIFIED_PATH]" in opinion.argument
        assert opinion.score == 3
        assert all("src/graph.py" not in cite for cite in opinion.cited_evidence)

    def test_opinion_grounding_removes_unsupported_quant_claims(self, sample_rubric):
        """Unsupported percentage claims should be pruned and penalized."""
        judge = Prosecutor()
        criterion = sample_rubric["dimensions"][0]
        evidences = {
            "RepoInvestigator": [
                Evidence(
                    found=True,
                    content="Pydantic models found in src/core/state.py",
                    location="src/core/state.py",
                    confidence=0.95,
                    detective_name="RepoInvestigator",
                )
            ]
        }

        argument = (
            "Pydantic models are present in src/core/state.py and strongly typed. "
            "There is 90% similarity across all judge prompts without exception, which proves collusion. "
            "This sentence is intentionally long enough to satisfy minimum argument length constraints."
        )
        grounded_response = StructuredOpinion(
            criterion_id="test_criterion",
            score=4,
            argument=argument,
            cited_evidence=["src/core/state.py"],
        )

        with patch.object(judge, "_invoke_with_fallback", return_value=grounded_response):
            opinion = judge.render_opinion(criterion, evidences)

        assert "90% similarity" not in opinion.argument
        assert "Unverified claims were removed" in opinion.argument
        assert opinion.score == 3

    def test_opinion_grounding_rejects_directory_only_citations(self, sample_rubric):
        """Directory-only citations should be dropped in favor of verified file evidence."""
        judge = Prosecutor()
        criterion = sample_rubric["dimensions"][0]
        evidences = {
            "RepoInvestigator": [
                Evidence(
                    found=True,
                    content="Sandbox utility exists",
                    location="src/tools/security.py",
                    confidence=0.93,
                    detective_name="RepoInvestigator",
                )
            ]
        }
        grounded_response = StructuredOpinion(
            criterion_id="test_criterion",
            score=4,
            argument=(
                "The security tooling is present and generally functional with adequate structure. "
                "This argument is long enough to satisfy validation constraints."
            ),
            cited_evidence=["src/tools/"],
        )

        with patch.object(judge, "_invoke_with_fallback", return_value=grounded_response):
            opinion = judge.render_opinion(criterion, evidences)

        assert "src/tools/" not in opinion.cited_evidence
        assert any("src/tools/security.py" in cite for cite in opinion.cited_evidence)


class TestDefense:
    """Tests for Defense judge."""

    def test_initialization(self):
        """Test judge initialization."""
        judge = Defense()
        assert judge.judge_name == "Defense"

    def test_system_prompt(self):
        """Test defense attorney's system prompt."""
        judge = Defense()
        prompt = judge.get_system_prompt()

        assert "DEFENSE" in prompt
        assert "Reward Effort" in prompt
        assert "generous" in prompt.lower()

    @pytest.mark.requires_api
    def test_evaluate_criteria_structure(self, sample_rubric):
        """Test evaluation returns correct structure."""
        judge = Defense()

        with patch.object(judge, "llm") as mock_llm:
            mock_llm.invoke.return_value = Mock(
                criterion_id="test_criterion",
                score=4,
                argument="This is a generous assessment with sufficient length for validation.",
                cited_evidence=["evidence1"],
            )

            evidences = {}
            opinions = judge.evaluate_all_criteria(sample_rubric, evidences)

            assert len(opinions) > 0
            assert all(op.judge == "Defense" for op in opinions)


class TestTechLead:
    """Tests for TechLead judge."""

    def test_initialization(self):
        """Test judge initialization."""
        judge = TechLead()
        assert judge.judge_name == "TechLead"

    def test_system_prompt(self):
        """Test tech lead's system prompt."""
        judge = TechLead()
        prompt = judge.get_system_prompt()

        assert "TECH LEAD" in prompt
        assert "Does it actually work" in prompt
        assert "maintainable" in prompt.lower()


class TestChiefJustice:
    """Tests for ChiefJustice synthesis engine."""

    def test_initialization(self):
        """Test chief justice initialization."""
        chief = ChiefJustice()
        assert chief is not None

    def test_synthesize_structure(self, sample_agent_state):
        """Test synthesis returns correct structure."""
        chief = ChiefJustice()

        # Add mock opinions
        sample_agent_state["opinions"] = [
            JudicialOpinion(
                judge="Prosecutor",
                criterion_id="test_criterion",
                score=2,
                argument="Harsh assessment with sufficient length.",
                cited_evidence=["evidence1"],
            ),
            JudicialOpinion(
                judge="Defense",
                criterion_id="test_criterion",
                score=4,
                argument="Generous assessment with sufficient length.",
                cited_evidence=["evidence1"],
            ),
            JudicialOpinion(
                judge="TechLead",
                criterion_id="test_criterion",
                score=3,
                argument="Pragmatic assessment with sufficient length.",
                cited_evidence=["evidence1"],
            ),
        ]

        result = chief.synthesize(sample_agent_state)

        assert "final_scores" in result
        assert "synthesis_summary" in result
        assert "final_report" in result
        assert "test_criterion" in result["final_scores"]

    def test_resolve_criterion_high_variance(self):
        """Test resolution of high-variance opinions."""
        chief = ChiefJustice()

        opinions = [
            JudicialOpinion(
                judge="Prosecutor",
                criterion_id="test",
                score=1,
                argument="Very harsh assessment with sufficient length for validation requirements.",
                cited_evidence=[],
            ),
            JudicialOpinion(
                judge="Defense",
                criterion_id="test",
                score=5,
                argument="Very generous assessment with sufficient length for validation requirements.",
                cited_evidence=[],
            ),
            JudicialOpinion(
                judge="TechLead",
                criterion_id="test",
                score=3,
                argument="Balanced assessment with sufficient length for validation requirements.",
                cited_evidence=[],
            ),
        ]

        score, note = chief._resolve_criterion("test", opinions, {})

        # High variance should default to TechLead
        assert 1 <= score <= 5
        assert "variance" in note.lower()

    def test_resolve_criterion_high_variance_with_severe_prosecutor_caps_score(self):
        """High variance + severe prosecutor concern should apply conservative cap."""
        chief = ChiefJustice()
        opinions = [
            JudicialOpinion(
                judge="Prosecutor",
                criterion_id="test",
                score=1,
                argument="Severe concern with enough details for validation length requirements.",
                cited_evidence=[],
            ),
            JudicialOpinion(
                judge="Defense",
                criterion_id="test",
                score=5,
                argument="Generous claim with enough details for validation length requirements.",
                cited_evidence=[],
            ),
            JudicialOpinion(
                judge="TechLead",
                criterion_id="test",
                score=4,
                argument="Balanced claim with enough details for validation length requirements.",
                cited_evidence=[],
            ),
        ]

        score, note = chief._resolve_criterion("test", opinions, {})
        assert score <= 3
        assert "conservative" in note.lower()

    def test_resolve_criterion_security_override(self):
        """Test security override rule."""
        chief = ChiefJustice()

        opinions = [
            JudicialOpinion(
                judge="Prosecutor",
                criterion_id="test",
                score=1,
                argument="SECURITY vulnerability detected: os.system without validation. Critical flaw.",
                cited_evidence=[],
            ),
            JudicialOpinion(
                judge="Defense",
                criterion_id="test",
                score=5,
                argument="Good effort shown despite issues. Sufficient length for validation.",
                cited_evidence=[],
            ),
            JudicialOpinion(
                judge="TechLead",
                criterion_id="test",
                score=3,
                argument="Functional but has security concerns. Sufficient length here.",
                cited_evidence=[],
            ),
        ]

        synthesis_rules = {
            "security_override": "Security flaws cap score at 3",
        }

        score, note = chief._resolve_criterion("test", opinions, synthesis_rules)

        # Should apply security cap
        assert score <= 3
        assert "security" in note.lower()

    def test_group_opinions(self):
        """Test grouping of opinions by criterion."""
        chief = ChiefJustice()

        opinions = [
            JudicialOpinion(
                judge="Prosecutor",
                criterion_id="criterion1",
                score=2,
                argument="Test argument with sufficient length.",
                cited_evidence=[],
            ),
            JudicialOpinion(
                judge="Defense",
                criterion_id="criterion1",
                score=4,
                argument="Test argument with sufficient length.",
                cited_evidence=[],
            ),
            JudicialOpinion(
                judge="Prosecutor",
                criterion_id="criterion2",
                score=3,
                argument="Test argument with sufficient length.",
                cited_evidence=[],
            ),
        ]

        grouped = chief._group_opinions(opinions)

        assert len(grouped) == 2
        assert len(grouped["criterion1"]) == 2
        assert len(grouped["criterion2"]) == 1
