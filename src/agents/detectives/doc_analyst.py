"""
DocAnalyst: The Paperwork Detective
Analyzes PDF reports for theoretical depth and cross-references claims.
"""

import time
from pathlib import Path
from typing import Dict, List

from ...core.state import AgentState, Evidence
from ...tools import PDFAnalyzer
from ...utils.exceptions import NodeExecutionError
from ...utils.logger import get_logger

logger = get_logger()


class DocAnalyst:
    """
    Detective agent that analyzes documentation.
    Validates claims against code evidence.
    """

    def __init__(self):
        self.pdf_analyzer = None  # Initialized per-investigation with correct base_dir

    def investigate(self, state: AgentState) -> Dict:
        """
        Execute forensic analysis of the PDF report.

        Args:
            state: Current graph state

        Returns:
            Dictionary with evidences key containing collected evidence
        """
        logger.log_node_start("DocAnalyst")
        start_time = time.time()

        try:
            pdf_path = state["pdf_path"]
            logger.set_context(pdf_path=pdf_path)

            # Convert to Path object
            pdf_file = Path(pdf_path)

            # Initialize PDF analyzer with base directory
            base_dir = pdf_file.parent if pdf_file.parent.exists() else Path.cwd()
            self.pdf_analyzer = PDFAnalyzer(base_dir)

            # Collect evidence from PDF
            evidence_list: List[Evidence] = []

            logger.info("Analyzing PDF document structure and content")
            pdf_evidences = self.pdf_analyzer.analyze_pdf(pdf_file)
            evidence_list.extend(pdf_evidences.values())

            for key, evidence in pdf_evidences.items():
                logger.log_evidence_found(key, evidence.confidence)

            # Cross-reference with RepoInvestigator findings
            if "evidences" in state and "RepoInvestigator" in state["evidences"]:
                logger.info("Cross-referencing PDF claims with code evidence")
                cross_ref_evidences = self._cross_reference_claims(state, pdf_file)
                evidence_list.extend(cross_ref_evidences)

            duration = time.time() - start_time
            logger.log_node_complete("DocAnalyst", duration)
            logger.clear_context()

            return {
                "evidences": {
                    "DocAnalyst": evidence_list,
                }
            }

        except Exception as e:
            duration = time.time() - start_time
            logger.log_node_error("DocAnalyst", e)
            logger.clear_context()

            raise NodeExecutionError("DocAnalyst", e)

    def _cross_reference_claims(self, state: AgentState, pdf_file: Path) -> List[Evidence]:
        """
        Cross-reference claims in PDF against actual code artifacts.

        Args:
            state: Current graph state with RepoInvestigator evidence
            pdf_file: Path to PDF file

        Returns:
            List of Evidence objects about claim verification
        """
        evidences: List[Evidence] = []

        try:
            # Extract text from PDF for analysis
            pdf_text = self.pdf_analyzer._extract_text(pdf_file)

            # Get verified files from RepoInvestigator
            repo_evidences = state["evidences"]["RepoInvestigator"]

            # Extract files that were found
            verified_files = []
            for evidence in repo_evidences:
                if evidence.found and evidence.location:
                    # Extract file path from location
                    location = evidence.location
                    if "/" in location or "\\" in location:
                        verified_files.append(location)

            # Perform cross-reference
            cross_ref = self.pdf_analyzer.cross_reference_claims(pdf_text, verified_files)
            evidences.extend(cross_ref.values())

            # Log results
            if "hallucinated_claims" in cross_ref:
                hallucination_evidence = cross_ref["hallucinated_claims"]
                if hallucination_evidence.found:
                    logger.warning(
                        f"HALLUCINATION DETECTED: {hallucination_evidence.content}"
                    )
                else:
                    logger.info("All PDF claims verified against code artifacts")

        except Exception as e:
            logger.warning(f"Cross-reference analysis failed: {e}")
            evidences.append(
                Evidence(
                    found=False,
                    content=f"Cross-reference failed: {str(e)}",
                    location=str(pdf_file),
                    confidence=0.3,
                    detective_name="DocAnalyst",
                )
            )

        return evidences


# Node function for LangGraph
def doc_analyst_node(state: AgentState) -> Dict:
    """
    LangGraph node wrapper for DocAnalyst.

    Args:
        state: Current graph state

    Returns:
        State updates
    """
    analyst = DocAnalyst()
    return analyst.investigate(state)
