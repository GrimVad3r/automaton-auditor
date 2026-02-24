"""
Chief Justice: The Synthesis Engine
Resolves dialectical conflicts and renders final verdicts.
"""

import time
from collections import defaultdict
from typing import Dict, List, Tuple

from ...core.state import AgentState, JudicialOpinion
from ...utils.exceptions import NodeExecutionError
from ...utils.formatters import MarkdownReportFormatter
from ...utils.logger import get_logger

logger = get_logger()


class ChiefJustice:
    """
    The Supreme Court synthesis engine.
    Applies deterministic rules to resolve judge conflicts.
    """

    def synthesize(self, state: AgentState) -> Dict:
        """
        Synthesize final verdicts from judicial opinions.

        Args:
            state: Current graph state with all opinions

        Returns:
            Dictionary with final scores and report
        """
        opinions = state.get("opinions", [])
        evidences = state.get("evidences", {})
        rubric = state["rubric"]

        logger.info(f"Synthesizing {len(opinions)} judicial opinions")

        # Group opinions by criterion
        opinions_by_criterion = self._group_opinions(opinions)

        # Apply synthesis rules
        final_scores = {}
        synthesis_notes = []

        for criterion_id, criterion_opinions in opinions_by_criterion.items():
            score, note = self._resolve_criterion(
                criterion_id, criterion_opinions, rubric["synthesis_rules"]
            )
            final_scores[criterion_id] = score
            synthesis_notes.append(note)

        # Generate synthesis summary
        synthesis_summary = self._generate_summary(synthesis_notes, final_scores)

        # Generate full report
        execution_time = (
            state.get("execution_end_time", time.time())
            - state.get("execution_start_time", 0)
        )

        report = MarkdownReportFormatter.format_full_report(
            repo_url=state["repo_url"],
            pdf_path=state["pdf_path"],
            evidences=evidences,
            opinions=opinions,
            final_scores=final_scores,
            synthesis_summary=synthesis_summary,
            execution_time=execution_time,
        )

        logger.info(f"Synthesis complete. Final scores: {final_scores}")

        return {
            "final_scores": final_scores,
            "synthesis_summary": synthesis_summary,
            "final_report": report,
        }

    def _group_opinions(
        self, opinions: List[JudicialOpinion]
    ) -> Dict[str, List[JudicialOpinion]]:
        """Group opinions by criterion ID."""
        grouped: Dict[str, List[JudicialOpinion]] = defaultdict(list)

        for opinion in opinions:
            grouped[opinion.criterion_id].append(opinion)

        return dict(grouped)

    def _resolve_criterion(
        self,
        criterion_id: str,
        opinions: List[JudicialOpinion],
        synthesis_rules: Dict[str, str],
    ) -> Tuple[int, str]:
        """
        Resolve conflicting opinions for a single criterion.

        Args:
            criterion_id: The criterion being evaluated
            opinions: All opinions for this criterion
            synthesis_rules: Global synthesis rules from rubric

        Returns:
            Tuple of (final_score, synthesis_note)
        """
        if not opinions:
            return 3, f"{criterion_id}: No opinions provided (defaulting to 3)"

        # Extract scores from each judge
        prosecutor_score = next((o.score for o in opinions if o.judge == "Prosecutor"), 3)
        defense_score = next((o.score for o in opinions if o.judge == "Defense"), 3)
        tech_lead_score = next((o.score for o in opinions if o.judge == "TechLead"), 3)

        logger.debug(
            f"{criterion_id} scores - Prosecutor: {prosecutor_score}, "
            f"Defense: {defense_score}, TechLead: {tech_lead_score}"
        )

        # Apply Rule of Security (from synthesis_rules)
        if prosecutor_score == 1:
            prosecutor_opinion = next(o for o in opinions if o.judge == "Prosecutor")
            if "security" in prosecutor_opinion.argument.lower():
                logger.warning(f"Security override applied for {criterion_id}")
                return (
                    min(prosecutor_score + 2, 3),
                    f"{criterion_id}: Security flaw detected by Prosecutor. "
                    f"Score capped at 3 per synthesis rules.",
                )

        # Calculate variance
        scores = [prosecutor_score, defense_score, tech_lead_score]
        variance = max(scores) - min(scores)

        # Rule: High variance (>2) triggers re-evaluation logic
        if variance > 2:
            # Apply Rule of Functionality: Tech Lead carries highest weight
            final_score = tech_lead_score
            note = (
                f"{criterion_id}: High variance detected ({min(scores)}-{max(scores)}). "
                f"Tech Lead opinion (score: {tech_lead_score}) carries decisive weight "
                f"due to pragmatic focus."
            )
        else:
            # Moderate variance: weighted average with Tech Lead emphasis
            final_score = int(
                round(
                    (prosecutor_score * 0.25 + defense_score * 0.25 + tech_lead_score * 0.5)
                )
            )
            note = (
                f"{criterion_id}: Moderate agreement. "
                f"Weighted synthesis (TechLead 50%, others 25% each) = {final_score}"
            )

        # Ensure score is in valid range
        final_score = max(1, min(5, final_score))

        return final_score, note

    def _generate_summary(self, synthesis_notes: List[str], final_scores: Dict[str, int]) -> str:
        """Generate executive summary of the synthesis process."""
        total_score = sum(final_scores.values())
        max_score = len(final_scores) * 5
        percentage = (total_score / max_score * 100) if max_score > 0 else 0

        summary = f"""
## Synthesis Summary

The Chief Justice has reviewed all evidence and judicial opinions to render final verdicts.

**Overall Assessment:** {total_score}/{max_score} ({percentage:.1f}%)

### Synthesis Process

The following principles guided the final verdicts:

1. **Rule of Security:** Confirmed security flaws cap scores at 3
2. **Rule of Evidence:** Forensic facts override subjective opinions
3. **Rule of Functionality:** Tech Lead assessment carries highest weight for architecture

### Key Resolutions

"""

        # Add top 3 most notable resolutions
        for note in synthesis_notes[:3]:
            summary += f"- {note}\n"

        return summary.strip()


# Node function for LangGraph
def chief_justice_node(state: AgentState) -> Dict:
    """
    LangGraph node wrapper for Chief Justice.

    Args:
        state: Current graph state

    Returns:
        State updates with final verdicts
    """
    logger.log_node_start("ChiefJustice")
    start_time = time.time()

    try:
        chief_justice = ChiefJustice()
        result = chief_justice.synthesize(state)

        duration = time.time() - start_time
        logger.log_node_complete("ChiefJustice", duration)

        return result

    except Exception as e:
        duration = time.time() - start_time
        logger.log_node_error("ChiefJustice", e)
        raise NodeExecutionError("ChiefJustice", e)
