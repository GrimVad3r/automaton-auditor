"""
Tech Lead: The Pragmatic Lens
Core Philosophy: "Does it actually work? Is it maintainable?"
"""

import time
from typing import Dict, List

from ...core.state import AgentState, Evidence, JudicialOpinion
from ...utils.exceptions import NodeExecutionError
from ...utils.logger import get_logger
from .base_judge import BaseJudge

logger = get_logger()


class TechLead(BaseJudge):
    """
    The Tech Lead judge persona.
    Evaluates architectural soundness, code cleanliness, and practical viability.
    """

    def __init__(self):
        super().__init__(judge_name="TechLead")

    def get_system_prompt(self) -> str:
        """Get the tech lead's system prompt."""
        return """You are the TECH LEAD in a code quality tribunal.

YOUR CORE PHILOSOPHY: "Does it actually work? Is it maintainable?"

YOUR ROLE:
- Evaluate architectural soundness and practical viability
- Ignore the "vibe" and focus on the artifacts
- Assess technical debt and long-term maintainability
- Be the pragmatic tie-breaker between Prosecutor and Defense

SCORING PHILOSOPHY:
- Score 5 (Production Ready): Clean, maintainable, follows best practices
- Score 4 (Needs Polish): Works well, minor refactoring needed
- Score 3 (Technical Debt): Functional but creates maintenance burden
- Score 2 (Brittle): Works but will break easily, needs significant rework
- Score 1 (Broken): Doesn't work or creates critical technical debt

KEY EVALUATION CRITERIA:
- "Architectural Soundness": Is the design modular and extensible?
- "State Management": Are reducers used correctly? Data loss risks?
- "Error Handling": Are failures gracefully handled?
- "Code Quality": Is it readable and maintainable?
- "Security Posture": Are tools properly sandboxed?

YOUR OUTPUT MUST:
1. Focus on technical facts, not effort or intent
2. Assess whether code would pass a production code review
3. Identify specific technical debt items
4. Provide actionable remediation advice
5. Be realistic - neither overly harsh nor overly lenient

DECISION FRAMEWORK:
- If Prosecutor says 1 (security flaw) and Defense says 5 (great effort):
  → You assess the actual technical risk (likely 1-2)
- If Defense says 5 (deep thinking) but code doesn't compile:
  → You assess functional completeness (likely 2-3)
- If Prosecutor says 1 (linear) but state management is solid:
  → You assess overall architecture (likely 3)

Remember: Your job is to ensure code quality without blocking innovation.
Be fair, be technical, be practical."""

    def evaluate_all_criteria(
        self,
        rubric: Dict,
        evidences: Dict[str, List[Evidence]],
    ) -> List[JudicialOpinion]:
        """
        Evaluate all rubric criteria from tech lead perspective.

        Args:
            rubric: Complete rubric configuration
            evidences: All evidence from detectives

        Returns:
            List of JudicialOpinion objects
        """
        logger.info("Tech Lead beginning evaluation of all criteria")

        opinions = []

        for dimension in rubric["dimensions"]:
            opinion = self.render_opinion(dimension, evidences)
            opinions.append(opinion)

        logger.info(f"Tech Lead completed {len(opinions)} evaluations")
        return opinions


# Node function for LangGraph
def tech_lead_node(state: AgentState) -> Dict:
    """
    LangGraph node wrapper for Tech Lead.

    Args:
        state: Current graph state

    Returns:
        State updates
    """
    logger.log_node_start("TechLead")
    start_time = time.time()

    try:
        tech_lead = TechLead()

        # Get evidences and rubric from state
        evidences = state.get("evidences", {})
        rubric = state["rubric"]

        # Evaluate all criteria
        opinions = tech_lead.evaluate_all_criteria(rubric, evidences)

        duration = time.time() - start_time
        logger.log_node_complete("TechLead", duration)

        return {
            "opinions": opinions,
        }

    except Exception as e:
        duration = time.time() - start_time
        logger.log_node_error("TechLead", e)
        raise NodeExecutionError("TechLead", e)
