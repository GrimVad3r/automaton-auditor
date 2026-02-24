"""
Tests for logging utilities.
"""

import logging
import re

import pytest

from src.utils.logger import AuditorLogger, SecurityFilter


class TestSecurityFilter:
    """Tests for SecurityFilter class."""

    @pytest.fixture
    def security_filter(self):
        """Create a security filter instance."""
        return SecurityFilter()

    def test_filter_openai_key(self, security_filter):
        """Test redaction of OpenAI API keys."""
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Using key: sk-1234567890abcdef1234567890abcdef1234567890abcd",
            args=(),
            exc_info=None,
        )

        security_filter.filter(record)
        assert "sk-***REDACTED***" in record.msg
        assert "sk-1234567890" not in record.msg

    def test_filter_anthropic_key(self, security_filter):
        """Test redaction of Anthropic API keys."""
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Using key: sk-ant-" + "a" * 95,
            args=(),
            exc_info=None,
        )

        security_filter.filter(record)
        assert "sk-ant-***REDACTED***" in record.msg
        assert "sk-ant-aaa" not in record.msg

    def test_filter_groq_key(self, security_filter):
        """Test redaction of Groq API keys."""
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Using key: gsk_" + "a" * 44,
            args=(),
            exc_info=None,
        )

        security_filter.filter(record)
        assert "gsk_***REDACTED***" in record.msg
        assert "gsk_aaa" not in record.msg

    def test_filter_huggingface_key(self, security_filter):
        """Test redaction of Hugging Face API keys."""
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Using key: hf_" + "a" * 40,
            args=(),
            exc_info=None,
        )

        security_filter.filter(record)
        assert "hf_***REDACTED***" in record.msg
        assert "hf_aaa" not in record.msg

    def test_filter_no_sensitive_data(self, security_filter):
        """Test that non-sensitive messages pass through."""
        original_msg = "This is a normal log message"
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg=original_msg,
            args=(),
            exc_info=None,
        )

        security_filter.filter(record)
        assert record.msg == original_msg


class TestAuditorLogger:
    """Tests for AuditorLogger class."""

    def test_singleton_pattern(self):
        """Test that logger follows singleton pattern."""
        logger1 = AuditorLogger()
        logger2 = AuditorLogger()
        assert logger1 is logger2

    def test_context_management(self):
        """Test context variable management."""
        logger = AuditorLogger()

        logger.set_context(repo_url="https://github.com/test/repo", attempt=1)
        assert logger._context["repo_url"] == "https://github.com/test/repo"
        assert logger._context["attempt"] == 1

        logger.clear_context()
        assert len(logger._context) == 0

    def test_log_levels(self, caplog):
        """Test different log levels."""
        logger = AuditorLogger()

        with caplog.at_level(logging.DEBUG):
            logger.debug("Debug message")
            logger.info("Info message")
            logger.warning("Warning message")
            logger.error("Error message")

        assert "Debug message" in caplog.text
        assert "Info message" in caplog.text
        assert "Warning message" in caplog.text
        assert "Error message" in caplog.text

    def test_context_in_message(self, caplog):
        """Test that context is included in log messages."""
        logger = AuditorLogger()
        logger.set_context(test_id="123")

        with caplog.at_level(logging.INFO):
            logger.info("Test message")

        assert "test_id=123" in caplog.text
        assert "Test message" in caplog.text

        logger.clear_context()

    def test_log_node_start(self, caplog):
        """Test node start logging."""
        logger = AuditorLogger()

        with caplog.at_level(logging.INFO):
            logger.log_node_start("TestNode")

        assert "Starting node" in caplog.text
        assert "TestNode" in caplog.text

    def test_log_node_complete(self, caplog):
        """Test node completion logging."""
        logger = AuditorLogger()

        with caplog.at_level(logging.INFO):
            logger.log_node_complete("TestNode", 1.5)

        assert "Completed node" in caplog.text
        assert "TestNode" in caplog.text
        assert "1.50s" in caplog.text

    def test_log_evidence_found(self, caplog):
        """Test evidence logging."""
        logger = AuditorLogger()

        with caplog.at_level(logging.INFO):
            logger.log_evidence_found("test_evidence", 0.95)

        assert "Evidence found" in caplog.text
        assert "test_evidence" in caplog.text
        assert "0.95" in caplog.text

    def test_log_judicial_opinion(self, caplog):
        """Test judicial opinion logging."""
        logger = AuditorLogger()

        with caplog.at_level(logging.INFO):
            logger.log_judicial_opinion("Prosecutor", "test_criterion", 3)

        assert "Prosecutor" in caplog.text
        assert "test_criterion" in caplog.text
        assert "Score: 3" in caplog.text

    def test_log_security_violation(self, caplog):
        """Test security violation logging."""
        logger = AuditorLogger()

        with caplog.at_level(logging.CRITICAL):
            logger.log_security_violation("Command Injection", "Detected shell metacharacter")

        assert "SECURITY VIOLATION" in caplog.text
        assert "Command Injection" in caplog.text
