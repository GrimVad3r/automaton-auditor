# Quick Start Guide

## Setup (5 minutes)

### 1. Install Dependencies
```bash
# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install the package
pip install -e .
```

### 2. Configure API Keys
```bash
# Copy example environment file
cp .env.example .env

# Edit .env and add your API keys
nano .env  # or use your preferred editor
```

Minimum required configuration:
```bash
# Add ONE of these
OPENAI_API_KEY=sk-...
# OR
ANTHROPIC_API_KEY=sk-ant-...

# Optional but recommended
LANGCHAIN_API_KEY=ls-...
```

### 3. Verify Installation
```bash
# Check version
python -m src.main version

# Should output:
# Automaton Auditor v2.0.0
# Deep LangGraph Swarms for Autonomous Code Governance
```

## First Audit

### Example 1: Audit a GitHub Repository
```bash
python -m src.main audit \
  https://github.com/example/week2-submission \
  example_report.pdf
```

### Example 2: Self-Assessment
```bash
python -m src.main self-audit \
  https://github.com/your-username/your-repo \
  your_report.pdf
```

## Understanding the Output

The audit generates a Markdown report in `audit/report_onpeer_generated/audit_report.md` with:

1. **Executive Summary**
   - Overall scores and assessment
   - Key findings

2. **Forensic Evidence**
   - RepoInvestigator findings (code analysis)
   - DocAnalyst findings (PDF analysis)

3. **Judicial Analysis**
   - Prosecutor's critical assessment
   - Defense's supportive view
   - Tech Lead's pragmatic evaluation

4. **Remediation Plan**
   - Specific issues to fix
   - Priority ranking

## Troubleshooting

### "Configuration validation failed"
→ Check that your `.env` file has at least one API key

### "Git clone failed"
→ Verify the repository URL is correct and accessible
→ Check network connectivity

### "Module not found"
→ Run `pip install -e .` again
→ Ensure virtual environment is activated

### "LangSmith tracing failed"
→ Add `LANGCHAIN_API_KEY` to `.env`
→ Or disable tracing: `LANGCHAIN_TRACING_V2=false`

## Next Steps

1. **Review the rubric**: `rubric/week2_rubric.json`
2. **Customize settings**: Edit `.env` for your needs
3. **Run tests**: `pytest`
4. **Read full docs**: `README.md`

## Support

- Issues: GitHub Issues
- Questions: Discussion board
- Security: security@example.com

Happy Auditing! 🏛️
