"""
State definitions for the Automaton Auditor LangGraph.
Uses Pydantic for strict typing and operator reducers for parallel execution safety.
"""

import operator
from typing import Annotated, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field
from typing_extensions import TypedDict


class Evidence(BaseModel):
    """
    Evidence object collected by Detective agents.
    Represents objective findings with confidence scoring.
    """

    found: bool = Field(description="Whether the artifact exists")
    content: Optional[str] = Field(default=None, description="Relevant content snippet")
    location: str = Field(description="File path, commit hash, or document section")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence score [0.0-1.0]")
    detective_name: str = Field(
        description="Name of the detective agent that found this"
    )
    timestamp: Optional[str] = Field(
        default=None, description="When evidence was collected"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "found": True,
                "content": "class AgentState(TypedDict):",
                "location": "src/state.py:15",
                "confidence": 0.95,
                "detective_name": "RepoInvestigator",
                "timestamp": "2024-01-15T10:30:00",
            }
        }
    )


class JudicialOpinion(BaseModel):
    """
    Structured opinion from a Judge agent.
    Must be tied to a specific criterion with cited evidence.
    """

    judge: Literal["Prosecutor", "Defense", "TechLead"] = Field(
        description="Judge persona that rendered this opinion"
    )
    criterion_id: str = Field(description="Rubric criterion ID being evaluated")
    score: int = Field(ge=1, le=5, description="Score on 1-5 scale")
    argument: str = Field(description="Detailed reasoning for the score")
    cited_evidence: List[str] = Field(
        default_factory=list, description="References to evidence objects"
    )
    timestamp: Optional[str] = Field(
        default=None, description="When opinion was rendered"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "judge": "Prosecutor",
                "criterion_id": "forensic_accuracy_code",
                "score": 2,
                "argument": "Repository lacks sandboxed git operations. Security vulnerability detected.",
                "cited_evidence": ["RepoInvestigator:src/tools/git_tools.py"],
                "timestamp": "2024-01-15T10:35:00",
            }
        }
    )


class RubricDimension(BaseModel):
    """Single criterion from the rubric."""

    id: str
    name: str
    target_artifact: Literal["github_repo", "pdf_report"]
    forensic_instruction: str
    judicial_logic: Dict[str, str]


class RubricConfig(BaseModel):
    """Complete rubric configuration."""

    rubric_metadata: Dict[str, str]
    dimensions: List[RubricDimension]
    synthesis_rules: Dict[str, str]


class AgentState(TypedDict):
    """
    Central state for the Automaton Auditor LangGraph.
    Uses operator reducers to safely merge data from parallel nodes.

    Reducers:
    - operator.ior: Merges dictionaries (union)
    - operator.add: Appends to lists
    """

    # Input parameters
    repo_url: str
    pdf_path: str
    rubric: RubricConfig

    # Detective layer outputs (parallel execution safe)
    evidences: Annotated[Dict[str, List[Evidence]], operator.ior]

    # Judge layer outputs (parallel execution safe)
    opinions: Annotated[List[JudicialOpinion], operator.add]

    # Evidence aggregation (intermediate)
    aggregated_evidence: Optional[str]

    # Final outputs
    final_scores: Dict[str, int]
    synthesis_summary: str
    final_report: str

    # Metadata
    execution_start_time: Optional[float]
    execution_end_time: Optional[float]
    errors: Annotated[List[str], operator.add]


class NodeOutput(BaseModel):
    """
    Standard output format for graph nodes.
    Enables consistent error handling and logging.
    """

    success: bool = Field(description="Whether the node executed successfully")
    data: Optional[Dict] = Field(default=None, description="Output data")
    error: Optional[str] = Field(default=None, description="Error message if failed")
    duration: Optional[float] = Field(
        default=None, description="Execution time in seconds"
    )


class DetectiveOutput(BaseModel):
    """Output from a Detective node."""

    detective_name: str
    evidence_list: List[Evidence]
    execution_time: float
    success: bool
    error: Optional[str] = None


class JudgeOutput(BaseModel):
    """Output from a Judge node."""

    judge_name: str
    opinions: List[JudicialOpinion]
    execution_time: float
    success: bool
    error: Optional[str] = None


class SynthesisOutput(BaseModel):
    """Output from Chief Justice synthesis."""

    final_scores: Dict[str, int]
    synthesis_summary: str
    report_content: str
    execution_time: float
    success: bool
    error: Optional[str] = None
