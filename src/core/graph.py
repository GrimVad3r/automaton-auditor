"""
LangGraph orchestration for the Automaton Auditor.
Implements the three-layer hierarchical state graph.
"""

import time
import os
from pathlib import Path
from typing import Dict

from langgraph.graph import StateGraph, END

from ..agents.detectives import (
    doc_analyst_node,
    repo_investigator_node,
    vision_inspector_node,
)
from ..agents.judges import defense_node, prosecutor_node, tech_lead_node
from ..agents.justice import chief_justice_node
from ..core.config import get_config
from ..core.state import AgentState, Evidence
from ..tools import PDFAnalyzer
from ..utils.logger import get_logger

logger = get_logger()
FAIL_FAST = os.getenv("AUDITOR_FAIL_FAST", "true").lower() == "true"


def handle_error_node(state: AgentState) -> Dict:
    """
    Centralized error handler to ensure synthesis is aware of failures.
    """
    logger.log_node_start("HandleError")
    errors = state.get("errors", [])
    if errors:
        logger.warning(f"Errors detected upstream: {errors}")
    logger.log_node_complete("HandleError", 0.01)
    return {"errors": errors}


def _safe_node(node_fn, node_name: str, empty_updates: Dict) -> callable:
    """
    Wrap a node so failures are recorded in state instead of terminating the graph.
    """

    def wrapper(state: AgentState) -> Dict:
        try:
            return node_fn(state)
        except Exception as exc:
            logger.log_node_error(node_name, exc)
            if FAIL_FAST:
                raise
            updates = dict(empty_updates)
            updates["errors"] = [f"{node_name}: {exc}"]
            return updates

    return wrapper


def create_auditor_graph() -> StateGraph:
    """
    Create the hierarchical auditor graph with parallel execution.

    Graph Structure:
    START
      ↓
    INITIALIZE
      ↓
    ┌─────────────┐
    │  DETECTIVES │ (Parallel)
    │  - Repo     │
    │  - Doc      │
    └─────────────┘
      ↓
    AGGREGATE_EVIDENCE
      ↓
    ┌─────────────┐
    │   JUDGES    │ (Parallel)
    │  - Prosecutor
    │  - Defense  │
    │  - TechLead │
    └─────────────┘
      ↓
    CHIEF_JUSTICE
      ↓
    FINALIZE
      ↓
    END

    Returns:
        Compiled StateGraph
    """
    logger.info("Building Automaton Auditor graph")

    # Create graph builder
    builder = StateGraph(AgentState)

    # Add initialization node
    builder.add_node("initialize", initialize_node)

    # Layer 1: Detective nodes (parallel)
    config = get_config(require_llm_keys=False)
    builder.add_node(
        "repo_investigator",
        _safe_node(
            repo_investigator_node,
            "RepoInvestigator",
            {"evidences": {"RepoInvestigator": []}},
        ),
    )
    builder.add_node(
        "doc_analyst",
        _safe_node(
            doc_analyst_node,
            "DocAnalyst",
            {"evidences": {"DocAnalyst": []}},
        ),
    )
    detective_nodes = ["repo_investigator", "doc_analyst"]
    if config.enable_vision_inspector:
        builder.add_node(
            "vision_inspector",
            _safe_node(
                vision_inspector_node,
                "VisionInspector",
                {"evidences": {"VisionInspector": []}},
            ),
        )
        detective_nodes.append("vision_inspector")
        logger.info("VisionInspector node enabled")
    else:
        logger.info("VisionInspector node disabled")

    # Evidence aggregation node
    builder.add_node(
        "aggregate_evidence",
        _safe_node(
            aggregate_evidence_node,
            "AggregateEvidence",
            {"aggregated_evidence": None},
        ),
    )

    # Layer 2: Judge nodes (parallel)
    builder.add_node(
        "prosecutor",
        _safe_node(prosecutor_node, "Prosecutor", {"opinions": []}),
    )
    builder.add_node("defense", _safe_node(defense_node, "Defense", {"opinions": []}))
    builder.add_node(
        "tech_lead", _safe_node(tech_lead_node, "TechLead", {"opinions": []})
    )

    # Error handling node
    builder.add_node("handle_error", handle_error_node)

    # Layer 3: Chief Justice synthesis
    builder.add_node(
        "chief_justice",
        _safe_node(
            chief_justice_node,
            "ChiefJustice",
            {
                "final_scores": {},
                "synthesis_summary": "Synthesis skipped due to earlier errors.",
                "final_report": "",
            },
        ),
    )

    # Finalization node
    builder.add_node("finalize", _safe_node(finalize_node, "Finalize", {}))

    # Define edges - START to Initialize
    builder.set_entry_point("initialize")

    # Fan-out: Initialize to Detectives (parallel)
    for detective_node in detective_nodes:
        builder.add_edge("initialize", detective_node)

    # Fan-in: Detectives to Aggregation
    for detective_node in detective_nodes:
        builder.add_edge(detective_node, "aggregate_evidence")

    # Fan-out: Aggregation to Judges (parallel)
    builder.add_edge("aggregate_evidence", "prosecutor")
    builder.add_edge("aggregate_evidence", "defense")
    builder.add_edge("aggregate_evidence", "tech_lead")

    # Fan-in: Judges to error handler then Chief Justice
    builder.add_edge("prosecutor", "handle_error")
    builder.add_edge("defense", "handle_error")
    builder.add_edge("tech_lead", "handle_error")
    builder.add_edge("handle_error", "chief_justice")

    # Chief Justice to Finalize
    builder.add_edge("chief_justice", "finalize")

    # Finalize to END
    builder.add_edge("finalize", END)

    # Compile graph
    graph = builder.compile()

    logger.info("Auditor graph compiled successfully")
    return graph


def initialize_node(state: AgentState) -> Dict:
    """
    Initialize the audit process.

    Args:
        state: Current graph state

    Returns:
        State updates
    """
    logger.log_node_start("Initialize")

    logger.info(f"Initializing audit for repository: {state['repo_url']}")
    logger.info(f"PDF report: {state['pdf_path']}")

    return {
        "execution_start_time": time.time(),
        "evidences": {},
        "opinions": [],
        "errors": [],
    }


def aggregate_evidence_node(state: AgentState) -> Dict:
    """
    Aggregate evidence from all detectives before passing to judges.

    Args:
        state: Current graph state

    Returns:
        State updates
    """
    logger.log_node_start("AggregateEvidence")

    evidences = state.get("evidences", {})

    # Log summary
    total_evidence = sum(len(ev_list) for ev_list in evidences.values())
    logger.info(
        f"Aggregated {total_evidence} pieces of evidence from {len(evidences)} detectives"
    )

    for detective, ev_list in evidences.items():
        logger.info(f"  - {detective}: {len(ev_list)} evidence items")

    # Create aggregated summary
    summary_parts = []
    for detective, ev_list in evidences.items():
        found = sum(1 for ev in ev_list if ev.found)
        summary_parts.append(f"{detective}: {found}/{len(ev_list)} found")

    aggregated_summary = "; ".join(summary_parts)

    # Cross-reference PDF claims after fan-in so detective layer can stay parallel.
    cross_reference_evidence = _cross_reference_pdf_claims(state, evidences)
    updates: Dict = {
        "aggregated_evidence": aggregated_summary,
    }
    if cross_reference_evidence:
        updates["evidences"] = {"CrossReference": cross_reference_evidence}

    logger.log_node_complete("AggregateEvidence", 0.1)

    return updates


def _cross_reference_pdf_claims(
    state: AgentState, evidences: Dict[str, list]
) -> list[Evidence]:
    """
    Cross-reference document claims against repository evidence after fan-in.
    """
    repo_evidence = evidences.get("RepoInvestigator", [])
    if not repo_evidence:
        return []

    try:
        pdf_file = Path(state["pdf_path"])
        if not pdf_file.exists():
            return []

        base_dir = pdf_file.parent if pdf_file.parent.exists() else Path.cwd()
        pdf_analyzer = PDFAnalyzer(base_dir)
        pdf_text = pdf_analyzer._extract_text(pdf_file)

        verified_locations = []
        repo_roots: set[Path] = set()
        for evidence in repo_evidence:
            if (
                evidence.found
                and evidence.location
                and ("/" in evidence.location or "\\" in evidence.location)
            ):
                verified_locations.append(evidence.location)
                normalized_location = str(evidence.location).replace("\\", "/")
                if "/repo/" in normalized_location:
                    root_candidate = normalized_location.split("/repo/", 1)[0] + "/repo"
                    root_path = Path(root_candidate)
                    if root_path.exists() and root_path.is_dir():
                        repo_roots.add(root_path)

        # Build a verified file inventory from the cloned repository to avoid
        # false hallucination flags when PDFs cite real files that were not
        # directly emitted as detective evidence locations.
        allowed_ext = {".py", ".md", ".json", ".toml", ".yaml", ".yml"}
        for repo_root in repo_roots:
            try:
                for file_path in repo_root.rglob("*"):
                    if file_path.is_file() and file_path.suffix.lower() in allowed_ext:
                        verified_locations.append(str(file_path))
            except Exception as exc:
                logger.warning(
                    f"Failed to enumerate repository files for cross-reference: {exc}"
                )

        cross_ref = pdf_analyzer.cross_reference_claims(pdf_text, verified_locations)
        return list(cross_ref.values())
    except Exception as e:
        logger.warning(f"Post-aggregation cross-reference failed: {e}")
        return []


def finalize_node(state: AgentState) -> Dict:
    """
    Finalize the audit and prepare outputs.

    Args:
        state: Current graph state

    Returns:
        State updates
    """
    logger.log_node_start("Finalize")

    end_time = time.time()
    start_time = state.get("execution_start_time", end_time)
    total_duration = end_time - start_time

    logger.info(f"Audit completed in {total_duration:.2f} seconds")

    # Log final scores
    final_scores = state.get("final_scores", {})
    if final_scores:
        logger.info("Final Scores:")
        for criterion, score in final_scores.items():
            logger.info(f"  - {criterion}: {score}/5")

    logger.log_node_complete("Finalize", 0.1)

    return {
        "execution_end_time": end_time,
    }
