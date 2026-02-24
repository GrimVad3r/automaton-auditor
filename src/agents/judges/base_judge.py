"""
Base Judge class with common functionality for all judge personas.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Literal

from langchain_core.messages import SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

try:
    from langchain_anthropic import ChatAnthropic
except ImportError:  # pragma: no cover - optional provider dependency
    ChatAnthropic = None

from ...core.config import get_config
from ...core.state import Evidence, JudicialOpinion
from ...utils.logger import get_logger

logger = get_logger()


class StructuredOpinion(BaseModel):
    """Structured output schema for judicial opinions."""

    criterion_id: str = Field(description="The rubric criterion ID being evaluated")
    score: int = Field(ge=1, le=5, description="Score on 1-5 scale")
    argument: str = Field(
        description="Detailed reasoning for the score (minimum 100 characters)",
        min_length=100,
    )
    cited_evidence: List[str] = Field(
        description="Specific evidence references that support this opinion"
    )


class OfflineJudgeLLM:
    """
    Deterministic local fallback used when no LLM credentials are configured.
    """

    def with_structured_output(self, _schema, *args, **kwargs):
        return self

    def invoke(self, _messages):
        return StructuredOpinion(
            criterion_id="offline_fallback",
            score=3,
            argument=(
                "No LLM API key configured. Returning a deterministic neutral opinion "
                "to keep non-network workflows executable."
            ),
            cited_evidence=["offline_fallback"],
        )


class BaseJudge(ABC):
    """
    Abstract base class for all judge personas.
    Enforces structured output and provides common utilities.
    """

    def __init__(self, judge_name: Literal["Prosecutor", "Defense", "TechLead"]):
        """
        Initialize base judge.

        Args:
            judge_name: The persona of this judge
        """
        self.judge_name = judge_name
        self.config = get_config(require_llm_keys=False)

        # Initialize LLM with structured output
        llm_model = self._build_llm()
        self.llm = self._configure_structured_output(llm_model)

        logger.debug(f"Initialized {judge_name} with model {self.config.default_llm_model}")

    @abstractmethod
    def get_system_prompt(self) -> str:
        """
        Get the system prompt that defines this judge's persona.

        Returns:
            System prompt string
        """
        pass

    def render_opinion(
        self,
        criterion: Dict,
        evidences: Dict[str, List[Evidence]],
    ) -> JudicialOpinion:
        """
        Render a judicial opinion for a specific criterion.

        Args:
            criterion: The rubric criterion to evaluate
            evidences: All evidence collected by detectives

        Returns:
            JudicialOpinion object
        """
        criterion_data = (
            criterion.model_dump()
            if hasattr(criterion, "model_dump")
            else criterion
        )
        criterion_id = criterion_data["id"]
        logger.info(f"{self.judge_name} evaluating criterion: {criterion_id}")

        # Build evidence context
        evidence_context = self._format_evidence_for_context(evidences, criterion_data)

        # Get judicial logic for this persona
        judicial_instruction = criterion_data["judicial_logic"].get(
            self.judge_name.lower(), ""
        )

        # Construct prompt
        user_message = f"""
**CRITERION TO EVALUATE:**
{criterion_data['name']}

**FORENSIC INSTRUCTION:**
{criterion_data['forensic_instruction']}

**YOUR JUDICIAL LOGIC ({self.judge_name}):**
{judicial_instruction}

**AVAILABLE EVIDENCE:**
{evidence_context}

**YOUR TASK:**
As the {self.judge_name}, evaluate this criterion based on the evidence.
You must return a score (1-5) with detailed reasoning that cites specific evidence.

Score 1: Critical failure / Security violation / Missing entirely
Score 2: Major gaps / Significant issues
Score 3: Functional but flawed / Technical debt present
Score 4: Good implementation / Minor issues only
Score 5: Excellent / Exceeds expectations

Your argument must be at least 100 characters and cite specific evidence.
        """

        # Get system prompt
        system_prompt = self.get_system_prompt()

        try:
            # Invoke LLM with structured output
            response: StructuredOpinion = self.llm.invoke(
                [
                    SystemMessage(content=system_prompt),
                    {"role": "user", "content": user_message},
                ]
            )

            # Convert to JudicialOpinion
            opinion = JudicialOpinion(
                judge=self.judge_name,
                criterion_id=criterion_id,
                score=response.score,
                argument=response.argument,
                cited_evidence=response.cited_evidence,
            )

            logger.log_judicial_opinion(self.judge_name, criterion_id, opinion.score)

            return opinion

        except Exception as e:
            logger.error(f"{self.judge_name} failed to render opinion: {e}", exc_info=True)

            # Return fallback opinion
            return JudicialOpinion(
                judge=self.judge_name,
                criterion_id=criterion_id,
                score=3,  # Neutral score on error
                argument=f"Failed to evaluate due to error: {str(e)}. Defaulting to neutral score.",
                cited_evidence=["error"],
            )

    def _build_llm(self):
        """
        Build an LLM client based on configured provider credentials.
        """
        if self.config.openai_api_key:
            return ChatOpenAI(
                model=self.config.default_llm_model,
                temperature=self.config.llm_temperature,
            )

        if self.config.anthropic_api_key:
            if ChatAnthropic is None:
                raise ValueError(
                    "ANTHROPIC_API_KEY is set but langchain-anthropic is not installed"
                )
            return ChatAnthropic(
                model="claude-3-5-sonnet-latest",
                temperature=self.config.llm_temperature,
            )

        logger.warning(
            "No LLM API key configured; using deterministic offline judge fallback."
        )
        return OfflineJudgeLLM()

    def _configure_structured_output(self, llm_model):
        """
        Configure structured output with explicit function-calling mode when supported.
        """
        try:
            return llm_model.with_structured_output(
                StructuredOpinion,
                method="function_calling",
            )
        except TypeError:
            return llm_model.with_structured_output(StructuredOpinion)

    def _format_evidence_for_context(
        self,
        evidences: Dict[str, List[Evidence]],
        criterion: Dict,
    ) -> str:
        """
        Format evidence into a readable context string.

        Args:
            evidences: All collected evidence
            criterion: The criterion being evaluated

        Returns:
            Formatted evidence string
        """
        # Filter evidence by target artifact
        target_artifact = criterion.get("target_artifact")
        detective_targets = {
            "RepoInvestigator": "github_repo",
            "DocAnalyst": "pdf_report",
            "VisionInspector": "pdf_report",
            "CrossReference": "pdf_report",
        }

        context_parts = []

        for detective_name, evidence_list in evidences.items():
            if target_artifact and detective_name in detective_targets:
                if detective_targets[detective_name] != target_artifact:
                    continue

            context_parts.append(f"\n## {detective_name} Evidence:\n")

            for evidence in evidence_list:
                status = "✓ FOUND" if evidence.found else "✗ NOT FOUND"
                context_parts.append(f"\n{status} [{evidence.location}]")
                context_parts.append(f"Confidence: {evidence.confidence:.2f}")

                if evidence.content:
                    # Truncate long content
                    content = evidence.content[:500]
                    if len(evidence.content) > 500:
                        content += "..."
                    context_parts.append(f"Content: {content}")

                context_parts.append("")  # Blank line

        return "\n".join(context_parts)
