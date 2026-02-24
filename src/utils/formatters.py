"""
Report formatting utilities for generating audit outputs.
"""

from datetime import datetime
from typing import Any, Dict, List

from ..core.state import Evidence, JudicialOpinion


class MarkdownReportFormatter:
    """Format audit results as Markdown reports."""

    @staticmethod
    def format_full_report(
        repo_url: str,
        pdf_path: str,
        evidences: Dict[str, List[Evidence]],
        opinions: List[JudicialOpinion],
        final_scores: Dict[str, int],
        synthesis_summary: str,
        execution_time: float,
    ) -> str:
        """
        Generate a complete audit report in Markdown format.

        Args:
            repo_url: The audited repository URL
            pdf_path: Path to the PDF report
            evidences: Evidence collected by detectives
            opinions: All judicial opinions
            final_scores: Final scores per criterion
            synthesis_summary: Chief Justice synthesis
            execution_time: Total execution time

        Returns:
            Formatted Markdown report
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Group opinions by criterion
        opinions_by_criterion: Dict[str, List[JudicialOpinion]] = {}
        for opinion in opinions:
            if opinion.criterion_id not in opinions_by_criterion:
                opinions_by_criterion[opinion.criterion_id] = []
            opinions_by_criterion[opinion.criterion_id].append(opinion)

        report = f"""# Automaton Auditor Report

**Generated:** {timestamp}  
**Execution Time:** {execution_time:.2f} seconds  
**Repository:** {repo_url}  
**Report Document:** {pdf_path}

---

## Executive Summary

{synthesis_summary}

### Overall Scores

"""

        # Add score summary table
        report += "| Criterion | Score |\n"
        report += "|-----------|-------|\n"
        for criterion_id, score in final_scores.items():
            report += f"| {criterion_id} | {score}/5 |\n"

        total_score = sum(final_scores.values())
        max_score = len(final_scores) * 5
        percentage = (total_score / max_score) * 100 if max_score > 0 else 0

        report += f"\n**Total:** {total_score}/{max_score} ({percentage:.1f}%)\n\n"

        report += "---\n\n## Forensic Evidence\n\n"

        # Add evidence section
        for detective_name, evidence_list in evidences.items():
            report += f"### {detective_name}\n\n"
            for evidence in evidence_list:
                status = "✅ Found" if evidence.found else "❌ Not Found"
                report += f"**{status}** - {evidence.location}\n"
                report += f"- **Confidence:** {evidence.confidence:.2f}\n"
                if evidence.content:
                    report += f"- **Content:** {evidence.content[:200]}...\n"
                report += "\n"

        report += "---\n\n## Judicial Analysis\n\n"

        # Add judicial opinions
        for criterion_id, criterion_opinions in opinions_by_criterion.items():
            report += f"### {criterion_id}\n\n"

            # Show each judge's opinion
            for opinion in criterion_opinions:
                report += f"#### {opinion.judge}\n\n"
                report += f"**Score:** {opinion.score}/5\n\n"
                report += f"**Argument:**\n{opinion.argument}\n\n"
                if opinion.cited_evidence:
                    report += "**Cited Evidence:**\n"
                    for evidence_ref in opinion.cited_evidence:
                        report += f"- {evidence_ref}\n"
                report += "\n"

            # Show final score for this criterion
            final = final_scores.get(criterion_id, 0)
            report += f"**Final Verdict:** {final}/5\n\n"
            report += "---\n\n"

        report += "## Remediation Plan\n\n"
        report += MarkdownReportFormatter._generate_remediation(
            final_scores, opinions_by_criterion
        )

        report += "\n---\n\n"
        report += "## Appendix: Dialectical Process\n\n"
        report += MarkdownReportFormatter._generate_dialectics_summary(opinions_by_criterion)

        return report

    @staticmethod
    def _generate_remediation(
        final_scores: Dict[str, int],
        opinions_by_criterion: Dict[str, List[JudicialOpinion]],
    ) -> str:
        """Generate actionable remediation steps."""
        remediation = ""

        # Focus on criteria with low scores
        low_scores = [(cid, score) for cid, score in final_scores.items() if score < 4]

        if not low_scores:
            remediation += "✅ **All criteria met expectations.** No immediate remediation required.\n\n"
            return remediation

        remediation += "### Priority Issues\n\n"

        for criterion_id, score in sorted(low_scores, key=lambda x: x[1]):
            remediation += f"#### {criterion_id} (Score: {score}/5)\n\n"

            # Extract key issues from judicial opinions
            if criterion_id in opinions_by_criterion:
                prosecutor_opinion = next(
                    (o for o in opinions_by_criterion[criterion_id] if o.judge == "Prosecutor"),
                    None,
                )
                tech_lead_opinion = next(
                    (o for o in opinions_by_criterion[criterion_id] if o.judge == "TechLead"),
                    None,
                )

                if prosecutor_opinion:
                    remediation += f"**Critical Issues:**\n{prosecutor_opinion.argument}\n\n"

                if tech_lead_opinion:
                    remediation += (
                        f"**Technical Recommendations:**\n{tech_lead_opinion.argument}\n\n"
                    )

            remediation += "---\n\n"

        return remediation

    @staticmethod
    def _generate_dialectics_summary(
        opinions_by_criterion: Dict[str, List[JudicialOpinion]]
    ) -> str:
        """Summarize the dialectical process."""
        summary = "This section documents the dialectical reasoning process.\n\n"

        for criterion_id, opinions in opinions_by_criterion.items():
            scores = [o.score for o in opinions]
            variance = max(scores) - min(scores)

            if variance > 1:
                summary += f"### {criterion_id}\n\n"
                summary += f"**Score Variance:** {variance} (High dialectical tension)\n\n"

                prosecutor = next((o for o in opinions if o.judge == "Prosecutor"), None)
                defense = next((o for o in opinions if o.judge == "Defense"), None)

                if prosecutor and defense:
                    summary += f"**Thesis (Prosecutor):** Score {prosecutor.score}\n"
                    summary += f"{prosecutor.argument[:200]}...\n\n"
                    summary += f"**Antithesis (Defense):** Score {defense.score}\n"
                    summary += f"{defense.argument[:200]}...\n\n"

                summary += "---\n\n"

        return summary


class JSONReportFormatter:
    """Format audit results as JSON for machine consumption."""

    @staticmethod
    def format_report(
        repo_url: str,
        evidences: Dict[str, List[Evidence]],
        opinions: List[JudicialOpinion],
        final_scores: Dict[str, int],
    ) -> Dict[str, Any]:
        """Generate JSON report structure."""
        return {
            "metadata": {
                "timestamp": datetime.now().isoformat(),
                "repo_url": repo_url,
            },
            "scores": final_scores,
            "evidences": {
                detective: [e.model_dump() for e in evidence_list]
                for detective, evidence_list in evidences.items()
            },
            "opinions": [o.model_dump() for o in opinions],
        }
