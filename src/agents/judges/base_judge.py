"""
Base Judge class with common functionality for all judge personas.
"""

from abc import ABC, abstractmethod
import json
import random
import re
import time
from typing import Dict, List, Literal, Optional

from langchain_core.messages import SystemMessage
try:
    from langchain_core.output_parsers import OutputParserException
except ImportError:  # fallback for older langchain-core
    OutputParserException = Exception  # type: ignore
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field, ValidationError

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
        self.force_json_mode = bool(
            self.config.huggingface_api_key
            and not self.config.openai_api_key
            and not self.config.anthropic_api_key
            and not self.config.groq_api_key
        ) or bool(
            self.config.openai_base_url
            and (
                "127.0.0.1" in self.config.openai_base_url
                or "localhost" in self.config.openai_base_url
                or True  # any custom OpenAI-compatible base URL: avoid tool_choice payloads
            )
        ) or bool(self.config.openai_base_url and not self.config.openai_api_key)

        # Initialize LLM with structured output
        self.raw_llm = self._build_llm()
        # Local / JSON-only providers cannot handle OpenAI tool_choice payloads;
        # skip structured output wrapper in force_json_mode.
        if self.force_json_mode:
            self.llm = self.raw_llm
        else:
            self.llm = self._configure_structured_output(self.raw_llm)

        logger.debug(
            f"Initialized {judge_name} with model {self.config.default_llm_model}"
        )

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
            criterion.model_dump() if hasattr(criterion, "model_dump") else criterion
        )
        criterion_id = criterion_data["id"]
        logger.info(f"{self.judge_name} evaluating criterion: {criterion_id}")

        # Build evidence context
        filtered_evidence = self._filter_evidence_by_target(
            evidences, criterion_data.get("target_artifact")
        )
        evidence_context = self._format_evidence_for_context(
            filtered_evidence, criterion_data
        )

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
Do not claim a feature is missing if FOUND evidence already confirms it.
If evidence is mixed, state uncertainty instead of absolute absence.

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
            response = self._ground_opinion(response, criterion_id, evidences)

            # Convert to JudicialOpinion
            opinion = JudicialOpinion(
                judge=self.judge_name,
                criterion_id=criterion_id,
                score=response.score,
                argument=response.argument,
                cited_evidence=response.cited_evidence,
            )

            if not opinion.cited_evidence or opinion.cited_evidence == [
                "insufficient_verified_evidence"
            ]:
                opinion.score = min(opinion.score, 2)
                opinion.argument += " No verified evidence; score capped."

            logger.log_judicial_opinion(self.judge_name, criterion_id, opinion.score)

            return opinion

        except Exception as e:
            logger.error(
                f"{self.judge_name} failed to render opinion: {e}", exc_info=True
            )

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
        if (
            self.config.huggingface_api_key
            and not self.config.openai_api_key
            and not self.config.anthropic_api_key
            and not self.config.groq_api_key
        ):
            return ChatOpenAI(
                model=self.config.default_llm_model,
                temperature=self.config.llm_temperature,
                api_key=self.config.huggingface_api_key,
                base_url=self.config.huggingface_base_url,
                max_tokens=self.config.llm_max_output_tokens,
            )

        if self.config.openai_api_key:
            return ChatOpenAI(
                model=self.config.default_llm_model,
                temperature=self.config.llm_temperature,
                max_tokens=self.config.llm_max_output_tokens,
                base_url=self.config.openai_base_url,
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
        if self.force_json_mode:
            json_prompt = messages + [
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
            try:
                response = self._invoke_with_rate_limit_retry(
                    lambda: self.llm.invoke(json_prompt),
                    operation="json_only_invoke",
                )
                return self._coerce_structured_response(response, criterion_id)
            except (ValidationError, OutputParserException) as exc:
                logger.warning(
                    f"{self.judge_name} structured output validation failed in JSON-only mode; "
                    f"retrying with raw JSON fallback. Error: {exc}"
                )
                fallback_response = self._invoke_with_rate_limit_retry(
                    lambda: self.raw_llm.invoke(json_prompt),
                    operation="json_only_fallback_invoke",
                )
                return self._coerce_structured_response(
                    fallback_response, criterion_id
                )
            except Exception as exc:
                if self._is_insufficient_quota(exc):
                    logger.warning(
                        f"{self.judge_name} provider quota depleted; returning neutral opinion."
                    )
                    return StructuredOpinion(
                        criterion_id=criterion_id,
                        score=3,
                        argument=self._pad_argument(
                            "Provider quota exhausted (HTTP 402 or insufficient credits). "
                            "Returning neutral opinion to keep pipeline moving."
                        ),
                        cited_evidence=["provider_quota_depleted"],
                    )
                if self._is_tool_use_failure(exc):
                    logger.warning(
                        f"{self.judge_name} structured function call failed in JSON-only mode; "
                        "retrying with raw JSON fallback."
                    )
                    fallback_response = self._invoke_with_rate_limit_retry(
                        lambda: self.raw_llm.invoke(json_prompt),
                        operation="json_only_fallback_invoke",
                    )
                    return self._coerce_structured_response(
                        fallback_response, criterion_id
                    )
                raise

        try:
            response = self._invoke_with_rate_limit_retry(
                lambda: self.llm.invoke(messages),
                operation="structured_invoke",
            )
            return self._coerce_structured_response(response, criterion_id)
        except (ValidationError, OutputParserException) as exc:
            logger.warning(
                f"{self.judge_name} structured output validation failed; "
                f"retrying with JSON fallback. Error: {exc}"
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
        except Exception as exc:
            if self._is_insufficient_quota(exc):
                logger.warning(
                    f"{self.judge_name} provider quota depleted; returning neutral opinion."
                )
                return StructuredOpinion(
                    criterion_id=criterion_id,
                    score=3,
                    argument=self._pad_argument(
                        "Provider quota exhausted (HTTP 402 or insufficient credits). "
                        "Returning neutral opinion to keep pipeline moving."
                    ),
                    cited_evidence=["provider_quota_depleted"],
                )
            if self._is_tool_use_failure(exc):
                logger.warning(
                    f"{self.judge_name} structured function call failed; retrying with JSON fallback."
                )
                fallback_response = self.raw_llm.invoke(
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
                )
                return self._coerce_structured_response(fallback_response, criterion_id)
            raise

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

    def _is_insufficient_quota(self, exc: Exception) -> bool:
        message = str(exc).lower()
        markers = (
            "insufficient_quota",
            "quota",
            "402",
            "depleted your monthly included credits",
            "payment required",
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

    def _coerce_structured_response(
        self, response, criterion_id: str
    ) -> StructuredOpinion:
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
            try:
                payload = self._extract_json_payload(text)
            except Exception:
                # Fall back to wrapping raw text into a payload
                payload = {
                    "criterion_id": criterion_id,
                    "score": 3,
                    "argument": self._pad_argument(
                        text or "Model returned unparseable output."
                    ),
                    "cited_evidence": ["fallback_evidence"],
                }

        payload.setdefault("criterion_id", criterion_id)

        # Coercions to handle providers that return strings or stringified lists
        if "score" in payload and isinstance(payload["score"], str):
            try:
                payload["score"] = int(float(payload["score"]))
            except Exception:
                pass

        if "cited_evidence" in payload:
            cited = payload["cited_evidence"]
            if isinstance(cited, str):
                # Try to parse stringified list JSON, else wrap as single-item list
                try:
                    parsed = json.loads(cited)
                    if isinstance(parsed, list):
                        payload["cited_evidence"] = parsed
                    else:
                        payload["cited_evidence"] = [str(parsed)]
                except Exception:
                    # Handle formats like "[item1, item2]" without quotes
                    stripped = cited.strip()
                    if stripped.startswith("[") and stripped.endswith("]"):
                        inner = stripped[1:-1].strip()
                        if inner:
                            payload["cited_evidence"] = [
                                part.strip(" '\"")
                                for part in inner.split(",")
                                if part.strip(" '\"")
                            ]
                        else:
                            payload["cited_evidence"] = []
                    else:
                        payload["cited_evidence"] = [cited]

        # Ensure all required keys exist before validation (but do not override provided values)
        payload.setdefault("criterion_id", criterion_id)
        if "score" not in payload:
            payload["score"] = 3
        if "argument" not in payload:
            payload["argument"] = self._pad_argument(
                "Fallback opinion with padding to satisfy minimum length."
            )
        if "cited_evidence" not in payload:
            payload["cited_evidence"] = ["fallback_evidence"]

        try:
            structured = StructuredOpinion(**payload)
        except Exception as exc:
            logger.warning(
                f"{self.judge_name} produced malformed output; "
                f"defaulting to neutral opinion. Error: {exc}"
            )
            padded_argument = (
                "Model returned malformed opinion; defaulting to neutral score until a valid structured output is produced. "
                "This padding ensures minimum length is satisfied for validation and indicates the provider output was unusable."
            )
            structured = StructuredOpinion(
                criterion_id=criterion_id,
                score=3,
                argument=self._pad_argument(padded_argument),
                cited_evidence=["malformed_output"],
            )

        # Guard rails: keep score in range and enforce minimum argument length.
        if not 1 <= structured.score <= 5:
            structured.score = 3
        if len(structured.argument or "") < 100:
            structured.argument = (
                structured.argument
                + " Additional verified evidence is required before stronger conclusions can be made."
            )
        if not structured.cited_evidence:
            structured.cited_evidence = ["insufficient_verified_evidence"]

        return structured

    def _filter_evidence_by_target(
        self, evidences: Dict[str, List[Evidence]], target_artifact: str | None
    ) -> Dict[str, List[Evidence]]:
        """Limit evidence to detectors relevant to the rubric target."""
        if not target_artifact:
            return evidences
        allowed = {
            "github_repo": {"RepoInvestigator"},
            # Allow RepoInvestigator when evaluating docs so judges can cross-check PDF claims against code
            "pdf_report": {"DocAnalyst", "VisionInspector", "CrossReference", "RepoInvestigator"},
        }.get(target_artifact, set())
        return {k: v for k, v in evidences.items() if k in allowed}

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

        try:
            return json.loads(candidate)
        except Exception as exc:
            raise ValueError(f"Failed to parse JSON payload: {exc}") from exc

    def _pad_argument(self, argument: str) -> str:
        """Ensure argument meets minimum length."""
        if len(argument) >= 100:
            return argument
        return argument + " " + (".".join(["pad"] * ((100 - len(argument)) // 4 + 1)))

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

            selected_evidence = self._select_evidence_for_context(
                evidence_list, max_items
            )

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

    def _select_evidence_for_context(
        self, evidence_list: List[Evidence], max_items: int
    ) -> List[Evidence]:
        """
        Prioritize diverse, high-signal evidence so critical proofs survive tight contexts.
        """
        if not evidence_list:
            return []

        # De-duplicate near-identical evidence entries.
        deduped: Dict[tuple[str, str], Evidence] = {}
        for ev in evidence_list:
            key = (
                self._normalize_location(self._compact_location(ev.location)),
                (ev.content or "").strip()[:120].lower(),
            )
            current = deduped.get(key)
            if current is None or ev.confidence > current.confidence:
                deduped[key] = ev

        priority_terms = (
            "src/core/state.py",
            "src/core/graph.py",
            "src/tools/git_tools.py",
            "src/agents/judges/base_judge.py",
            "src/agents/judges/prosecutor.py",
            "src/agents/judges/defense.py",
            "src/agents/judges/tech_lead.py",
            "pydantic models",
            "parallel detective fan-out",
            "distinct judge prompts",
            "structuredopinion",
            "response coercion",
        )

        def rank(ev: Evidence) -> tuple[float, float]:
            location = self._normalize_location(self._compact_location(ev.location))
            content = (ev.content or "").lower()
            bonus = 0.0
            for term in priority_terms:
                if term in location or term in content:
                    bonus += 0.2
            return ev.confidence + bonus, ev.confidence

        ranked = sorted(deduped.values(), key=rank, reverse=True)
        return ranked[:max_items]

    def _compact_location(self, location: str) -> str:
        if not location:
            return "N/A"

        normalized = location.replace("\\", "/")
        if "/repo/" in normalized:
            return normalized.split("/repo/", 1)[1]
        if len(normalized) > 90:
            return normalized[-90:]
        return normalized

    def _ground_opinion(
        self,
        response: StructuredOpinion,
        criterion_id: str,
        evidences: Dict[str, List[Evidence]],
    ) -> StructuredOpinion:
        """
        Ground LLM output against known evidence to reduce path hallucinations.
        """
        allowed_locations = self._collect_allowed_locations(evidences)
        if not allowed_locations:
            response.criterion_id = criterion_id
            return response

        argument = response.argument
        adjusted_score = response.score
        unverified_paths = self._find_unverified_paths(argument, allowed_locations)
        penalties = 0
        if unverified_paths:
            for path in unverified_paths:
                argument = argument.replace(path, "[UNVERIFIED_PATH]")
            penalties += 1

        argument, removed_claims = self._prune_unverified_claim_sentences(
            argument, evidences, allowed_locations
        )
        if removed_claims:
            penalties += 1

        argument, contradicted_claims = self._remove_contradicted_claim_sentences(
            argument, evidences
        )
        if contradicted_claims:
            adjusted_score = min(5, adjusted_score + 1)
            argument += " Claims contradicting verified evidence were removed."

        if penalties:
            adjusted_score = max(1, adjusted_score - penalties)
            argument += " Unverified claims were removed from this opinion."

        if len(argument) < 100:
            argument = (
                argument
                + " Additional verified evidence is required before stronger conclusions can be made."
            )

        filtered_citations = [
            citation
            for citation in response.cited_evidence
            if self._is_citation_verified(citation, allowed_locations)
        ]
        if not filtered_citations:
            filtered_citations = self._fallback_citations(evidences)

        return StructuredOpinion(
            criterion_id=criterion_id,
            score=adjusted_score,
            argument=argument,
            cited_evidence=filtered_citations,
        )

    def _collect_allowed_locations(
        self, evidences: Dict[str, List[Evidence]]
    ) -> List[str]:
        """Collect normalized evidence locations usable for citation checks."""
        locations: set[str] = set()
        for evidence_list in evidences.values():
            for evidence in evidence_list:
                location = self._normalize_location(evidence.location)
                if location:
                    locations.add(location)
                compact_location = self._normalize_location(
                    self._compact_location(evidence.location)
                )
                if compact_location:
                    locations.add(compact_location)
        return sorted(locations)

    def _normalize_location(self, value: str) -> str:
        """Normalize a location string for fuzzy evidence matching."""
        return str(value or "").strip().lower().replace("\\", "/")

    def _is_citation_verified(
        self, citation: str, allowed_locations: List[str]
    ) -> bool:
        """Check whether a citation overlaps with known evidence locations."""
        normalized_citation = self._normalize_location(citation)
        if not normalized_citation:
            return False

        if normalized_citation.endswith("/"):
            return False
        if (
            "/" in normalized_citation
            and "." not in normalized_citation.rsplit("/", 1)[-1]
        ):
            if not normalized_citation.startswith("http"):
                return False

        return self._is_location_supported(normalized_citation, allowed_locations)

    def _fallback_citations(self, evidences: Dict[str, List[Evidence]]) -> List[str]:
        """Fallback to top evidence locations when model citations are ungrounded."""
        ranked: List[Evidence] = []
        for evidence_list in evidences.values():
            ranked.extend(evidence_list)
        ranked = sorted(ranked, key=lambda ev: ev.confidence, reverse=True)
        fallback = [
            self._compact_location(ev.location) for ev in ranked[:3] if ev.location
        ]
        return fallback or ["insufficient_verified_evidence"]

    def _find_unverified_paths(
        self, argument: str, allowed_locations: List[str]
    ) -> List[str]:
        """Extract path-like references that are not present in collected evidence."""
        path_pattern = re.compile(
            r"\b(?:src|lib|app|tools|agents)/[\w./-]+\b", re.IGNORECASE
        )
        unverified: List[str] = []
        for match in path_pattern.finditer(argument):
            referenced_path = match.group(0)
            normalized_path = self._normalize_location(referenced_path)
            is_verified = self._is_location_supported(normalized_path, allowed_locations)
            if not is_verified:
                unverified.append(referenced_path)
        return unverified

    def _is_location_supported(
        self, normalized_path: str, allowed_locations: List[str]
    ) -> bool:
        """
        Determine whether a referenced path is supported by known locations.
        Includes conservative aliases for legacy path mentions.
        """
        for location in allowed_locations:
            if (
                normalized_path == location
                or normalized_path in location
                or location.endswith(normalized_path)
            ):
                return True

        alias_map = {
            "src/state.py": "src/core/state.py",
            "src/graph.py": "src/core/graph.py",
        }
        alias = alias_map.get(normalized_path)
        if alias:
            for location in allowed_locations:
                if alias == location or alias in location or location.endswith(alias):
                    return True

        return False

    def _prune_unverified_claim_sentences(
        self,
        argument: str,
        evidences: Dict[str, List[Evidence]],
        allowed_locations: List[str],
    ) -> tuple[str, int]:
        """
        Remove high-confidence quantitative/absolute claims not supported by evidence.
        """
        sentences = re.split(r"(?<=[.!?])\s+", argument.strip())
        if not sentences:
            return argument, 0

        evidence_tokens = self._collect_evidence_tokens(evidences)
        kept_sentences: List[str] = []
        removed_count = 0

        for sentence in sentences:
            if not sentence:
                continue
            if self._is_high_risk_claim(
                sentence
            ) and not self._sentence_has_evidence_anchor(
                sentence, evidence_tokens, allowed_locations
            ):
                removed_count += 1
                continue
            kept_sentences.append(sentence)

        cleaned = " ".join(kept_sentences).strip()
        if not cleaned:
            cleaned = "Opinion retained only where verifiable evidence exists."
        return cleaned, removed_count

    def _is_high_risk_claim(self, sentence: str) -> bool:
        """Detect claim patterns that should be evidence-anchored."""
        high_risk_patterns = (
            r"\b\d{1,3}%\b",
            r"\b\d+\s*(?:times|x)\b",
            r"\b(?:always|never|purely|only|all|none|no evidence)\b",
        )
        return any(
            re.search(pattern, sentence, re.IGNORECASE)
            for pattern in high_risk_patterns
        )

    def _collect_evidence_tokens(
        self, evidences: Dict[str, List[Evidence]]
    ) -> set[str]:
        """Collect compact token set from evidence for lightweight claim anchoring."""
        tokens: set[str] = set()
        for evidence_list in evidences.values():
            for evidence in evidence_list:
                text = f"{evidence.location} {evidence.content or ''}"
                for token in re.findall(r"[A-Za-z][A-Za-z0-9_./-]{3,}", text.lower()):
                    if token.startswith(("src/", "http", "c:/")) or len(token) >= 6:
                        tokens.add(token)
        return tokens

    def _sentence_has_evidence_anchor(
        self,
        sentence: str,
        evidence_tokens: set[str],
        allowed_locations: List[str],
    ) -> bool:
        """Check whether a sentence overlaps with evidence-derived anchors."""
        normalized_sentence = self._normalize_location(sentence)
        if any(location in normalized_sentence for location in allowed_locations):
            return True

        sentence_tokens = set(
            re.findall(r"[A-Za-z][A-Za-z0-9_./-]{3,}", normalized_sentence)
        )
        overlap = sentence_tokens & evidence_tokens
        return len(overlap) >= 2

    def _remove_contradicted_claim_sentences(
        self, argument: str, evidences: Dict[str, List[Evidence]]
    ) -> tuple[str, int]:
        """
        Remove claims that explicitly contradict strong, verified evidence.
        """
        sentences = re.split(r"(?<=[.!?])\s+", argument.strip())
        if not sentences:
            return argument, 0

        evidence_text = self._build_evidence_text(evidences)
        active_patterns: List[re.Pattern[str]] = []

        if self._has_sandbox_evidence(evidence_text):
            active_patterns.extend(
                [
                    re.compile(
                        r"\bfail\w*\s+to\s+implement\s+sandbox(?:ed)?\s+git\b",
                        re.IGNORECASE,
                    ),
                    re.compile(r"\bno mention of sandbox", re.IGNORECASE),
                    re.compile(r"\blacks?\b.*\bsandbox", re.IGNORECASE),
                    re.compile(r"\babsence of explicit sandbox", re.IGNORECASE),
                    re.compile(r"\bno explicit sandbox", re.IGNORECASE),
                    re.compile(
                        r"\bwithout\b.*\bsandbox(?:ing|ed)?\b", re.IGNORECASE
                    ),
                ]
            )

        if self._has_parallel_graph_evidence(evidence_text):
            active_patterns.extend(
                [
                    re.compile(r"\blinear graph\b", re.IGNORECASE),
                    re.compile(r"\bno parallel\w*\b", re.IGNORECASE),
                    re.compile(
                        r"\bno code implements\b.*\b(parallel|fan-out|fan-in)\b",
                        re.IGNORECASE,
                    ),
                    re.compile(
                        r"\bno proof of\b.*\bparallel(?:ism| judges| execution)?\b",
                        re.IGNORECASE,
                    ),
                    re.compile(
                        r"\bparallel(?:ism| judges)?\b.*\bremains unverified\b",
                        re.IGNORECASE,
                    ),
                ]
            )

        if self._has_distinct_persona_evidence(evidence_text):
            active_patterns.extend(
                [
                    re.compile(
                        r"\bshared\s+\d{1,3}%\s+identical prompt\b",
                        re.IGNORECASE,
                    ),
                    re.compile(r"\bpersona collusion\b", re.IGNORECASE),
                    re.compile(r"\black of distinct judicial logic\b", re.IGNORECASE),
                ]
            )

        if not active_patterns:
            return argument, 0

        kept_sentences: List[str] = []
        removed_count = 0
        for sentence in sentences:
            normalized = self._normalize_location(sentence)
            if any(pattern.search(normalized) for pattern in active_patterns):
                removed_count += 1
                continue
            kept_sentences.append(sentence)

        cleaned = " ".join(kept_sentences).strip()
        if not cleaned:
            cleaned = "Opinion retained only where verifiable evidence exists."
        return cleaned, removed_count

    def _build_evidence_text(self, evidences: Dict[str, List[Evidence]]) -> str:
        """Flatten found evidence into one normalized text blob for rule checks."""
        parts: List[str] = []
        for evidence_list in evidences.values():
            for evidence in evidence_list:
                if not evidence.found:
                    continue
                parts.append(f"{evidence.location} {evidence.content or ''}")
        return self._normalize_location(" ".join(parts))

    def _has_sandbox_evidence(self, evidence_text: str) -> bool:
        """Detect strong proof that sandboxed git behavior is implemented."""
        required_terms = (
            "sandboxed_git_clone",
            "repositorysandbox.clone_repository",
            "src/tools/git_tools.py",
            "without raw os.system",
        )
        return any(term in evidence_text for term in required_terms)

    def _has_parallel_graph_evidence(self, evidence_text: str) -> bool:
        """Detect strong proof of non-linear graph orchestration."""
        return (
            "parallel detective fan-out" in evidence_text
            or "parallel judge fan-out" in evidence_text
            or "stategraph found with parallel architecture" in evidence_text
            or "src/core/graph.py" in evidence_text
        )

    def _has_distinct_persona_evidence(self, evidence_text: str) -> bool:
        """Detect proof that persona prompts are differentiated."""
        return (
            "distinct judge prompts detected" in evidence_text
            or (
                "trust no one" in evidence_text
                and "reward effort" in evidence_text
                and "does it actually work" in evidence_text
            )
        )
