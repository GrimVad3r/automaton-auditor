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
