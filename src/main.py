"""
Main entry point for the Automaton Auditor.
Provides CLI interface for running audits.
"""

import sys
from datetime import datetime
from pathlib import Path

import typer
from rich.console import Console

from .core.config import get_config, load_rubric
from .core.graph import create_auditor_graph
from .core.state import RubricConfig
from .utils.exceptions import AutomatonAuditorException
from .utils.logger import get_logger

app = typer.Typer(
    name="automaton-auditor",
    help="Production-grade code quality auditing with multi-agent LangGraph swarms",
)

console = Console()
logger = get_logger()


def _run_audit(
    repo_url: str,
    pdf_path: str,
    output_dir: str,
    rubric_path: str,
) -> None:
    """
    Shared audit runner used by both `audit` and `self-audit` commands.
    """
    console.print("\n[bold blue]=== Automaton Auditor ===[/bold blue]\n")

    console.print("[yellow]->[/yellow] Loading configuration...")
    get_config()

    console.print(f"[yellow]->[/yellow] Loading rubric from {rubric_path}...")
    rubric_dict = load_rubric(rubric_path)
    rubric = RubricConfig(**rubric_dict)

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

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

    console.print("[yellow]->[/yellow] Building auditor graph...")
    graph = create_auditor_graph()

    console.print("\n[bold green]Starting audit execution...[/bold green]\n")
    result = graph.invoke(initial_state)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_file = output_path / f"audit_report_{timestamp}.md"
    latest_report_file = output_path / "audit_report.md"

    report_content = result["final_report"]
    report_file.write_text(report_content, encoding="utf-8")
    # Keep a stable filename for quick access while preserving timestamped history.
    latest_report_file.write_text(report_content, encoding="utf-8")

    console.print("\n[bold green]=== Audit Complete ===[/bold green]\n")
    console.print(f"[green]Saved report:[/green] {report_file}")
    console.print(f"[green]Updated latest:[/green] {latest_report_file}")

    if result.get("final_scores"):
        console.print("\n[bold]Final Scores:[/bold]")
        for criterion, score in result["final_scores"].items():
            color = "green" if score >= 4 else "yellow" if score >= 3 else "red"
            console.print(f"  [{color}]*[/{color}] {criterion}: {score}/5")

        total = sum(result["final_scores"].values())
        max_score = len(result["final_scores"]) * 5
        percentage = (total / max_score * 100) if max_score > 0 else 0

        color = "green" if percentage >= 80 else "yellow" if percentage >= 60 else "red"
        console.print(f"\n[{color}]Total: {total}/{max_score} ({percentage:.1f}%)[/{color}]")

    console.print("")


@app.command()
def audit(
    repo_url: str = typer.Argument(..., help="GitHub repository URL to audit"),
    pdf_path: str = typer.Argument(..., help="Path to PDF architectural report"),
    output_dir: str = typer.Option(
        "audit/report_onpeer_generated",
        "--output",
        "-o",
        help="Output directory for audit report",
    ),
    rubric_path: str = typer.Option(
        "rubric/week2_rubric.json",
        "--rubric",
        "-r",
        help="Path to rubric JSON file",
    ),
):
    """
    Run a comprehensive audit on a repository and report.

    Example:
        python -m src.main audit https://github.com/user/repo report.pdf
    """
    try:
        _run_audit(
            repo_url=repo_url,
            pdf_path=pdf_path,
            output_dir=output_dir,
            rubric_path=rubric_path,
        )
    except AutomatonAuditorException as e:
        console.print(f"\n[bold red]Audit failed:[/bold red] {e}\n")
        logger.error(f"Audit failed: {e}", exc_info=True)
        sys.exit(1)
    except Exception as e:
        console.print(f"\n[bold red]Unexpected error:[/bold red] {e}\n")
        logger.error(f"Unexpected error: {e}", exc_info=True)
        sys.exit(1)


@app.command("self-audit")
def self_audit(
    repo_url: str = typer.Argument(..., help="Your own repository URL"),
    pdf_path: str = typer.Argument(..., help="Your architectural report PDF"),
    rubric_path: str = typer.Option(
        "rubric/week2_rubric.json",
        "--rubric",
        "-r",
        help="Path to rubric JSON file",
    ),
):
    """
    Audit your own Week 2 submission.

    This will generate a self-assessment report in audit/report_onself_generated/
    """
    console.print("\n[bold cyan]=== Self-Audit Mode ===[/bold cyan]\n")

    try:
        _run_audit(
            repo_url=repo_url,
            pdf_path=pdf_path,
            output_dir="audit/report_onself_generated",
            rubric_path=rubric_path,
        )
    except AutomatonAuditorException as e:
        console.print(f"\n[bold red]Self-audit failed:[/bold red] {e}\n")
        logger.error(f"Self-audit failed: {e}", exc_info=True)
        sys.exit(1)
    except Exception as e:
        console.print(f"\n[bold red]Unexpected error:[/bold red] {e}\n")
        logger.error(f"Unexpected error in self-audit: {e}", exc_info=True)
        sys.exit(1)


@app.command()
def version():
    """Display version information."""
    console.print("\n[bold]Automaton Auditor[/bold] v2.0.0")
    console.print("Deep LangGraph Swarms for Autonomous Code Governance\n")


if __name__ == "__main__":
    app()
