# Automaton Auditor

**Deep LangGraph Swarms for Autonomous Code Governance**

A production-grade multi-agent system that forensically analyzes code repositories and architectural documentation using a hierarchical "Digital Courtroom" architecture.

## 🏛️ Architecture Overview

The Automaton Auditor implements a three-layer hierarchical state graph:

```
┌─────────────────────────────────────────────────────────────┐
│                     LAYER 1: DETECTIVES                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │     Repo     │  │     Doc      │  │   Vision     │       │
│  │ Investigator │  │   Analyst    │  │  Inspector   │       │
│  └──────────────┘  └──────────────┘  └──────────────┘       │
│         │                 │                 │               │
│         └─────────────────┴─────────────────┘               │
│                           │                                 │
└───────────────────────────┼─────────────────────────────────┘
                            │
                  ┌─────────▼─────────┐
                  │ Evidence          │
                  │ Aggregation       │
                  └─────────┬─────────┘
                            │
┌───────────────────────────┼─────────────────────────────────┐
│                     LAYER 2: JUDGES                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │ Prosecutor   │  │   Defense    │  │  Tech Lead   │       │
│  │  (Critical)  │  │ (Optimistic) │  │ (Pragmatic)  │       │
│  └──────────────┘  └──────────────┘  └──────────────┘       │
│         │                 │                 │               │
│         └─────────────────┴─────────────────┘               │
└───────────────────────────┼─────────────────────────────────┘
                            │
                  ┌─────────▼─────────┐
                  │  Chief Justice    │
                  │   (Synthesis)     │
                  └───────────────────┘
```

### Layer 1: Detective Layer (Forensic Evidence Collection)
- **RepoInvestigator**: Analyzes git history, file structure, and code using AST parsing
- **DocAnalyst**: Extracts concepts from PDFs and cross-references claims
- **VisionInspector**: Analyzes architectural diagrams (optional)

### Layer 2: Judicial Layer (Dialectical Reasoning)
- **Prosecutor**: Critical lens, assumes "vibe coding", harsh scoring
- **Defense Attorney**: Optimistic lens, rewards effort and intent
- **Tech Lead**: Pragmatic lens, evaluates maintainability and functionality

### Layer 3: Supreme Court (Synthesis)
- **Chief Justice**: Resolves conflicts using deterministic rules, generates final report

## 🔐 Security Features

- **Sandboxed Git Operations**: All repository clones run in isolated temporary directories
- **Input Validation**: URLs, file paths, and command arguments are validated against injection attacks
- **No Shell Execution**: Uses `subprocess` with argument lists (never `shell=True`)
- **Path Traversal Protection**: All file operations validated against base directory
- **Resource Limits**: Enforces size limits on repositories (500MB) and files (10MB)
- **API Key Security**: Environment-based configuration with automatic redaction in logs

## 📋 Prerequisites

- Python 3.11+
- Git
- API keys for:
  - OpenAI (GPT-4) or Anthropic (Claude)
  - LangSmith (for tracing)

## 🚀 Installation

1. **Clone the repository:**
```bash
git clone https://github.com/GrimVad3r/automaton-auditor.git
cd automaton-auditor
```

2. **Create virtual environment:**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies:**
```bash
pip install -e .
```

4. **Configure environment:**
```bash
cp .env.example .env
# Edit .env and add your API keys
```

## ⚙️ Configuration

Edit `.env` file:

```bash
# Required: At least one LLM API key
OPENAI_API_KEY=sk-your-openai-key
# OR
ANTHROPIC_API_KEY=sk-ant-your-anthropic-key

# LangSmith (optional but recommended)
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=ls-your-langsmith-key
LANGCHAIN_PROJECT=automaton-auditor

# Application Settings
MAX_REPO_SIZE_MB=500
GIT_CLONE_TIMEOUT=60
LOG_LEVEL=INFO

# Security
ALLOWED_GIT_DOMAINS=github.com,gitlab.com,bitbucket.org
```

## 📖 Usage

### Audit a Peer's Repository

```bash
python -m src.main audit \
  https://github.com/peer/week2-submission \
  peer_report.pdf \
  --output audit/report_onpeer_generated
```

### Self-Audit Your Own Work

```bash
python -m src.main self-audit \
  https://github.com/your-username/week2-submission \
  your_report.pdf
```

### Custom Rubric

```bash
python -m src.main audit \
  https://github.com/user/repo \
  report.pdf \
  --rubric path/to/custom_rubric.json
```

## 📊 Output Structure

```
audit/
├── report_bypeer_received/     # Reports you received from peers
├── report_onpeer_generated/    # Reports you generated for peers
├── report_onself_generated/    # Your self-assessment reports
└── langsmith_logs/             # LangSmith trace exports
```

Each audit generates:
- `audit_report.md`: Comprehensive Markdown report
- Evidence breakdown by detective
- Judicial opinions from all three judges
- Final scores with synthesis notes
- Remediation plan

## 🧪 Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test file
pytest tests/test_detectives.py
```

## 🏗️ Project Structure

```
automaton-auditor/
├── src/
│   ├── agents/
│   │   ├── detectives/
│   │   │   ├── repo_investigator.py
│   │   │   ├── doc_analyst.py
│   │   │   └── vision_inspector.py
│   │   ├── judges/
│   │   │   ├── base_judge.py
│   │   │   ├── prosecutor.py
│   │   │   ├── defense.py
│   │   │   └── tech_lead.py
│   │   └── justice/
│   │       └── chief_justice.py
│   ├── core/
│   │   ├── config.py
│   │   ├── graph.py
│   │   └── state.py
│   ├── tools/
│   │   ├── git_tools.py
│   │   ├── ast_tools.py
│   │   ├── pdf_tools.py
│   │   └── security.py
│   ├── utils/
│   │   ├── exceptions.py
│   │   ├── logger.py
│   │   ├── validators.py
│   │   └── formatters.py
│   └── main.py
├── rubric/
│   └── week2_rubric.json
├── audit/
├── tests/
├── pyproject.toml
└── README.md
```

## 🔍 How It Works

1. **Initialization**: Loads rubric and configuration
2. **Detective Phase** (Parallel):
   - RepoInvestigator clones repo, analyzes structure and code
   - DocAnalyst extracts concepts from PDF, cross-references claims
3. **Evidence Aggregation**: Collects all forensic findings
4. **Judicial Phase** (Parallel):
   - Each judge evaluates every criterion independently
   - Prosecutor: harsh, security-focused
   - Defense: generous, intent-focused  
   - Tech Lead: pragmatic, functionality-focused
5. **Synthesis**: Chief Justice resolves conflicts using rules:
   - Security flaws cap scores at 3
   - Facts override opinions
   - Tech Lead carries highest weight
6. **Report Generation**: Produces comprehensive Markdown report

## 🎯 Key Design Principles

- **Structured Output Enforcement**: All judges use Pydantic for validated JSON
- **State Reducers**: `operator.add` and `operator.ior` prevent data loss in parallel execution
- **Security-First**: All external operations are sandboxed and validated
- **Observable**: LangSmith integration for debugging complex chains
- **Production-Grade**: Comprehensive error handling, logging, and monitoring

## 📚 Core Dependencies

- `langgraph`: StateGraph orchestration
- `langchain`: LLM abstractions
- `pydantic`: Data validation
- `gitpython`: Git operations
- `pypdf`: PDF parsing
- `rich`: Beautiful console output
- `typer`: CLI interface

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests and linting
5. Submit a pull request

## 📄 License

MIT License - see LICENSE file for details

## 🆘 Troubleshooting

### Git Clone Timeout
```bash
# Increase timeout in .env
GIT_CLONE_TIMEOUT=120
```

### Repository Too Large
```bash
# Increase size limit in .env
MAX_REPO_SIZE_MB=1000
```

### API Rate Limits
```bash
# Add retry configuration in .env
MAX_RETRIES=5
```

### LangSmith Not Tracing
```bash
# Verify LangSmith configuration
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=ls-your-key
```

## 📞 Support

- GitHub Issues: [Report bugs or request features](https://github.com/GrimVad3r/automaton-auditor/issues)
- Documentation: [Full docs](https://docs.automaton-auditor.dev)

## 🙏 Acknowledgments

Built for the AI-Native Enterprise training program, implementing concepts from:
- LangGraph documentation
- Multi-Agent Systems (MAS) research
- Constitutional AI principles
- Production security best practices

---

**Built with ❤️ for autonomous code governance**
