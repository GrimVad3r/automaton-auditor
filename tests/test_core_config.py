"""
Tests for configuration management.
"""

import os
import pytest
from pathlib import Path

from src.core.config import Config, load_config, load_rubric
from src.utils.exceptions import ConfigurationError


class TestConfig:
    """Tests for Config class."""

    def test_config_defaults(self, test_env):
        """Test default configuration values."""
        config = Config()

        # test_env fixture sets LOG_LEVEL=ERROR for quieter test output
        assert config.log_level == "ERROR"
        # test_env fixture also sets reduced limits for faster test execution
        assert config.max_repo_size_mb == 100
        assert config.git_clone_timeout == 10
        assert isinstance(config.default_llm_model, str)
        assert config.default_llm_model.strip() != ""
        assert config.default_groq_model == "llama-3.1-8b-instant"
        assert config.llm_max_output_tokens > 0
        assert config.llm_max_evidence_items_per_detective > 0
        assert config.llm_max_evidence_content_chars > 0
        assert config.llm_max_context_chars > 0

    def test_config_from_env(self, test_env):
        """Test configuration loading from environment."""
        os.environ["LOG_LEVEL"] = "DEBUG"
        os.environ["MAX_REPO_SIZE_MB"] = "1000"

        config = Config()

        assert config.log_level == "DEBUG"
        assert config.max_repo_size_mb == 1000

    def test_get_allowed_domains(self, test_env):
        """Test parsing of allowed domains."""
        config = Config()

        domains = config.get_allowed_domains()

        assert isinstance(domains, list)
        assert "github.com" in domains
        assert "gitlab.com" in domains

    def test_validate_configuration_success(self, test_env):
        """Test successful configuration validation."""
        config = Config()
        config.openai_api_key = "sk-test-key"

        # Should not raise
        config.validate_configuration()

    def test_validate_configuration_no_api_key(self):
        """Test validation failure with no API keys."""
        config = Config()
        config.openai_api_key = None
        config.anthropic_api_key = None
        config.groq_api_key = None
        config.huggingface_api_key = None

        with pytest.raises(ConfigurationError, match="No LLM API key"):
            config.validate_configuration()

    def test_validate_configuration_groq_with_na_placeholders(self):
        """Test Groq is accepted when other providers are set to NA placeholders."""
        config = Config()
        config.openai_api_key = "NA"
        config.anthropic_api_key = "NA"
        config.groq_api_key = "gsk-test-key"

        # Should normalize NA values and pass validation using Groq key.
        config.validate_configuration()
        assert config.openai_api_key is None
        assert config.anthropic_api_key is None
        assert config.groq_api_key == "gsk-test-key"

    def test_validate_configuration_huggingface_with_na_placeholders(self):
        """Test Hugging Face is accepted when other providers are set to NA placeholders."""
        config = Config()
        config.openai_api_key = "NA"
        config.anthropic_api_key = "NA"
        config.groq_api_key = "NA"
        config.huggingface_api_key = "hf-test-key"

        config.validate_configuration()
        assert config.openai_api_key is None
        assert config.anthropic_api_key is None
        assert config.groq_api_key is None
        assert config.huggingface_api_key == "hf-test-key"

    def test_validate_configuration_invalid_limits(self, test_env):
        """Test validation failure with invalid limits."""
        config = Config()
        config.openai_api_key = "sk-test"
        config.max_repo_size_mb = -1

        with pytest.raises(ConfigurationError, match="MAX_REPO_SIZE_MB"):
            config.validate_configuration()

    def test_setup_environment(self, test_env):
        """Test environment setup."""
        config = Config()
        config.openai_api_key = "sk-test-key"
        config.setup_environment()

        assert os.environ.get("OPENAI_API_KEY") == "sk-test-key"
        assert os.environ.get("LANGCHAIN_TRACING_V2") in ["true", "false"]

    def test_sandbox_dir_creation(self, test_env, temp_dir):
        """Test sandbox directory creation."""
        config = Config()
        config.sandbox_dir = str(temp_dir / "sandbox")
        config.setup_environment()

        assert Path(config.sandbox_dir).exists()


class TestLoadConfig:
    """Tests for load_config function."""

    def test_load_config_with_env_file(self, test_env, temp_dir, monkeypatch):
        """Test loading configuration from .env file."""
        # Ensure no ambient env var overrides values from the temp env file.
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        monkeypatch.delenv("HUGGINGFACE_API_KEY", raising=False)
        monkeypatch.delenv("LOG_LEVEL", raising=False)
        monkeypatch.delenv("MAX_REPO_SIZE_MB", raising=False)

        env_file = temp_dir / ".env"
        env_file.write_text("""
OPENAI_API_KEY=sk-test-key
LOG_LEVEL=DEBUG
MAX_REPO_SIZE_MB=200
""")

        config = load_config(str(env_file))
        assert config.openai_api_key == "sk-test-key"
        assert config.log_level == "DEBUG"
        assert config.max_repo_size_mb == 200

    def test_load_config_nonexistent_file(self, monkeypatch, temp_dir):
        """Test loading with nonexistent .env file."""
        # Clear process-level keys so this test is deterministic.
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        monkeypatch.delenv("HUGGINGFACE_API_KEY", raising=False)
        # Also isolate from any real project-level .env file.
        original_cwd = Path.cwd()
        try:
            monkeypatch.chdir(temp_dir)
            with pytest.raises(ConfigurationError):
                load_config("nonexistent.env")
        finally:
            # Ensure temp_dir can be cleaned up on Windows.
            monkeypatch.chdir(original_cwd)

    def test_load_config_groq_with_na_placeholders(self, temp_dir, monkeypatch):
        """Test loading .env where only Groq key is active."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        monkeypatch.delenv("HUGGINGFACE_API_KEY", raising=False)

        env_file = temp_dir / ".env"
        env_file.write_text(
            """
OPENAI_API_KEY=NA
ANTHROPIC_API_KEY=NA
GROQ_API_KEY=gsk-test-key
"""
        )

        config = load_config(str(env_file))
        assert config.openai_api_key is None
        assert config.anthropic_api_key is None
        assert config.groq_api_key == "gsk-test-key"

    def test_load_config_huggingface_with_na_placeholders(self, temp_dir, monkeypatch):
        """Test loading .env where only Hugging Face key is active."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        monkeypatch.delenv("HUGGINGFACE_API_KEY", raising=False)

        env_file = temp_dir / ".env"
        env_file.write_text(
            """
OPENAI_API_KEY=NA
ANTHROPIC_API_KEY=NA
GROQ_API_KEY=NA
HUGGINGFACE_API_KEY=hf-test-key
"""
        )

        config = load_config(str(env_file))
        assert config.openai_api_key is None
        assert config.anthropic_api_key is None
        assert config.groq_api_key is None
        assert config.huggingface_api_key == "hf-test-key"


class TestLoadRubric:
    """Tests for load_rubric function."""

    def test_load_rubric_success(self):
        """Test successful rubric loading."""
        rubric = load_rubric("rubric/week2_rubric.json")

        assert "rubric_metadata" in rubric
        assert "dimensions" in rubric
        assert "synthesis_rules" in rubric
        assert len(rubric["dimensions"]) > 0

    def test_load_rubric_nonexistent(self):
        """Test loading nonexistent rubric."""
        with pytest.raises(ConfigurationError, match="not found"):
            load_rubric("nonexistent_rubric.json")

    def test_load_rubric_invalid_json(self, temp_dir):
        """Test loading invalid JSON."""
        bad_rubric = temp_dir / "bad_rubric.json"
        bad_rubric.write_text("{ invalid json }")

        with pytest.raises(ConfigurationError, match="Invalid JSON"):
            load_rubric(str(bad_rubric))

    def test_load_rubric_missing_keys(self, temp_dir):
        """Test loading rubric with missing required keys."""
        incomplete_rubric = temp_dir / "incomplete.json"
        incomplete_rubric.write_text('{"rubric_metadata": {}}')

        with pytest.raises(ConfigurationError, match="missing required key"):
            load_rubric(str(incomplete_rubric))

    def test_rubric_structure(self):
        """Test rubric has correct structure."""
        rubric = load_rubric("rubric/week2_rubric.json")

        # Check dimensions
        for dimension in rubric["dimensions"]:
            assert "id" in dimension
            assert "name" in dimension
            assert "target_artifact" in dimension
            assert "forensic_instruction" in dimension
            assert "judicial_logic" in dimension

            # Check judicial logic
            judicial = dimension["judicial_logic"]
            assert "prosecutor" in judicial
            assert "defense" in judicial
            assert "tech_lead" in judicial

        # Check synthesis rules
        assert "security_override" in rubric["synthesis_rules"]
        assert "fact_supremacy" in rubric["synthesis_rules"]


class TestConfigurationIntegration:
    """Integration tests for configuration system."""

    def test_full_configuration_flow(self, test_env):
        """Test complete configuration flow."""
        # Load config
        config = Config()
        config.openai_api_key = "sk-test"

        # Validate
        config.validate_configuration()

        # Setup environment
        config.setup_environment()

        # Verify environment variables set
        assert os.environ.get("OPENAI_API_KEY") is not None

    def test_config_singleton_pattern(self, test_env):
        """Test that get_config returns singleton."""
        from src.core.config import get_config, _config

        # Reset singleton
        import src.core.config
        src.core.config._config = None

        config1 = get_config()
        config2 = get_config()

        assert config1 is config2
