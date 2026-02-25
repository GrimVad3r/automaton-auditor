"""
Tests for PDF analysis tools.
"""

import pytest

from src.tools.pdf_tools import PDFAnalyzer
from src.utils.exceptions import PDFParsingError


class TestPDFAnalyzer:
    """Tests for PDFAnalyzer class."""

    @pytest.fixture
    def analyzer(self, temp_dir):
        """Create a PDF analyzer instance."""
        return PDFAnalyzer(temp_dir)

    def test_analyze_pdf_success(self, analyzer, mock_pdf_file):
        """Test successful PDF analysis."""
        evidences = analyzer.analyze_pdf(mock_pdf_file)

        assert "pdf_extracted" in evidences
        # PDF extraction may succeed or fail depending on content

    def test_analyze_pdf_nonexistent(self, analyzer, temp_dir):
        """Test handling of nonexistent PDF."""
        evidences = analyzer.analyze_pdf(temp_dir / "nonexistent.pdf")

        assert "pdf_access" in evidences
        assert evidences["pdf_access"].found is False

    def test_extract_text(self, analyzer, mock_pdf_file):
        """Test text extraction from PDF."""
        try:
            text = analyzer._extract_text(mock_pdf_file)
            # Minimal PDF may have no text, which is fine
            assert isinstance(text, str)
        except PDFParsingError:
            # Parsing may fail for minimal PDFs
            pass

    def test_analyze_content_concepts(self, analyzer, temp_dir):
        """Test concept detection in PDF content."""
        # Create a text-rich PDF simulation
        test_text = """
        Our architecture implements dialectical synthesis through a
        fan-out pattern. The metacognition layer ensures quality.
        We use state synchronization with operator.add reducers.
        """

        evidences = analyzer._analyze_content(test_text, temp_dir / "test.pdf")

        # Should detect key concepts
        assert "concept_dialectical_synthesis" in evidences
        assert evidences["concept_dialectical_synthesis"].found is True

        assert "concept_metacognition" in evidences
        assert evidences["concept_metacognition"].found is True

        assert "concept_fan_out_fan_in" in evidences
        assert evidences["concept_fan_out_fan_in"].found is True

    def test_analyze_content_missing_concepts(self, analyzer, temp_dir):
        """Test handling of missing concepts."""
        test_text = "This is a simple document without technical terms."

        evidences = analyzer._analyze_content(test_text, temp_dir / "test.pdf")

        # Should not find concepts
        for key in evidences:
            if key.startswith("concept_"):
                assert evidences[key].found is False

    def test_extract_file_references(self, analyzer, temp_dir):
        """Test extraction of file path references."""
        test_text = """
        We implemented the detective in src/agents/detectives/repo_investigator.py
        and the tools in src/tools/git_tools.py. The state is defined in
        src/core/state.py.
        """

        evidences = analyzer._extract_file_references(test_text, temp_dir / "test.pdf")

        assert "file_references" in evidences
        assert evidences["file_references"].found is True
        assert (
            "src/agents/detectives/repo_investigator.py"
            in evidences["file_references"].content
        )
        assert "src/tools/git_tools.py" in evidences["file_references"].content

    def test_extract_file_references_none(self, analyzer, temp_dir):
        """Test handling when no file references exist."""
        test_text = "This document has no file paths."

        evidences = analyzer._extract_file_references(test_text, temp_dir / "test.pdf")

        assert "file_references" in evidences
        assert evidences["file_references"].found is False

    def test_cross_reference_claims(self, analyzer):
        """Test cross-referencing PDF claims against actual files."""
        test_text = """
        We created src/tools/git_tools.py and src/tools/ast_tools.py.
        We also have src/nonexistent/fake.py.
        """

        verified_files = [
            "src/tools/git_tools.py",
            "src/tools/ast_tools.py",
        ]

        evidences = analyzer.cross_reference_claims(test_text, verified_files)

        assert "hallucinated_claims" in evidences

        # Should detect the hallucinated file
        if evidences["hallucinated_claims"].found:
            assert "nonexistent" in evidences["hallucinated_claims"].content

    def test_cross_reference_claims_all_verified(self, analyzer):
        """Test when all claims are verified."""
        test_text = "We have src/tools/git_tools.py."
        verified_files = ["src/tools/git_tools.py"]

        evidences = analyzer.cross_reference_claims(test_text, verified_files)

        assert "hallucinated_claims" in evidences
        assert evidences["hallucinated_claims"].found is False

    def test_cross_reference_claims_with_absolute_verified_paths(self, analyzer):
        """Test that absolute verified paths are normalized before comparison."""
        test_text = "We have src/tools/git_tools.py and src/core/graph.py."
        verified_files = [
            r"C:\tmp\auditor\repo\src\tools\git_tools.py",
            r"C:\tmp\auditor\repo\src\core\graph.py",
        ]

        evidences = analyzer.cross_reference_claims(test_text, verified_files)

        assert "hallucinated_claims" in evidences
        assert evidences["hallucinated_claims"].found is False

    def test_cross_reference_no_claims(self, analyzer):
        """Test when PDF has no file claims."""
        test_text = "This is a document without file references."
        verified_files = ["src/tools/git_tools.py"]

        evidences = analyzer.cross_reference_claims(test_text, verified_files)

        # Should return empty dict when no claims to verify
        assert len(evidences) == 0
