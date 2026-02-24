"""
Base Judge class with common functionality for all judge personas.
"""

from abc import ABC, abstractmethod
import json
import random
import re
import time
from typing import Dict, List, Literal

from langchain_core.messages import SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

try:
    from langchain_anthropic import ChatAnthropic
except ImportError:  # pragma: no cover - optional provider dependency
    ChatAnthropic = None

try:
    from langchain_groq import ChatGroq
except ImportError:  # pragma: no cover - optional provider dependency
    ChatGroq = None

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
        self.raw_llm = self._build_llm()
        self.llm = self._configure_structured_output(self.raw_llm)

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
Keep your argument concise (target 100-220 characters).
        """

        # Get system prompt
        system_prompt = self.get_system_prompt()

        try:
            messages = [
                SystemMessage(content=system_prompt),
                {"role": "user", "content": user_message},
            ]
            response = self._invoke_with_fallback(messages, criterion_id)

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
                max_tokens=self.config.llm_max_output_tokens,
            )

        if self.config.anthropic_api_key:
            if ChatAnthropic is None:
                raise ValueError(
                    "ANTHROPIC_API_KEY is set but langchain-anthropic is not installed"
                )
            return ChatAnthropic(
                model="claude-3-5-sonnet-latest",
                temperature=self.config.llm_temperature,
                max_tokens=self.config.llm_max_output_tokens,
            )

        if self.config.groq_api_key:
            if ChatGroq is None:
                raise ValueError(
                    "GROQ_API_KEY is set but langchain-groq is not installed"
                )

            model_name = self.config.default_llm_model
            if model_name.startswith(("gpt-", "claude-")):
                logger.warning(
                    f"Model '{model_name}' is not a Groq-native model. "
                    f"Falling back to DEFAULT_GROQ_MODEL={self.config.default_groq_model}."
                )
                model_name = self.config.default_groq_model

            return ChatGroq(
                model=model_name,
                temperature=self.config.llm_temperature,
                api_key=self.config.groq_api_key,
                max_tokens=self.config.llm_max_output_tokens,
            )

        if self.config.huggingface_api_key:
            model_name = self.config.default_huggingface_model
            return ChatOpenAI(
                model=model_name,
                temperature=self.config.llm_temperature,
                api_key=self.config.huggingface_api_key,
                base_url=self.config.huggingface_base_url,
                max_tokens=self.config.llm_max_output_tokens,
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

    def _invoke_with_fallback(self, messages, criterion_id: str) -> StructuredOpinion:
        """
        Invoke structured output first; on tool/function-call failures, retry via JSON text mode.
        """
        try:
            response = self._invoke_with_rate_limit_retry(
                lambda: self.llm.invoke(messages),
                operation="structured_invoke",
            )
            return self._coerce_structured_response(response, criterion_id)
        except Exception as exc:
            if not self._is_tool_use_failure(exc):
                raise

            logger.warning(
                f"{self.judge_name} structured function call failed; retrying with JSON fallback."
            )
            fallback_response = self._invoke_with_rate_limit_retry(
                lambda: self.raw_llm.invoke(
                    messages
                    + [
                        {
                            "role": "user",
                            "content": (
                                "Return ONLY valid JSON with keys: "
                                "criterion_id (string), score (integer 1-5), "
                                "argument (string min 100 chars), cited_evidence (array of strings). "
                                f"Use criterion_id='{criterion_id}'."
                            ),
                        }
                    ]
                ),
                operation="json_fallback_invoke",
            )
            return self._coerce_structured_response(fallback_response, criterion_id)

    def _is_tool_use_failure(self, exc: Exception) -> bool:
        message = str(exc)
        markers = (
            "tool_use_failed",
            "Failed to call a function",
            "function_calling",
        )
        return any(marker in message for marker in markers)

    def _is_rate_limit_error(self, exc: Exception) -> bool:
        message = str(exc)
        markers = (
            "429",
            "rate_limit_exceeded",
            "Rate limit reached",
            "tokens per minute",
            "insufficient_quota",
        )
        return any(marker in message for marker in markers)

    def _invoke_with_rate_limit_retry(self, invoke_fn, operation: str):
        """
        Retry an LLM call on provider rate-limit errors using bounded exponential backoff.
        """
        attempts = max(1, self.config.max_retries)
        base_delay = self.config.llm_retry_base_delay_seconds
        max_delay = self.config.llm_retry_max_delay_seconds

        for attempt in range(attempts):
            try:
                return invoke_fn()
            except Exception as exc:
                if not self._is_rate_limit_error(exc) or attempt == attempts - 1:
                    raise

                delay = min(max_delay, base_delay * (2**attempt))
                jitter = random.uniform(0.0, min(0.5, delay * 0.25))
                wait_seconds = delay + jitter
                logger.warning(
                    f"{self.judge_name} hit rate limit during {operation}; "
                    f"retrying in {wait_seconds:.2f}s "
                    f"(attempt {attempt + 1}/{attempts})."
                )
                time.sleep(wait_seconds)

    def _coerce_structured_response(self, response, criterion_id: str) -> StructuredOpinion:
        """Convert model response variants into StructuredOpinion."""
        expected_keys = {"criterion_id", "score", "argument", "cited_evidence"}

        if isinstance(response, StructuredOpinion):
            if response.criterion_id:
                return response
            response.criterion_id = criterion_id
            return response

        payload = None
        if isinstance(response, dict) and expected_keys.issubset(response.keys()):
            payload = dict(response)
        elif hasattr(response, "model_dump"):
            dumped = response.model_dump()
            if isinstance(dumped, dict) and expected_keys.issubset(dumped.keys()):
                payload = dumped

        if payload is None:
            text = self._extract_text_content(response)
            payload = self._extract_json_payload(text)

        payload.setdefault("criterion_id", criterion_id)
        return StructuredOpinion(**payload)

    def _extract_text_content(self, response) -> str:
        """Extract plain text content from LangChain response objects."""
        content = getattr(response, "content", response)
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            parts: List[str] = []
            for part in content:
                if isinstance(part, dict) and "text" in part:
                    parts.append(str(part["text"]))
                else:
                    parts.append(str(part))
            return "\n".join(parts).strip()
        return str(content).strip()

    def _extract_json_payload(self, text: str) -> Dict:
        """Parse JSON payload from raw text or fenced blocks."""
        if not text:
            raise ValueError("Empty model response while parsing JSON payload")

        candidate = text
        if "```" in text:
            match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
            if match:
                candidate = match.group(1)
        if candidate == text:
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if match:
                candidate = match.group(0)

        return json.loads(candidate)

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

    # Override with token-budget-aware formatting for low-TPM providers.
    def _format_evidence_for_context(
        self,
        evidences: Dict[str, List[Evidence]],
        criterion: Dict,
    ) -> str:
        target_artifact = criterion.get("target_artifact")
        detective_targets = {
            "RepoInvestigator": "github_repo",
            "DocAnalyst": "pdf_report",
            "VisionInspector": "pdf_report",
            "CrossReference": "pdf_report",
        }

        context_parts = []
        max_items = self.config.llm_max_evidence_items_per_detective
        max_content_chars = self.config.llm_max_evidence_content_chars
        max_context_chars = self.config.llm_max_context_chars

        for detective_name, evidence_list in evidences.items():
            if target_artifact and detective_name in detective_targets:
                if detective_targets[detective_name] != target_artifact:
                    continue

            context_parts.append(f"\n## {detective_name} Evidence:\n")

            selected_evidence = sorted(
                evidence_list,
                key=lambda ev: ev.confidence,
                reverse=True,
            )[:max_items]

            for evidence in selected_evidence:
                status = "FOUND" if evidence.found else "NOT FOUND"
                location = self._compact_location(evidence.location)
                context_parts.append(f"\n{status} [{location}]")
                context_parts.append(f"Confidence: {evidence.confidence:.2f}")

                if evidence.content:
                    content = " ".join(evidence.content.split())
                    if len(content) > max_content_chars:
                        content = content[:max_content_chars] + "..."
                    context_parts.append(f"Content: {content}")

                context_parts.append("")

        context = "\n".join(context_parts)
        if len(context) > max_context_chars:
            context = context[:max_context_chars].rstrip()
            context += "\n...[truncated for token budget]"
        return context

    def _compact_location(self, location: str) -> str:
        if not location:
            return "N/A"

        normalized = location.replace("\\", "/")
        if "/repo/" in normalized:
            return normalized.split("/repo/", 1)[1]
        if len(normalized) > 90:
            return normalized[-90:]
        return normalized
