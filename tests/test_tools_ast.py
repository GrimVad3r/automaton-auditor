"""
Tests for AST analysis tools.
"""

import pytest
from pathlib import Path

from src.tools.ast_tools import ASTAnalyzer
from src.utils.exceptions import ASTParsingError, PathTraversalError


class TestASTAnalyzer:
    """Tests for ASTAnalyzer class."""

    @pytest.fixture
    def analyzer(self, temp_dir):
        """Create an AST analyzer instance."""
        return ASTAnalyzer(temp_dir)

    @pytest.fixture
    def sample_python_file(self, temp_dir):
        """Create a sample Python file for analysis."""
        file_path = temp_dir / "sample.py"
        file_path.write_text("""
from langgraph.graph import StateGraph
from pydantic import BaseModel
from typing import TypedDict
import os

class AgentState(TypedDict):
    data: str

class Evidence(BaseModel):
    found: bool
    content: str

def process_data(x):
    return x * 2

builder = StateGraph(AgentState)
builder.add_node("node1", lambda x: x)
builder.add_edge("node1", "node2")
""")
        return file_path

    @pytest.fixture
    def insecure_python_file(self, temp_dir):
        """Create a Python file with security issues."""
        file_path = temp_dir / "insecure.py"
        file_path.write_text("""
import os
import subprocess

def dangerous_function(user_input):
    os.system(f"echo {user_input}")
    subprocess.run(["ls", "-la"], shell=True)
    return "done"
""")
        return file_path

    def test_analyze_file_success(self, analyzer, sample_python_file):
        """Test successful file analysis."""
        evidences = analyzer.analyze_file(sample_python_file)

        assert len(evidences) > 0
        assert any("import" in key for key in evidences.keys())

    def test_analyze_file_path_traversal(self, analyzer):
        """Test rejection of path traversal attempts."""
        with pytest.raises(PathTraversalError):
            analyzer.analyze_file(Path("../../etc/passwd"))

    def test_analyze_file_syntax_error(self, analyzer, temp_dir):
        """Test handling of syntax errors."""
        bad_file = temp_dir / "bad_syntax.py"
        bad_file.write_text("def broken(:\n    pass")

        evidences = analyzer.analyze_file(bad_file)

        assert "syntax" in evidences
        assert evidences["syntax"].found is False

    def test_analyze_imports(self, analyzer, sample_python_file):
        """Test import detection."""
        evidences = analyzer.analyze_file(sample_python_file)

        # Check for LangGraph imports
        assert "langgraph_imports" in evidences
        assert evidences["langgraph_imports"].found is True
        assert "langgraph" in evidences["langgraph_imports"].content.lower()

        # Check for Pydantic imports
        assert "pydantic_imports" in evidences
        assert evidences["pydantic_imports"].found is True

    def test_analyze_classes(self, analyzer, sample_python_file):
        """Test class detection."""
        evidences = analyzer.analyze_file(sample_python_file)

        # Should detect Pydantic BaseModel
        assert "pydantic_models" in evidences
        assert evidences["pydantic_models"].found is True
        assert "Evidence" in evidences["pydantic_models"].content

        # Should detect TypedDict
        assert "typed_dicts" in evidences
        assert evidences["typed_dicts"].found is True
        assert "AgentState" in evidences["typed_dicts"].content

    def test_analyze_functions(self, analyzer, sample_python_file):
        """Test function detection."""
        evidences = analyzer.analyze_file(sample_python_file)

        assert "functions" in evidences
        assert evidences["functions"].found is True

    def test_analyze_security_patterns(self, analyzer, insecure_python_file):
        """Test security vulnerability detection."""
        evidences = analyzer.analyze_file(insecure_python_file)

        assert "security_vulnerabilities" in evidences
        assert evidences["security_vulnerabilities"].found is True

        # Check for os.system detection
        assert "os.system()" in evidences["security_vulnerabilities"].content

        # Check for shell=True detection
        assert "shell=True" in evidences["security_vulnerabilities"].content

    def test_analyze_security_patterns_safe_code(self, analyzer, sample_python_file):
        """Test that safe code passes security checks."""
        evidences = analyzer.analyze_file(sample_python_file)

        assert "security_vulnerabilities" in evidences
        assert evidences["security_vulnerabilities"].found is False

    def test_find_langgraph_definition(self, analyzer, sample_python_file):
        """Test LangGraph definition detection."""
        evidence = analyzer.find_langgraph_definition(sample_python_file)

        assert evidence is not None
        assert evidence.found is True
        assert "StateGraph" in evidence.content

    def test_find_langgraph_definition_not_present(self, analyzer, temp_dir):
        """Test handling when LangGraph is not present."""
        file_path = temp_dir / "no_langgraph.py"
        file_path.write_text("""
def simple_function():
    return "Hello"
""")

        evidence = analyzer.find_langgraph_definition(file_path)
        assert evidence is None

    def test_parallel_execution_detection(self, analyzer, temp_dir):
        """Test detection of parallel execution patterns."""
        file_path = temp_dir / "parallel.py"
        file_path.write_text("""
from langgraph.graph import StateGraph

builder = StateGraph(MyState)
builder.add_node("detective1", func1)
builder.add_node("detective2", func2)
builder.add_node("detective3", func3)
builder.add_node("aggregator", agg_func)
builder.add_edge("start", "detective1")
builder.add_edge("start", "detective2")
builder.add_edge("start", "detective3")
""")

        evidence = analyzer.find_langgraph_definition(file_path)

        if evidence:
            assert "parallel" in evidence.content.lower()
            assert evidence.confidence > 0.8

    def test_sequential_execution_detection(self, analyzer, temp_dir):
        """Test detection of sequential execution patterns."""
        file_path = temp_dir / "sequential.py"
        file_path.write_text("""
from langgraph.graph import StateGraph

builder = StateGraph(MyState)
builder.add_node("node1", func1)
builder.add_node("node2", func2)
builder.add_edge("node1", "node2")
""")

        evidence = analyzer.find_langgraph_definition(file_path)

        if evidence:
            # Sequential should have lower confidence or different content
            assert evidence.found is True
