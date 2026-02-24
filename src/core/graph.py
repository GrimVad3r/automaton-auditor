"""
LangGraph orchestration for the Automaton Auditor.
Implements the three-layer hierarchical state graph.
"""

import time
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
from ..core.state import AgentState, Evidence
from ..tools import PDFAnalyzer
from ..utils.logger import get_logger

logger = get_logger()


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
    builder.add_node("repo_investigator", repo_investigator_node)
    builder.add_node("doc_analyst", doc_analyst_node)
    builder.add_node("vision_inspector", vision_inspector_node)

    # Evidence aggregation node
    builder.add_node("aggregate_evidence", aggregate_evidence_node)

    # Layer 2: Judge nodes (parallel)
    builder.add_node("prosecutor", prosecutor_node)
    builder.add_node("defense", defense_node)
    builder.add_node("tech_lead", tech_lead_node)

    # Layer 3: Chief Justice synthesis
    builder.add_node("chief_justice", chief_justice_node)

    # Finalization node
    builder.add_node("finalize", finalize_node)

    # Define edges - START to Initialize
    builder.set_entry_point("initialize")

    # Fan-out: Initialize to Detectives (parallel)
    builder.add_edge("initialize", "repo_investigator")
    builder.add_edge("initialize", "doc_analyst")
    builder.add_edge("initialize", "vision_inspector")

    # Fan-in: Detectives to Aggregation
    builder.add_edge("repo_investigator", "aggregate_evidence")
    builder.add_edge("doc_analyst", "aggregate_evidence")
    builder.add_edge("vision_inspector", "aggregate_evidence")

    # Fan-out: Aggregation to Judges (parallel)
    builder.add_edge("aggregate_evidence", "prosecutor")
    builder.add_edge("aggregate_evidence", "defense")
    builder.add_edge("aggregate_evidence", "tech_lead")

    # Fan-in: Judges to Chief Justice
    builder.add_edge("prosecutor", "chief_justice")
    builder.add_edge("defense", "chief_justice")
    builder.add_edge("tech_lead", "chief_justice")

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
    logger.info(f"Aggregated {total_evidence} pieces of evidence from {len(evidences)} detectives")

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


def _cross_reference_pdf_claims(state: AgentState, evidences: Dict[str, list]) -> list[Evidence]:
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
        for evidence in repo_evidence:
            if evidence.found and evidence.location and (
                "/" in evidence.location or "\\" in evidence.location
            ):
                verified_locations.append(evidence.location)

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
