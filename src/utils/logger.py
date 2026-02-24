"""
Comprehensive logging system for the Automaton Auditor.
Provides structured logging with context tracking and security filtering.
"""

import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from rich.console import Console
from rich.logging import RichHandler


class SecurityFilter(logging.Filter):
    """Filter to redact sensitive information from logs."""

    SENSITIVE_KEYS = {
        "api_key",
        "token",
        "password",
        "secret",
        "authorization",
        "openai_api_key",
        "anthropic_api_key",
    }

    def filter(self, record: logging.LogRecord) -> bool:
        """Redact sensitive information from log messages."""
        if hasattr(record, "msg") and isinstance(record.msg, str):
            for key in self.SENSITIVE_KEYS:
                if key in record.msg.lower():
                    # Redact values that look like API keys
                    record.msg = self._redact_keys(record.msg)
        return True

    def _redact_keys(self, message: str) -> str:
        """Redact potential API keys from message."""
        import re

        # Redact OpenAI-style keys
        message = re.sub(r"sk-[a-zA-Z0-9]{48}", "sk-***REDACTED***", message)
        # Redact Anthropic-style keys
        message = re.sub(r"sk-ant-[a-zA-Z0-9-]{95}", "sk-ant-***REDACTED***", message)
        return message


class AuditorLogger:
    """
    Central logging system with context tracking and structured output.
    """

    _instance: Optional["AuditorLogger"] = None
    _initialized: bool = False

    def __new__(cls) -> "AuditorLogger":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self._setup_logging()
            self._initialized = True

    def _setup_logging(self) -> None:
        """Configure logging with both file and console handlers."""
        # Create logs directory
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)

        # Create logger
        self.logger = logging.getLogger("automaton_auditor")
        self.logger.setLevel(logging.DEBUG)
        self.logger.handlers = []  # Clear existing handlers

        # File handler (detailed)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_handler = logging.FileHandler(log_dir / f"auditor_{timestamp}.log")
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(funcName)s:%(lineno)d | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        file_handler.setFormatter(file_formatter)
        file_handler.addFilter(SecurityFilter())
        self.logger.addHandler(file_handler)

        # Console handler (clean output with Rich)
        console_handler = RichHandler(
            console=Console(stderr=True),
            show_time=True,
            show_path=False,
            markup=True,
            rich_tracebacks=True,
        )
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter("%(message)s", datefmt="[%X]")
        console_handler.setFormatter(console_formatter)
        console_handler.addFilter(SecurityFilter())
        self.logger.addHandler(console_handler)

        # Context storage
        self._context: Dict[str, Any] = {}

    def set_context(self, **kwargs: Any) -> None:
        """Set context variables for logging."""
        self._context.update(kwargs)

    def clear_context(self) -> None:
        """Clear all context variables."""
        self._context.clear()

    def _format_message(self, message: str) -> str:
        """Format message with context."""
        if self._context:
            context_str = " | ".join([f"{k}={v}" for k, v in self._context.items()])
            return f"[{context_str}] {message}"
        return message

    def debug(self, message: str, **kwargs: Any) -> None:
        """Log debug message."""
        self.logger.debug(self._format_message(message), extra=kwargs)

    def info(self, message: str, **kwargs: Any) -> None:
        """Log info message."""
        self.logger.info(self._format_message(message), extra=kwargs)

    def warning(self, message: str, **kwargs: Any) -> None:
        """Log warning message."""
        self.logger.warning(self._format_message(message), extra=kwargs)

    def error(self, message: str, exc_info: bool = False, **kwargs: Any) -> None:
        """Log error message."""
        self.logger.error(self._format_message(message), exc_info=exc_info, extra=kwargs)

    def critical(self, message: str, exc_info: bool = True, **kwargs: Any) -> None:
        """Log critical message."""
        self.logger.critical(self._format_message(message), exc_info=exc_info, extra=kwargs)

    def log_node_start(self, node_name: str) -> None:
        """Log the start of a graph node."""
        self.info(f"[bold blue]→ Starting node:[/bold blue] {node_name}")

    def log_node_complete(self, node_name: str, duration: float) -> None:
        """Log successful completion of a graph node."""
        self.info(f"[bold green]✓ Completed node:[/bold green] {node_name} ({duration:.2f}s)")

    def log_node_error(self, node_name: str, error: Exception) -> None:
        """Log node execution error."""
        self.error(f"[bold red]✗ Node failed:[/bold red] {node_name} - {str(error)}", exc_info=True)

    def log_evidence_found(self, evidence_type: str, confidence: float) -> None:
        """Log evidence discovery."""
        confidence_color = "green" if confidence > 0.8 else "yellow" if confidence > 0.5 else "red"
        self.info(
            f"[bold {confidence_color}]📋 Evidence found:[/bold {confidence_color}] "
            f"{evidence_type} (confidence: {confidence:.2f})"
        )

    def log_judicial_opinion(self, judge: str, criterion: str, score: int) -> None:
        """Log judicial opinion."""
        self.info(f"[bold magenta]⚖️  {judge}:[/bold magenta] {criterion} → Score: {score}")

    def log_security_violation(self, violation_type: str, details: str) -> None:
        """Log security violation."""
        self.critical(
            f"[bold red]🚨 SECURITY VIOLATION:[/bold red] {violation_type} - {details}",
            exc_info=False,
        )


# Global logger instance
logger = AuditorLogger()


def get_logger() -> AuditorLogger:
    """Get the global logger instance."""
    return logger
