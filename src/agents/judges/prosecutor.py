"""
Prosecutor: The Critical Lens
Core Philosophy: "Trust No One. Assume Vibe Coding."
"""

import time
from typing import Dict, List

from ...core.state import AgentState, Evidence, JudicialOpinion
from ...utils.exceptions import NodeExecutionError
from ...utils.logger import get_logger
from .base_judge import BaseJudge

logger = get_logger()


class Prosecutor(BaseJudge):
    """
    The Prosecutor judge persona.
    Scrutinizes evidence for gaps, security flaws, and laziness.
    """

    def __init__(self):
        super().__init__(judge_name="Prosecutor")

    def get_system_prompt(self) -> str:
        """Get the prosecutor's system prompt."""
        return """You are the PROSECUTOR in a code quality tribunal.

YOUR CORE PHILOSOPHY: "Trust No One. Assume Vibe Coding."

YOUR ROLE:
- Scrutinize every claim with extreme skepticism
- Look for security vulnerabilities, shortcuts, and laziness
- Assume guilt until proven innocent by overwhelming evidence
- Never give the benefit of the doubt

SCORING PHILOSOPHY:
- Score 1 (Critical Failure): Use this liberally for security issues, missing fundamentals
- Score 2 (Major Issues): For significant gaps even if code "works"
- Score 3 (Barely Passing): Only if technically functional but sloppy
- Score 4-5 (Good/Excellent): Reserve for truly exceptional work with solid evidence

KEY VIOLATIONS TO CHARGE:
- "Security Negligence": Raw os.system(), path traversal, command injection
- "Orchestration Fraud": Linear graphs claiming to be parallel
- "Hallucination Liability": Free-text outputs instead of Pydantic validation
- "Vibe Coding": Buzzwords without implementation

YOUR OUTPUT MUST:
1. Lead with the charge (e.g., "I charge the defendant with Security Negligence")
2. Cite specific evidence that proves guilt
3. Assign harsh but justified scores
4. Provide a list of specific missing elements

Remember: Your job is to protect production systems from bad code.
Be harsh, be specific, be right."""

    def evaluate_all_criteria(
        self,
        rubric: Dict,
        evidences: Dict[str, List[Evidence]],
    ) -> List[JudicialOpinion]:
        """
        Evaluate all rubric criteria from prosecutor perspective.

        Args:
            rubric: Complete rubric configuration
            evidences: All evidence from detectives

        Returns:
            List of JudicialOpinion objects
        """
        logger.info("Prosecutor beginning evaluation of all criteria")

        opinions = []
        dimensions = (
            rubric.dimensions if hasattr(rubric, "dimensions") else rubric["dimensions"]
        )

        for dimension in dimensions:
            opinion = self.render_opinion(dimension, evidences)
            opinions.append(opinion)

        logger.info(f"Prosecutor completed {len(opinions)} evaluations")
        return opinions


# Node function for LangGraph
def prosecutor_node(state: AgentState) -> Dict:
    """
    LangGraph node wrapper for Prosecutor.

    Args:
        state: Current graph state

    Returns:
        State updates
    """
    logger.log_node_start("Prosecutor")
    start_time = time.time()

    try:
        prosecutor = Prosecutor()

        # Get evidences and rubric from state
        evidences = state.get("evidences", {})
        rubric = state["rubric"]

        # Evaluate all criteria
        opinions = prosecutor.evaluate_all_criteria(rubric, evidences)

        duration = time.time() - start_time
        logger.log_node_complete("Prosecutor", duration)

        return {
            "opinions": opinions,
        }

    except Exception as e:
        duration = time.time() - start_time
        logger.log_node_error("Prosecutor", e)
        raise NodeExecutionError("Prosecutor", e)
