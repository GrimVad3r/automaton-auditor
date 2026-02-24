"""
Abstract Syntax Tree (AST) analysis tools.
Provides deep code inspection without executing potentially malicious code.
"""

import ast
from pathlib import Path
from typing import Dict, List, Optional, Set

from ..core.state import Evidence
from ..utils.exceptions import ASTParsingError, PathTraversalError
from ..utils.logger import get_logger
from ..utils.validators import SecurityValidator

logger = get_logger()


class ASTAnalyzer:
    """
    Analyze Python code using AST parsing.
    Avoids regex-based parsing which is brittle and error-prone.
    """

    def __init__(self, base_dir: Path):
        """
        Initialize AST analyzer.

        Args:
            base_dir: Base directory for file operations (for security validation)
        """
        self.base_dir = base_dir

    def analyze_file(self, file_path: Path) -> Dict[str, Evidence]:
        """
        Analyze a Python file using AST.

        Args:
            file_path: Path to Python file

        Returns:
            Dictionary of evidence about the file
        """
        evidences: Dict[str, Evidence] = {}

        # Validate file path for security
        try:
            validated_path = SecurityValidator.validate_file_path(str(file_path), self.base_dir)
        except PathTraversalError:
            # Security-critical validation failures should be explicit.
            raise
        except Exception as e:
            logger.error(f"File path validation failed: {e}")
            evidences["file_access"] = Evidence(
                found=False,
                content=f"Security violation: {e}",
                location=str(file_path),
                confidence=1.0,
                detective_name="ASTAnalyzer",
            )
            return evidences

        # Read and parse file
        try:
            with open(validated_path, "r", encoding="utf-8") as f:
                source = f.read()

            tree = ast.parse(source, filename=str(validated_path))

            # Analyze AST
            evidences.update(self._analyze_imports(tree, file_path))
            evidences.update(self._analyze_classes(tree, file_path))
            evidences.update(self._analyze_functions(tree, file_path))
            evidences.update(self._analyze_security_patterns(tree, file_path))

        except SyntaxError as e:
            logger.warning(f"Syntax error in {file_path}: {e}")
            evidences["syntax"] = Evidence(
                found=False,
                content=f"Syntax error: {e}",
                location=str(file_path),
                confidence=1.0,
                detective_name="ASTAnalyzer",
            )

        except Exception as e:
            logger.error(f"AST parsing failed for {file_path}: {e}", exc_info=True)
            raise ASTParsingError(f"Failed to parse {file_path}: {e}")

        return evidences

    def _analyze_imports(self, tree: ast.AST, file_path: Path) -> Dict[str, Evidence]:
        """Extract and analyze imports."""
        evidences: Dict[str, Evidence] = {}
        imports: Set[str] = set()

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.add(node.module)

        # Check for key framework imports
        langgraph_imports = [imp for imp in imports if "langgraph" in imp]
        pydantic_imports = [imp for imp in imports if "pydantic" in imp]

        if langgraph_imports:
            evidences["langgraph_imports"] = Evidence(
                found=True,
                content=f"LangGraph imports: {', '.join(langgraph_imports)}",
                location=str(file_path),
                confidence=0.95,
                detective_name="ASTAnalyzer",
            )

        if pydantic_imports:
            evidences["pydantic_imports"] = Evidence(
                found=True,
                content=f"Pydantic imports: {', '.join(pydantic_imports)}",
                location=str(file_path),
                confidence=0.95,
                detective_name="ASTAnalyzer",
            )

        return evidences

    def _analyze_classes(self, tree: ast.AST, file_path: Path) -> Dict[str, Evidence]:
        """Analyze class definitions."""
        evidences: Dict[str, Evidence] = {}
        classes: List[str] = []
        pydantic_models: List[str] = []
        typed_dicts: List[str] = []

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                classes.append(node.name)

                # Check for BaseModel inheritance (Pydantic)
                for base in node.bases:
                    if isinstance(base, ast.Name) and base.id == "BaseModel":
                        pydantic_models.append(node.name)

                # Check for TypedDict inheritance
                for base in node.bases:
                    if isinstance(base, ast.Name) and base.id == "TypedDict":
                        typed_dicts.append(node.name)

        if pydantic_models:
            evidences["pydantic_models"] = Evidence(
                found=True,
                content=f"Pydantic models found: {', '.join(pydantic_models)}",
                location=str(file_path),
                confidence=0.95,
                detective_name="ASTAnalyzer",
            )

        if typed_dicts:
            evidences["typed_dicts"] = Evidence(
                found=True,
                content=f"TypedDict classes found: {', '.join(typed_dicts)}",
                location=str(file_path),
                confidence=0.95,
                detective_name="ASTAnalyzer",
            )

        return evidences

    def _analyze_functions(self, tree: ast.AST, file_path: Path) -> Dict[str, Evidence]:
        """Analyze function definitions."""
        evidences: Dict[str, Evidence] = {}
        functions: List[str] = []

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
                functions.append(node.name)

        if functions:
            evidences["functions"] = Evidence(
                found=True,
                content=f"Found {len(functions)} functions",
                location=str(file_path),
                confidence=0.9,
                detective_name="ASTAnalyzer",
            )

        return evidences

    def _analyze_security_patterns(self, tree: ast.AST, file_path: Path) -> Dict[str, Evidence]:
        """Detect potential security issues."""
        evidences: Dict[str, Evidence] = {}
        security_issues: List[str] = []

        for node in ast.walk(tree):
            # Check for os.system calls
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute):
                    if (
                        isinstance(node.func.value, ast.Name)
                        and node.func.value.id == "os"
                        and node.func.attr == "system"
                    ):
                        security_issues.append(f"os.system() call at line {node.lineno}")

                # Check for subprocess with shell=True
                if isinstance(node.func, ast.Attribute) and node.func.attr == "run":
                    for keyword in node.keywords:
                        if keyword.arg == "shell" and isinstance(keyword.value, ast.Constant):
                            if keyword.value.value is True:
                                security_issues.append(
                                    f"subprocess with shell=True at line {node.lineno}"
                                )

        if security_issues:
            evidences["security_vulnerabilities"] = Evidence(
                found=True,
                content=f"Security issues detected: {'; '.join(security_issues)}",
                location=str(file_path),
                confidence=0.99,
                detective_name="ASTAnalyzer",
            )
        else:
            evidences["security_vulnerabilities"] = Evidence(
                found=False,
                content="No obvious security vulnerabilities detected",
                location=str(file_path),
                confidence=0.7,  # Lower confidence since we can't detect everything
                detective_name="ASTAnalyzer",
            )

        return evidences

    def find_langgraph_definition(self, file_path: Path) -> Optional[Evidence]:
        """
        Specifically look for StateGraph definition and wiring.

        Args:
            file_path: Path to Python file

        Returns:
            Evidence about LangGraph architecture, or None if not found
        """
        try:
            validated_path = SecurityValidator.validate_file_path(str(file_path), self.base_dir)

            with open(validated_path, "r", encoding="utf-8") as f:
                source = f.read()

            tree = ast.parse(source, filename=str(validated_path))

            # Look for StateGraph instantiation
            has_state_graph = False
            has_add_node = False
            has_add_edge = False
            parallel_execution = False

            for node in ast.walk(tree):
                # Check for StateGraph class usage
                if isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name) and node.func.id == "StateGraph":
                        has_state_graph = True

                # Check for graph building methods
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                    if node.func.attr == "add_node":
                        has_add_node = True
                    elif node.func.attr == "add_edge":
                        has_add_edge = True

            # Heuristic: If multiple add_node calls, likely has parallelism
            if has_state_graph and has_add_node:
                # Count number of times nodes are added
                node_count = sum(
                    1
                    for node in ast.walk(tree)
                    if isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "add_node"
                )
                parallel_execution = node_count >= 3  # Heuristic threshold

            if has_state_graph:
                architecture_type = "parallel" if parallel_execution else "sequential"
                return Evidence(
                    found=True,
                    content=f"StateGraph found with {architecture_type} architecture",
                    location=str(file_path),
                    confidence=0.9 if parallel_execution else 0.8,
                    detective_name="ASTAnalyzer",
                )

            return None

        except Exception as e:
            logger.error(f"Failed to analyze LangGraph definition: {e}")
            return None
