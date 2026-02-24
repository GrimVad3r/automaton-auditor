"""
Configuration management for the Automaton Auditor.
Loads settings from environment variables with validation.
"""

import json
import os
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from ..utils.exceptions import ConfigurationError
from ..utils.logger import get_logger

logger = get_logger()


class Config(BaseSettings):
    """
    Application configuration loaded from environment variables.
    Validates all settings on initialization.
    """

    # API Keys
    openai_api_key: Optional[str] = Field(default=None, alias="OPENAI_API_KEY")
    anthropic_api_key: Optional[str] = Field(default=None, alias="ANTHROPIC_API_KEY")
    groq_api_key: Optional[str] = Field(default=None, alias="GROQ_API_KEY")
    huggingface_api_key: Optional[str] = Field(default=None, alias="HUGGINGFACE_API_KEY")

    # LangSmith Configuration
    langchain_tracing_v2: bool = Field(default=True, alias="LANGCHAIN_TRACING_V2")
    langchain_endpoint: str = Field(
        default="https://api.smith.langchain.com", alias="LANGCHAIN_ENDPOINT"
    )
    langchain_api_key: Optional[str] = Field(default=None, alias="LANGCHAIN_API_KEY")
    langchain_project: str = Field(default="automaton-auditor", alias="LANGCHAIN_PROJECT")

    # Application Settings
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    max_repo_size_mb: int = Field(default=500, alias="MAX_REPO_SIZE_MB")
    git_clone_timeout: int = Field(default=60, alias="GIT_CLONE_TIMEOUT")
    sandbox_dir: str = Field(default="/tmp/auditor_sandbox", alias="SANDBOX_DIR")

    # Security Settings
    allowed_git_domains: str = Field(
        default="github.com,gitlab.com,bitbucket.org", alias="ALLOWED_GIT_DOMAINS"
    )
    max_file_size_mb: int = Field(default=10, alias="MAX_FILE_SIZE_MB")

    # LLM Settings
    default_llm_model: str = Field(default="gpt-4-turbo-preview", alias="DEFAULT_LLM_MODEL")
    default_groq_model: str = Field(
        default="llama-3.1-8b-instant", alias="DEFAULT_GROQ_MODEL"
    )
    default_huggingface_model: str = Field(
        default="meta-llama/Llama-3.1-8B-Instruct", alias="DEFAULT_HUGGINGFACE_MODEL"
    )
    huggingface_base_url: str = Field(
        default="https://router.huggingface.co/v1", alias="HUGGINGFACE_BASE_URL"
    )
    llm_temperature: float = Field(default=0.1, alias="LLM_TEMPERATURE")
    llm_max_output_tokens: int = Field(default=400, alias="LLM_MAX_OUTPUT_TOKENS")
    llm_max_evidence_items_per_detective: int = Field(
        default=4, alias="LLM_MAX_EVIDENCE_ITEMS_PER_DETECTIVE"
    )
    llm_max_evidence_content_chars: int = Field(
        default=160, alias="LLM_MAX_EVIDENCE_CONTENT_CHARS"
    )
    llm_max_context_chars: int = Field(default=2400, alias="LLM_MAX_CONTEXT_CHARS")
    llm_retry_base_delay_seconds: float = Field(default=1.0, alias="LLM_RETRY_BASE_DELAY_SECONDS")
    llm_retry_max_delay_seconds: float = Field(default=8.0, alias="LLM_RETRY_MAX_DELAY_SECONDS")
    max_retries: int = Field(default=3, alias="MAX_RETRIES")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    def get_allowed_domains(self) -> List[str]:
        """Parse allowed git domains from comma-separated string."""
        return [d.strip() for d in self.allowed_git_domains.split(",")]

    @staticmethod
    def _normalize_api_key(value: Optional[str]) -> Optional[str]:
        """Normalize placeholder API key values to None."""
        if value is None:
            return None

        normalized = value.strip()
        if not normalized or normalized.upper() == "NA":
            return None

        return normalized

    def validate_configuration(self, require_llm_keys: bool = True) -> None:
        """
        Validate that required configuration is present.

        Raises:
            ConfigurationError: If critical configuration is missing
        """
        errors = []

        # Normalize placeholder values such as "NA" so provider selection is deterministic.
        self.openai_api_key = self._normalize_api_key(self.openai_api_key)
        self.anthropic_api_key = self._normalize_api_key(self.anthropic_api_key)
        self.groq_api_key = self._normalize_api_key(self.groq_api_key)
        self.huggingface_api_key = self._normalize_api_key(self.huggingface_api_key)

        # API keys are required only for judge/LLM execution, not for tool-only flows.
        if (
            not self.openai_api_key
            and not self.anthropic_api_key
            and not self.groq_api_key
            and not self.huggingface_api_key
        ):
            if require_llm_keys:
                errors.append(
                    "No LLM API key configured "
                    "(OPENAI_API_KEY, ANTHROPIC_API_KEY, GROQ_API_KEY, or HUGGINGFACE_API_KEY)"
                )
            else:
                logger.warning(
                    "No LLM API key configured. Tooling and graph setup will work, "
                    "but judge execution will fail until a key is provided."
                )

        # Check LangSmith if tracing enabled
        if self.langchain_tracing_v2 and not self.langchain_api_key:
            logger.warning(
                "LangSmith tracing enabled but LANGCHAIN_API_KEY not set. "
                "Disabling tracing to avoid runtime ingestion failures."
            )
            self.langchain_tracing_v2 = False

        # Validate numeric ranges
        if self.max_repo_size_mb <= 0:
            errors.append("MAX_REPO_SIZE_MB must be positive")

        if self.git_clone_timeout <= 0:
            errors.append("GIT_CLONE_TIMEOUT must be positive")

        if self.llm_max_output_tokens <= 0:
            errors.append("LLM_MAX_OUTPUT_TOKENS must be positive")

        if self.llm_max_evidence_items_per_detective <= 0:
            errors.append("LLM_MAX_EVIDENCE_ITEMS_PER_DETECTIVE must be positive")

        if self.llm_max_evidence_content_chars <= 0:
            errors.append("LLM_MAX_EVIDENCE_CONTENT_CHARS must be positive")

        if self.llm_max_context_chars <= 0:
            errors.append("LLM_MAX_CONTEXT_CHARS must be positive")

        if self.llm_retry_base_delay_seconds <= 0:
            errors.append("LLM_RETRY_BASE_DELAY_SECONDS must be positive")

        if self.llm_retry_max_delay_seconds <= 0:
            errors.append("LLM_RETRY_MAX_DELAY_SECONDS must be positive")

        if self.llm_retry_max_delay_seconds < self.llm_retry_base_delay_seconds:
            errors.append("LLM_RETRY_MAX_DELAY_SECONDS must be >= LLM_RETRY_BASE_DELAY_SECONDS")

        if errors:
            raise ConfigurationError(f"Configuration validation failed: {'; '.join(errors)}")

        logger.info("Configuration validated successfully")

    def setup_environment(self) -> None:
        """
        Set up environment variables for LangChain and other tools.
        """
        # Set API keys
        if self.openai_api_key:
            os.environ["OPENAI_API_KEY"] = self.openai_api_key
        else:
            os.environ.pop("OPENAI_API_KEY", None)

        if self.anthropic_api_key:
            os.environ["ANTHROPIC_API_KEY"] = self.anthropic_api_key
        else:
            os.environ.pop("ANTHROPIC_API_KEY", None)

        if self.groq_api_key:
            os.environ["GROQ_API_KEY"] = self.groq_api_key
        else:
            os.environ.pop("GROQ_API_KEY", None)

        if self.huggingface_api_key:
            os.environ["HUGGINGFACE_API_KEY"] = self.huggingface_api_key
            # Maintain compatibility with libraries expecting this variable name.
            os.environ["HUGGINGFACEHUB_API_TOKEN"] = self.huggingface_api_key
        else:
            os.environ.pop("HUGGINGFACE_API_KEY", None)
            os.environ.pop("HUGGINGFACEHUB_API_TOKEN", None)

        # Set LangSmith
        os.environ["LANGCHAIN_TRACING_V2"] = str(self.langchain_tracing_v2).lower()
        os.environ["LANGCHAIN_ENDPOINT"] = self.langchain_endpoint
        if self.langchain_api_key:
            os.environ["LANGCHAIN_API_KEY"] = self.langchain_api_key
        os.environ["LANGCHAIN_PROJECT"] = self.langchain_project

        # Create sandbox directory
        Path(self.sandbox_dir).mkdir(parents=True, exist_ok=True)

        logger.info("Environment configured")


def load_config(env_file: str = ".env", require_llm_keys: bool = True) -> Config:
    """
    Load configuration from environment file.

    Args:
        env_file: Path to .env file

    Returns:
        Validated Config object

    Raises:
        ConfigurationError: If configuration is invalid
    """
    # Load .env file
    # Respect process-level env vars (e.g. test harness overrides) over .env file values.
    load_dotenv(env_file, override=False)

    # Create and validate config
    config = Config()
    config.validate_configuration(require_llm_keys=require_llm_keys)
    config.setup_environment()

    return config


def load_rubric(rubric_path: str = "rubric/week2_rubric.json") -> dict:
    """
    Load and parse the rubric JSON file.

    Args:
        rubric_path: Path to rubric JSON file

    Returns:
        Parsed rubric dictionary

    Raises:
        ConfigurationError: If rubric file is invalid
    """
    try:
        rubric_file = Path(rubric_path)
        if not rubric_file.exists():
            raise ConfigurationError(f"Rubric file not found: {rubric_path}")

        with open(rubric_file, "r") as f:
            rubric = json.load(f)

        # Basic validation
        required_keys = ["rubric_metadata", "dimensions", "synthesis_rules"]
        for key in required_keys:
            if key not in rubric:
                raise ConfigurationError(f"Rubric missing required key: {key}")

        logger.info(f"Loaded rubric with {len(rubric['dimensions'])} dimensions")
        return rubric

    except json.JSONDecodeError as e:
        raise ConfigurationError(f"Invalid JSON in rubric file: {e}")
    except Exception as e:
        raise ConfigurationError(f"Failed to load rubric: {e}")


# Global config instance
_config: Optional[Config] = None


def get_config(require_llm_keys: bool = True) -> Config:
    """Get the global configuration instance."""
    global _config
    if _config is None:
        _config = load_config(require_llm_keys=require_llm_keys)
    elif require_llm_keys:
        _config.validate_configuration(require_llm_keys=True)
    return _config
