"""
Main entry point for the Automaton Auditor.
Provides CLI interface for running audits.
"""

import sys
import os
import shutil
import json
from datetime import datetime
from pathlib import Path
import re
from typing import Literal
from urllib.parse import parse_qs, urlparse
from urllib.request import Request, urlopen
from uuid import uuid4

import typer
from rich.console import Console

from .core.config import get_config, load_rubric
from .core.graph import create_auditor_graph
from .core.state import RubricConfig
from .utils.formatters import MarkdownReportFormatter
from .utils.exceptions import AutomatonAuditorException
from .utils.logger import get_logger

app = typer.Typer(
    name="automaton-auditor",
    help="Production-grade code quality auditing with multi-agent LangGraph swarms",
)

console = Console()
logger = get_logger()


def _is_http_url(value: str) -> bool:
    """Return True when input is an HTTP(S) URL."""
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _extract_google_drive_file_id(url: str) -> str | None:
    """Extract file ID from common Google Drive sharing URL formats."""
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    if "drive.google.com" not in host:
        return None

    query_id = parse_qs(parsed.query).get("id", [None])[0]
    if query_id:
        return query_id

    match = re.search(r"/file/d/([^/]+)", parsed.path)
    if match:
        return match.group(1)

    return None


def _normalize_pdf_download_url(url: str) -> str:
    """Convert Google Drive sharing URLs into direct download URLs."""
    drive_file_id = _extract_google_drive_file_id(url)
    if drive_file_id:
        return f"https://drive.google.com/uc?export=download&id={drive_file_id}"
    return url


def _resolve_local_pdf_path(pdf_input: str) -> Path:
    """Resolve local PDF path from absolute, relative, or filename-only input."""
    candidate = Path(pdf_input).expanduser()

    if candidate.is_absolute() and candidate.is_file():
        return candidate.resolve()

    if not candidate.is_absolute():
        cwd_candidate = (Path.cwd() / candidate).resolve()
        if cwd_candidate.is_file():
            return cwd_candidate

        # Filename-only fallback: search once inside repository tree.
        if candidate.parent == Path("."):
            matches = [
                p.resolve() for p in Path.cwd().rglob(candidate.name) if p.is_file()
            ]
            if len(matches) == 1:
                return matches[0]
            if len(matches) > 1:
                sample = ", ".join(str(p.relative_to(Path.cwd())) for p in matches[:3])
                raise AutomatonAuditorException(
                    f"PDF file name '{pdf_input}' is ambiguous. Matches: {sample}. "
                    "Provide a full or unique relative path."
                )

    raise AutomatonAuditorException(
        f"PDF file not found: '{pdf_input}'. Working directory is '{Path.cwd()}'. "
        "Use an absolute path, a valid relative path, or an HTTP(S) URL."
    )


def _download_pdf_from_url(pdf_url: str, output_dir: Path) -> Path:
    """Download remote PDF (including Google Drive) into output cache directory."""
    output_dir.mkdir(parents=True, exist_ok=True)
    download_url = _normalize_pdf_download_url(pdf_url)

    try:
        request = Request(download_url, headers={"User-Agent": "AutomatonAuditor/2.0"})
        with urlopen(request, timeout=30) as response:
            payload = response.read()
            content_type = str(response.headers.get("Content-Type", "")).lower()
    except Exception as e:
        raise AutomatonAuditorException(f"Failed to download PDF from URL: {e}") from e

    if not payload:
        raise AutomatonAuditorException("Downloaded PDF is empty")

    if not payload.startswith(b"%PDF"):
        raise AutomatonAuditorException(
            f"Downloaded content is not a PDF (content-type: '{content_type or 'unknown'}')"
        )

    file_name = f"downloaded_report_{uuid4().hex[:10]}.pdf"
    destination = (output_dir / file_name).resolve()
    destination.write_bytes(payload)
    return destination


def _resolve_pdf_input(
    pdf_input: str,
    output_dir: Path,
    source_mode: Literal["auto", "local", "remote"] = "auto",
) -> Path:
    """Resolve CLI PDF input into a concrete local file path."""
    cleaned = pdf_input.strip().strip('"').strip("'")
    is_remote_input = _is_http_url(cleaned)

    if source_mode == "local":
        if is_remote_input:
            raise AutomatonAuditorException(
                "PDF source mode is local, but an HTTP(S) URL was provided."
            )
        return _resolve_local_pdf_path(cleaned)

    if source_mode == "remote":
        if not is_remote_input:
            raise AutomatonAuditorException(
                "PDF source mode is remote, but input is not an HTTP(S) URL."
            )
        return _download_pdf_from_url(cleaned, output_dir / "_downloads")

    if is_remote_input:
        return _download_pdf_from_url(cleaned, output_dir / "_downloads")
    return _resolve_local_pdf_path(cleaned)


def _store_peer_report(
    pdf_input: str,
    source_mode: Literal["auto", "local", "remote"] = "auto",
    label: str | None = None,
) -> Path:
    """
    Save a peer-provided PDF into audit/report_bypeer_received with a manifest entry.
    """
    output_dir = Path("audit") / "report_bypeer_received"
    output_dir.mkdir(parents=True, exist_ok=True)
    resolved_pdf = _resolve_pdf_input(pdf_input, output_dir, source_mode=source_mode)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = output_dir / f"peer_report_{timestamp}.pdf"
    shutil.copy2(resolved_pdf, dest)

    manifest = output_dir / "manifest.jsonl"
    entry = {
        "saved_as": dest.name,
        "source": pdf_input,
        "resolved_path": str(resolved_pdf),
        "label": label or "peer_report",
        "timestamp": timestamp,
    }
    with manifest.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
    return dest


def _resolve_source_mode(
    local_pdf: bool, remote_pdf: bool
) -> Literal["auto", "local", "remote"]:
    """Resolve mutually exclusive local/remote CLI flags."""
    if local_pdf and remote_pdf:
        raise typer.BadParameter("Use either --local/-l or --remote/-r, not both.")
    if local_pdf:
        return "local"
    if remote_pdf:
        return "remote"
    return "auto"


def _run_audit(
    repo_url: str,
    pdf_path: str,
    output_dir: str,
    rubric_path: str,
    pdf_source_mode: Literal["auto", "local", "remote"] = "auto",
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
    resolved_pdf_path = _resolve_pdf_input(
        pdf_path, output_path, source_mode=pdf_source_mode
    )
    logger.info(f"Resolved PDF path: {resolved_pdf_path}")

    initial_state = {
        "repo_url": repo_url,
        "pdf_path": str(resolved_pdf_path),
        "pdf_source": pdf_path,
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
    # Allow robust execution for CLI runs.
    os.environ["AUDITOR_FAIL_FAST"] = "false"
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
        console.print(
            f"\n[{color}]Total: {total}/{max_score} ({percentage:.1f}%)[/{color}]"
        )

    console.print("")


@app.command()
def audit(
    repo_url: str = typer.Argument(..., help="GitHub repository URL to audit"),
    pdf_path: str = typer.Argument(..., help="Path to PDF architectural report"),
    local_pdf: bool = typer.Option(
        False,
        "--local",
        "-l",
        help="Treat pdf_path as a local filesystem path.",
    ),
    remote_pdf: bool = typer.Option(
        False,
        "--remote",
        "-r",
        help="Treat pdf_path as an HTTP(S) URL (including Google Drive links).",
    ),
    output_dir: str = typer.Option(
        "audit/report_onpeer_generated",
        "--output",
        "-o",
        help="Output directory for audit report",
    ),
    rubric_path: str = typer.Option(
        "rubric/week2_rubric.json",
        "--rubric",
        help="Path to rubric JSON file",
    ),
):
    """
    Run a comprehensive audit on a repository and report.

    Example:
        python -m src.main audit https://github.com/user/repo report.pdf
    """
    try:
        pdf_source_mode = _resolve_source_mode(local_pdf, remote_pdf)
        _run_audit(
            repo_url=repo_url,
            pdf_path=pdf_path,
            output_dir=output_dir,
            rubric_path=rubric_path,
            pdf_source_mode=pdf_source_mode,
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
    local_pdf: bool = typer.Option(
        False,
        "--local",
        "-l",
        help="Treat pdf_path as a local filesystem path.",
    ),
    remote_pdf: bool = typer.Option(
        False,
        "--remote",
        "-r",
        help="Treat pdf_path as an HTTP(S) URL (including Google Drive links).",
    ),
    rubric_path: str = typer.Option(
        "rubric/week2_rubric.json",
        "--rubric",
        help="Path to rubric JSON file",
    ),
):
    """
    Audit your own Week 2 submission.

    This will generate a self-assessment report in audit/report_onself_generated/
    """
    console.print("\n[bold cyan]=== Self-Audit Mode ===[/bold cyan]\n")

    try:
        pdf_source_mode = _resolve_source_mode(local_pdf, remote_pdf)
        _run_audit(
            repo_url=repo_url,
            pdf_path=pdf_path,
            output_dir="audit/report_onself_generated",
            rubric_path=rubric_path,
            pdf_source_mode=pdf_source_mode,
        )
    except AutomatonAuditorException as e:
        console.print(f"\n[bold red]Self-audit failed:[/bold red] {e}\n")
        logger.error(f"Self-audit failed: {e}", exc_info=True)
        sys.exit(1)
    except Exception as e:
        console.print(f"\n[bold red]Unexpected error:[/bold red] {e}\n")
        logger.error(f"Unexpected error in self-audit: {e}", exc_info=True)
        sys.exit(1)


@app.command("triage-report")
def triage_report(
    repo_url: str = typer.Argument(..., help="GitHub repository URL to audit"),
    pdf_path: str = typer.Argument(..., help="Path to PDF architectural report"),
    local_pdf: bool = typer.Option(
        False, "--local", "-l", help="Treat pdf_path as a local filesystem path."
    ),
    remote_pdf: bool = typer.Option(
        False,
        "--remote",
        "-r",
        help="Treat pdf_path as an HTTP(S) URL (including Google Drive links).",
    ),
    rubric_path: str = typer.Option(
        "rubric/week2_rubric.json",
        "--rubric",
        help="Path to rubric JSON file",
    ),
    output_dir: str = typer.Option(
        "reports/triage",
        "--output",
        "-o",
        help="Output directory for triage report",
    ),
):
    """
    Generate a concise remediation-focused report.
    """
    try:
        pdf_source_mode = _resolve_source_mode(local_pdf, remote_pdf)
        get_config()
        rubric_dict = load_rubric(rubric_path)
        rubric = RubricConfig(**rubric_dict)

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        resolved_pdf_path = _resolve_pdf_input(
            pdf_path, output_path, source_mode=pdf_source_mode
        )

        initial_state = {
            "repo_url": repo_url,
            "pdf_path": str(resolved_pdf_path),
            "pdf_source": pdf_path,
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

        os.environ["AUDITOR_FAIL_FAST"] = "false"
        graph = create_auditor_graph()
        result = graph.invoke(initial_state)

        exec_time = (
            result.get("execution_end_time", 0)
            - result.get("execution_start_time", 0)
        )
        opinions_by_criterion = {}
        for op in result.get("opinions", []):
            opinions_by_criterion.setdefault(op.criterion_id, []).append(op)

        remediation = MarkdownReportFormatter._generate_remediation(  # type: ignore
            result.get("final_scores", {}), opinions_by_criterion
        )

        report_content = MarkdownReportFormatter.format_triage_report(
            repo_url=repo_url,
            pdf_path=str(resolved_pdf_path),
            final_scores=result.get("final_scores", {}),
            synthesis_summary=result.get("synthesis_summary", ""),
            remediation=remediation,
            execution_time=exec_time,
        )

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = output_path / f"triage_{timestamp}.md"
        report_file.write_text(report_content, encoding="utf-8")
        console.print(f"\n[bold green]Saved triage report:[/bold green] {report_file}")

    except AutomatonAuditorException as e:
        console.print(f"\n[bold red]Triage failed:[/bold red] {e}\n")
        logger.error(f"Triage failed: {e}", exc_info=True)
        sys.exit(1)
    except Exception as e:
        console.print(f"\n[bold red]Unexpected error:[/bold red] {e}\n")
        logger.error(f"Unexpected error in triage-report: {e}", exc_info=True)
        sys.exit(1)


@app.command("receive-peer")
def receive_peer(
    pdf_path: str = typer.Argument(..., help="Peer's PDF report to store"),
    local_pdf: bool = typer.Option(
        False,
        "--local",
        "-l",
        help="Treat pdf_path as a local filesystem path.",
    ),
    remote_pdf: bool = typer.Option(
        False,
        "--remote",
        "-r",
        help="Treat pdf_path as an HTTP(S) URL (including Google Drive links).",
    ),
    label: str = typer.Option(
        "peer_report",
        "--label",
        "-L",
        help="Optional label for manifest entry.",
    ),
):
    """
    Store a peer-provided audit PDF under audit/report_bypeer_received.
    """
    try:
        pdf_source_mode = _resolve_source_mode(local_pdf, remote_pdf)
        saved = _store_peer_report(pdf_path, source_mode=pdf_source_mode, label=label)
        console.print(
            f"\n[bold green]Saved peer report:[/bold green] {saved} "
            f"(label: {label})"
        )
    except AutomatonAuditorException as e:
        console.print(f"\n[bold red]Receive failed:[/bold red] {e}\n")
        logger.error(f"Receive peer failed: {e}", exc_info=True)
        sys.exit(1)
    except Exception as e:
        console.print(f"\n[bold red]Unexpected error:[/bold red] {e}\n")
        logger.error(f"Unexpected error in receive-peer: {e}", exc_info=True)
        sys.exit(1)


@app.command()
def version():
    """Display version information."""
    console.print("\n[bold]Automaton Auditor[/bold] v2.0.0")
    console.print("Deep LangGraph Swarms for Autonomous Code Governance\n")


if __name__ == "__main__":
    app()
