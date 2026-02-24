"""
Defense Attorney: The Optimistic Lens
Core Philosophy: "Reward Effort and Intent. Look for the 'Spirit of the Law'."
"""

import time
from typing import Dict, List

from ...core.state import AgentState, Evidence, JudicialOpinion
from ...utils.exceptions import NodeExecutionError
from ...utils.logger import get_logger
from .base_judge import BaseJudge

logger = get_logger()


class Defense(BaseJudge):
    """
    The Defense Attorney judge persona.
    Highlights creative workarounds, deep thought, and effort.
    """

    def __init__(self):
        super().__init__(judge_name="Defense")

    def get_system_prompt(self) -> str:
        """Get the defense attorney's system prompt."""
        return """You are the DEFENSE ATTORNEY in a code quality tribunal.

YOUR CORE PHILOSOPHY: "Reward Effort and Intent. Look for the 'Spirit of the Law'."

YOUR ROLE:
- Highlight creative workarounds and innovative thinking
- Recognize effort and learning, even if execution is imperfect
- Look at the git history - struggle and iteration show genuine engineering
- Champion the developer's intent and vision

SCORING PHILOSOPHY:
- Score 5 (Excellent): For deep understanding even with minor bugs
- Score 4 (Good): When intent is clear and approach is sound
- Score 3 (Acceptable): If the core ideas are present
- Score 2 (Needs Work): Only for fundamental misunderstandings
- Score 1 (Critical): Reserve for complete absence of effort

KEY STRENGTHS TO HIGHLIGHT:
- "Master Thinker Profile": Deep architectural understanding despite bugs
- "Engineering Process": Git history shows iterative refinement
- "Creative Solutions": Novel approaches to difficult problems
- "Spirit of Compliance": Meets the intent even if not the letter

YOUR OUTPUT MUST:
1. Start with what the developer got RIGHT
2. Acknowledge the difficulty of the task
3. Highlight evidence of deep thinking or effort
4. Argue for a generous interpretation of the rubric
5. Provide encouragement while being honest about gaps

Remember: Your job is to recognize genuine effort and protect good intentions
from being crushed by perfectionism. Be generous, be encouraging, be fair."""

    def evaluate_all_criteria(
        self,
        rubric: Dict,
        evidences: Dict[str, List[Evidence]],
    ) -> List[JudicialOpinion]:
        """
        Evaluate all rubric criteria from defense perspective.

        Args:
            rubric: Complete rubric configuration
            evidences: All evidence from detectives

        Returns:
            List of JudicialOpinion objects
        """
        logger.info("Defense Attorney beginning evaluation of all criteria")

        opinions = []
        dimensions = (
            rubric.dimensions if hasattr(rubric, "dimensions") else rubric["dimensions"]
        )

        for dimension in dimensions:
            opinion = self.render_opinion(dimension, evidences)
            opinions.append(opinion)

        logger.info(f"Defense Attorney completed {len(opinions)} evaluations")
        return opinions


# Node function for LangGraph
def defense_node(state: AgentState) -> Dict:
    """
    LangGraph node wrapper for Defense Attorney.

    Args:
        state: Current graph state

    Returns:
        State updates
    """
    logger.log_node_start("Defense")
    start_time = time.time()

    try:
        defense = Defense()

        # Get evidences and rubric from state
        evidences = state.get("evidences", {})
        rubric = state["rubric"]

        # Evaluate all criteria
        opinions = defense.evaluate_all_criteria(rubric, evidences)

        duration = time.time() - start_time
        logger.log_node_complete("Defense", duration)

        return {
            "opinions": opinions,
        }

    except Exception as e:
        duration = time.time() - start_time
        logger.log_node_error("Defense", e)
        raise NodeExecutionError("Defense", e)
