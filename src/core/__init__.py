"""
Core package exports.
"""

from .config import Config, get_config, load_config, load_rubric
from .state import (
    AgentState,
    DetectiveOutput,
    Evidence,
    JudicialOpinion,
    JudgeOutput,
    NodeOutput,
    RubricConfig,
    RubricDimension,
    SynthesisOutput,
)


def create_auditor_graph():
    """Lazily import the graph builder to avoid package import cycles."""
    from .graph import create_auditor_graph as _create_auditor_graph

    return _create_auditor_graph()

__all__ = [
    "AgentState",
    "Config",
    "DetectiveOutput",
    "Evidence",
    "JudgeOutput",
    "JudicialOpinion",
    "NodeOutput",
    "RubricConfig",
    "RubricDimension",
    "SynthesisOutput",
    "create_auditor_graph",
    "get_config",
    "load_config",
    "load_rubric",
]
