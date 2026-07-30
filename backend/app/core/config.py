"""
Application configuration management.
"""
from typing import List
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    app_env: str = "development"
    app_name: str = "DARWINBOXAI"
    api_v1_str: str = "/api/v1"
    app_debug: bool = True
    secret_key: str = "change-me-in-production"
    log_level: str = "INFO"

    # JWT
    jwt_secret_key: str = "development-jwt-secret-change-me-32-chars"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # Database
    database_url: str = "postgresql://postgres:postgres@localhost:5432/darwinboxai"
    database_echo: bool = False
    database_pool_size: int = 20
    database_max_overflow: int = 10

    # CORS
    cors_origins: List[str] = ["http://localhost:3000", "http://localhost:5173"]

    # LLM Configuration
    llm_provider: str = "openai"
    llm_model: str = "gpt-5.6-sol"
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    llm_timeout_seconds: float = 60
    llm_max_retries: int = 2
    llm_max_output_tokens: int = 2000
    llm_reasoning_effort: str = "medium"

    # Embedding Configuration
    embedding_provider: str = "mock"
    embedding_model: str = "text-embedding-3-small"
    embedding_dimension: int = 128

    # Mock HR Adapters
    mock_hr_adapters_enabled: bool = True

    # Policy RAG
    policy_top_k: int = 5
    policy_min_score: float = 0.3
    policy_chunk_size: int = 500
    policy_chunk_overlap: int = 100

    # Incident Memory
    incident_top_k: int = 3
    incident_min_score: float = 0.4

    # Workflow Configuration
    workflow_max_retries: int = 3
    workflow_timeout_seconds: int = 3600
    approval_expiry_hours: int = 48

    # Data Freshness
    data_freshness_max_age_minutes: int = 30

    # APScheduler
    scheduler_enabled: bool = True
    scheduler_timezone: str = "UTC"

    # Logging
    log_format: str = "json"
    correlation_id_header: str = "X-Correlation-ID"
    rate_limiting_enabled: bool = True
    rate_limit_requests_per_minute: int = 120

    # Feature Flags
    enable_policy_rag: bool = True
    enable_incident_memory: bool = True
    enable_audit_logging: bool = True
    enable_approvals: bool = True
    enable_task_scheduling: bool = True

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
