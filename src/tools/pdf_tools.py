"""
PDF document analysis tools.
Extracts text and images for forensic analysis.
"""

import warnings
from pathlib import Path
from typing import Dict, List, Optional

try:
    from pypdf import PdfReader
except ImportError:  # pragma: no cover - compatibility fallback
    # PyPDF2 emits a deprecation warning at import-time.
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            category=DeprecationWarning,
            message="PyPDF2 is deprecated.*",
        )
        from PyPDF2 import PdfReader  # type: ignore[import-not-found,no-redef]

from ..core.state import Evidence
from ..utils.exceptions import PDFParsingError
from ..utils.logger import get_logger
from ..utils.validators import SecurityValidator

logger = get_logger()


class PDFAnalyzer:
    """
    Analyze PDF documents for evidence.
    Extracts text and validates claims against code artifacts.
    """

    def __init__(self, base_dir: Path):
        """
        Initialize PDF analyzer.

        Args:
            base_dir: Base directory for security validation
        """
        self.base_dir = base_dir

    def analyze_pdf(self, pdf_path: Path) -> Dict[str, Evidence]:
        """
        Extract and analyze PDF content.

        Args:
            pdf_path: Path to PDF file

        Returns:
            Dictionary of evidence from the PDF
        """
        evidences: Dict[str, Evidence] = {}

        # Validate file path
        try:
            validated_path = SecurityValidator.validate_file_path(
                str(pdf_path), self.base_dir
            )
            SecurityValidator.validate_file_size(validated_path)
        except Exception as e:
            logger.error(f"PDF validation failed: {e}")
            evidences["pdf_access"] = Evidence(
                found=False,
                content=f"Validation failed: {e}",
                location=str(pdf_path),
                confidence=1.0,
                detective_name="PDFAnalyzer",
            )
            return evidences

        # Extract text
        try:
            text_content = self._extract_text(validated_path)

            evidences["pdf_extracted"] = Evidence(
                found=True,
                content=f"Extracted {len(text_content)} characters",
                location=str(pdf_path),
                confidence=0.95,
                detective_name="PDFAnalyzer",
            )

            # Analyze content for key concepts
            evidences.update(self._analyze_content(text_content, pdf_path))

            # Extract file references
            evidences.update(self._extract_file_references(text_content, pdf_path))

        except PDFParsingError as e:
            logger.error(f"PDF parsing failed: {e}")
            evidences["pdf_parsing"] = Evidence(
                found=False,
                content=f"Parsing failed: {e}",
                location=str(pdf_path),
                confidence=1.0,
                detective_name="PDFAnalyzer",
            )

        return evidences

    def _extract_text(self, pdf_path: Path) -> str:
        """
        Extract text content from PDF.

        Args:
            pdf_path: Path to PDF file

        Returns:
            Extracted text

        Raises:
            PDFParsingError: If extraction fails
        """
        try:
            with open(pdf_path, "rb") as f:
                reader = PdfReader(f)
                text_parts: List[str] = []

                for page_num, page in enumerate(reader.pages):
                    try:
                        page_text = page.extract_text()
                        text_parts.append(page_text)
                    except Exception as e:
                        logger.warning(
                            f"Failed to extract text from page {page_num}: {e}"
                        )
                        continue

                full_text = "\n".join(text_parts)
                logger.info(f"Extracted {len(full_text)} characters from PDF")
                return full_text

        except Exception as e:
            raise PDFParsingError(f"Failed to extract text from PDF: {e}")

    def _analyze_content(self, text: str, pdf_path: Path) -> Dict[str, Evidence]:
        """
        Analyze PDF content for key concepts.

        Args:
            text: Extracted PDF text
            pdf_path: Path to PDF

        Returns:
            Dictionary of evidence about content
        """
        evidences: Dict[str, Evidence] = {}

        # Define key concepts to search for
        key_concepts = {
            "dialectical_synthesis": [
                "dialectical synthesis",
                "thesis",
                "antithesis",
                "synthesis",
            ],
            "metacognition": [
                "metacognition",
                "thinking about thinking",
                "meta-cognitive",
                "feedback loop",
                "reflection",
                "bidirectional learning",
                "self-audit",
            ],
            "fan_out_fan_in": [
                "fan-out",
                "fan-in",
                "parallel execution",
                "parallelism",
                "parallel judges",
            ],
            "state_synchronization": [
                "state synchronization",
                "state reducer",
                "operator.add",
                "operator.ior",
                "aggregate_evidence",
                "handle_error",
                "chief_justice",
            ],
        }

        for concept_id, search_terms in key_concepts.items():
            matches = []
            for term in search_terms:
                if term.lower() in text.lower():
                    # Extract context around the match
                    idx = text.lower().find(term.lower())
                    context_start = max(0, idx - 100)
                    context_end = min(len(text), idx + 100)
                    context = text[context_start:context_end].replace("\n", " ")
                    matches.append(f"'{term}': ...{context}...")

            if matches:
                evidences[f"concept_{concept_id}"] = Evidence(
                    found=True,
                    content=f"Found {len(matches)} mentions: {matches[0]}",
                    location=str(pdf_path),
                    confidence=0.8,
                    detective_name="PDFAnalyzer",
                )
            else:
                evidences[f"concept_{concept_id}"] = Evidence(
                    found=False,
                    content="Concept not mentioned in document",
                    location=str(pdf_path),
                    confidence=0.6,
                    detective_name="PDFAnalyzer",
                )

        return evidences

    def _extract_file_references(
        self, text: str, pdf_path: Path
    ) -> Dict[str, Evidence]:
        """
        Extract file path references from PDF.

        Args:
            text: Extracted PDF text
            pdf_path: Path to PDF

        Returns:
            Evidence about file references
        """
        import re

        # Match project file paths with extensions (avoid directory-only claims).
        file_pattern = (
            r"(?:src|lib|app|tools|agents)/[A-Za-z0-9_./-]*\.[A-Za-z0-9]{1,10}"
        )

        matches = re.findall(file_pattern, text)

        if matches:
            # Remove duplicates and sort
            unique_files = sorted(set(matches))

            return {
                "file_references": Evidence(
                    found=True,
                    content=f"File references: {', '.join(unique_files[:10])}",
                    location=str(pdf_path),
                    confidence=0.9,
                    detective_name="PDFAnalyzer",
                )
            }

        return {
            "file_references": Evidence(
                found=False,
                content="No file references found",
                location=str(pdf_path),
                confidence=0.5,
                detective_name="PDFAnalyzer",
            )
        }

    def cross_reference_claims(
        self, text: str, verified_files: List[str]
    ) -> Dict[str, Evidence]:
        """
        Cross-reference claims in PDF against actual files.

        Args:
            text: PDF text content
            verified_files: List of files that actually exist

        Returns:
            Evidence about claim accuracy
        """
        import re

        evidences: Dict[str, Evidence] = {}

        def normalize_path(value: str) -> str:
            normalized = value.rstrip(".,;:!?)\"'").replace("\\", "/")
            return normalized

        def to_project_relative_path(value: str) -> Optional[str]:
            """
            Convert absolute/heterogeneous locations into project-relative paths
            like `src/core/graph.py` for fair claim verification.
            """
            normalized = normalize_path(value)
            match = re.search(
                r"(?:^|/)((?:src|lib|app|tools|agents)/[\w/.-]+)", normalized
            )
            if match:
                return match.group(1)
            return None

        # Only verify concrete file claims, not directory mentions.
        file_pattern = (
            r"(?:src|lib|app|tools|agents)/[A-Za-z0-9_./-]*\.[A-Za-z0-9]{1,10}"
        )
        claimed_files = {
            normalize_path(match) for match in re.findall(file_pattern, text)
        }

        if not claimed_files:
            return evidences

        # Check which claims are verified
        verified_set = set()
        for path in verified_files:
            relative = to_project_relative_path(path)
            if relative:
                verified_set.add(relative)

        hallucinated = claimed_files - verified_set

        if hallucinated:
            evidences["hallucinated_claims"] = Evidence(
                found=True,
                content=f"Hallucinated files: {', '.join(sorted(hallucinated))}",
                location="PDF Report",
                confidence=0.95,
                detective_name="PDFAnalyzer",
            )
        else:
            evidences["hallucinated_claims"] = Evidence(
                found=False,
                content="All file references verified",
                location="PDF Report",
                confidence=0.9,
                detective_name="PDFAnalyzer",
            )

        return evidences
