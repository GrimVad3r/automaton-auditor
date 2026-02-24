"""
Example: Programmatic usage of the Automaton Auditor.
This shows how to use the system as a library rather than CLI.
"""

from pathlib import Path

from src.core import create_auditor_graph, get_config, load_rubric
from src.core.state import RubricConfig
from src.utils.logger import get_logger

logger = get_logger()


def run_audit_programmatically(repo_url: str, pdf_path: str):
    """
    Run an audit programmatically without using the CLI.

    Args:
        repo_url: GitHub repository URL
        pdf_path: Path to PDF report

    Returns:
        Dictionary with audit results
    """
    logger.info("Starting programmatic audit")

    # Load configuration
    config = get_config()

    # Load rubric
    rubric_dict = load_rubric("rubric/week2_rubric.json")
    rubric = RubricConfig(**rubric_dict)

    # Build initial state
    initial_state = {
        "repo_url": repo_url,
        "pdf_path": pdf_path,
        "rubric": rubric,
        "evidences": {},
        "opinions": [],
        "final_scores": {},
        "synthesis_summary": "",
        "final_report": "",
        "aggregated_evidence": None,
        "execution_start_time": None,
        "execution_end_time": None,
        "errors": [],
    }

    # Create graph
    graph = create_auditor_graph()

    # Execute audit
    logger.info("Executing audit graph")
    result = graph.invoke(initial_state)

    # Extract key results
    return {
        "final_scores": result["final_scores"],
        "synthesis_summary": result["synthesis_summary"],
        "report": result["final_report"],
        "execution_time": (
            result["execution_end_time"] - result["execution_start_time"]
        ),
    }


def batch_audit_multiple_repos(repos_and_pdfs: list):
    """
    Audit multiple repositories in batch.

    Args:
        repos_and_pdfs: List of (repo_url, pdf_path) tuples

    Returns:
        List of audit results
    """
    results = []

    for repo_url, pdf_path in repos_and_pdfs:
        try:
            logger.info(f"Auditing {repo_url}")
            result = run_audit_programmatically(repo_url, pdf_path)
            results.append(
                {
                    "repo_url": repo_url,
                    "success": True,
                    "scores": result["final_scores"],
                    "execution_time": result["execution_time"],
                }
            )
        except Exception as e:
            logger.error(f"Audit failed for {repo_url}: {e}")
            results.append(
                {
                    "repo_url": repo_url,
                    "success": False,
                    "error": str(e),
                }
            )

    return results


def get_specific_criterion_analysis(repo_url: str, pdf_path: str, criterion_id: str):
    """
    Get analysis for a specific rubric criterion.

    Args:
        repo_url: Repository URL
        pdf_path: PDF path
        criterion_id: Criterion to focus on (e.g., 'langgraph_architecture')

    Returns:
        Dictionary with opinions and final score for that criterion
    """
    result = run_audit_programmatically(repo_url, pdf_path)

    # Filter opinions for this criterion
    relevant_opinions = [
        {
            "judge": "Prosecutor",
            "score": result.get("prosecutor_score", 0),
        },
        {
            "judge": "Defense",
            "score": result.get("defense_score", 0),
        },
        {
            "judge": "TechLead",
            "score": result.get("tech_lead_score", 0),
        },
    ]

    return {
        "criterion_id": criterion_id,
        "final_score": result["final_scores"].get(criterion_id),
        "opinions": relevant_opinions,
    }


if __name__ == "__main__":
    # Example 1: Single audit
    print("\\n=== Example 1: Single Audit ===")
    result = run_audit_programmatically(
        repo_url="https://github.com/example/repo",
        pdf_path="example_report.pdf",
    )
    print(f"Total Score: {sum(result['final_scores'].values())}")
    print(f"Execution Time: {result['execution_time']:.2f}s")

    # Example 2: Batch auditing
    print("\\n=== Example 2: Batch Audit ===")
    repos = [
        ("https://github.com/user1/repo", "user1_report.pdf"),
        ("https://github.com/user2/repo", "user2_report.pdf"),
    ]
    batch_results = batch_audit_multiple_repos(repos)

    for result in batch_results:
        if result["success"]:
            total = sum(result["scores"].values())
            print(f"✓ {result['repo_url']}: {total}/20")
        else:
            print(f"✗ {result['repo_url']}: {result['error']}")

    # Example 3: Focused analysis
    print("\\n=== Example 3: Focused Analysis ===")
    analysis = get_specific_criterion_analysis(
        repo_url="https://github.com/example/repo",
        pdf_path="example_report.pdf",
        criterion_id="langgraph_architecture",
    )
    print(f"Criterion: {analysis['criterion_id']}")
    print(f"Final Score: {analysis['final_score']}/5")
