from src.agents.detectives.repo_investigator import RepoInvestigator
from src.core.graph import _cross_reference_pdf_claims

state = {
    "repo_url": "https://github.com/GrimVad3r/automaton-auditor",
    "pdf_path": "reports/Week 2 - Final Report Take 8.pdf",
}
repo_out = RepoInvestigator().investigate(state)
evidences = {"RepoInvestigator": repo_out["evidences"]["RepoInvestigator"]}
cr = _cross_reference_pdf_claims(state, evidences)
for e in cr:
    print("found=", e.found)
    print("content=", e.content)
