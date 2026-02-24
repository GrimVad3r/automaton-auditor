"""
Tests for Pydantic state models.
"""

import pytest
from pydantic import ValidationError

from src.core.state import (
    Evidence,
    JudicialOpinion,
    RubricDimension,
    RubricConfig,
    NodeOutput,
    DetectiveOutput,
    JudgeOutput,
)


class TestEvidence:
    """Tests for Evidence model."""

    def test_valid_evidence(self):
        """Test creation of valid evidence."""
        evidence = Evidence(
            found=True,
            content="Test content",
            location="test.py:10",
            confidence=0.95,
            detective_name="TestDetective",
        )

        assert evidence.found is True
        assert evidence.content == "Test content"
        assert evidence.confidence == 0.95

    def test_confidence_bounds(self):
        """Test confidence value validation."""
        # Valid confidence
        evidence = Evidence(
            found=True,
            location="test.py",
            confidence=1.0,
            detective_name="TestDetective",
        )
        assert evidence.confidence == 1.0

        # Invalid confidence (too high)
        with pytest.raises(ValidationError):
            Evidence(
                found=True,
                location="test.py",
                confidence=1.1,
                detective_name="TestDetective",
            )

        # Invalid confidence (negative)
        with pytest.raises(ValidationError):
            Evidence(
                found=True,
                location="test.py",
                confidence=-0.1,
                detective_name="TestDetective",
            )

    def test_optional_fields(self):
        """Test that optional fields can be omitted."""
        evidence = Evidence(
            found=False,
            location="test.py",
            confidence=0.5,
            detective_name="TestDetective",
        )

        assert evidence.content is None
        assert evidence.timestamp is None

    def test_evidence_serialization(self):
        """Test JSON serialization."""
        evidence = Evidence(
            found=True,
            content="Test",
            location="test.py",
            confidence=0.9,
            detective_name="TestDetective",
        )

        json_data = evidence.model_dump()
        assert json_data["found"] is True
        assert json_data["confidence"] == 0.9


class TestJudicialOpinion:
    """Tests for JudicialOpinion model."""

    def test_valid_opinion(self):
        """Test creation of valid opinion."""
        opinion = JudicialOpinion(
            judge="Prosecutor",
            criterion_id="test_criterion",
            score=3,
            argument="This is a valid argument with sufficient length to pass validation requirements.",
            cited_evidence=["evidence1", "evidence2"],
        )

        assert opinion.judge == "Prosecutor"
        assert opinion.score == 3
        assert len(opinion.cited_evidence) == 2

    def test_judge_literal_validation(self):
        """Test that only valid judge names are accepted."""
        # Valid judges
        for judge in ["Prosecutor", "Defense", "TechLead"]:
            opinion = JudicialOpinion(
                judge=judge,
                criterion_id="test",
                score=3,
                argument="Valid argument with enough length.",
                cited_evidence=[],
            )
            assert opinion.judge == judge

        # Invalid judge
        with pytest.raises(ValidationError):
            JudicialOpinion(
                judge="InvalidJudge",
                criterion_id="test",
                score=3,
                argument="Argument",
                cited_evidence=[],
            )

    def test_score_bounds(self):
        """Test score validation."""
        # Valid scores
        for score in range(1, 6):
            opinion = JudicialOpinion(
                judge="Prosecutor",
                criterion_id="test",
                score=score,
                argument="Valid argument with enough length.",
                cited_evidence=[],
            )
            assert opinion.score == score

        # Invalid scores
        with pytest.raises(ValidationError):
            JudicialOpinion(
                judge="Prosecutor",
                criterion_id="test",
                score=0,
                argument="Argument",
                cited_evidence=[],
            )

        with pytest.raises(ValidationError):
            JudicialOpinion(
                judge="Prosecutor",
                criterion_id="test",
                score=6,
                argument="Argument",
                cited_evidence=[],
            )


class TestRubricConfig:
    """Tests for RubricConfig model."""

    def test_valid_rubric(self, sample_rubric):
        """Test creation of valid rubric config."""
        rubric = RubricConfig(**sample_rubric)

        assert rubric.rubric_metadata["rubric_name"] == "Test Rubric"
        assert len(rubric.dimensions) == 1
        assert rubric.dimensions[0].id == "test_criterion"

    def test_rubric_dimension_validation(self):
        """Test validation of rubric dimensions."""
        dimension = RubricDimension(
            id="test_id",
            name="Test Dimension",
            target_artifact="github_repo",
            forensic_instruction="Test instruction",
            judicial_logic={
                "prosecutor": "Harsh",
                "defense": "Generous",
                "tech_lead": "Pragmatic",
            },
        )

        assert dimension.target_artifact == "github_repo"

        # Invalid target_artifact
        with pytest.raises(ValidationError):
            RubricDimension(
                id="test_id",
                name="Test",
                target_artifact="invalid",
                forensic_instruction="Test",
                judicial_logic={},
            )


class TestNodeOutput:
    """Tests for NodeOutput model."""

    def test_successful_output(self):
        """Test creation of successful node output."""
        output = NodeOutput(
            success=True,
            data={"key": "value"},
            duration=1.5,
        )

        assert output.success is True
        assert output.data["key"] == "value"
        assert output.error is None

    def test_error_output(self):
        """Test creation of error node output."""
        output = NodeOutput(
            success=False,
            error="Something went wrong",
            duration=0.5,
        )

        assert output.success is False
        assert output.error == "Something went wrong"
        assert output.data is None


class TestDetectiveOutput:
    """Tests for DetectiveOutput model."""

    def test_successful_detective_output(self, sample_evidence):
        """Test creation of successful detective output."""
        output = DetectiveOutput(
            detective_name="RepoInvestigator",
            evidence_list=[sample_evidence],
            execution_time=2.5,
            success=True,
        )

        assert output.success is True
        assert len(output.evidence_list) == 1
        assert output.error is None

    def test_failed_detective_output(self):
        """Test creation of failed detective output."""
        output = DetectiveOutput(
            detective_name="RepoInvestigator",
            evidence_list=[],
            execution_time=0.5,
            success=False,
            error="Clone failed",
        )

        assert output.success is False
        assert output.error == "Clone failed"


class TestJudgeOutput:
    """Tests for JudgeOutput model."""

    def test_successful_judge_output(self, sample_opinion):
        """Test creation of successful judge output."""
        output = JudgeOutput(
            judge_name="Prosecutor",
            opinions=[sample_opinion],
            execution_time=3.5,
            success=True,
        )

        assert output.success is True
        assert len(output.opinions) == 1
        assert output.error is None
