from pydantic_settings import BaseSettings


_KNOWN_DEFAULT_SECRET_KEYS = {
    "dev-secret-key-change-in-production-min32",
    "change-me",
    "secret",
}


class Settings(BaseSettings):
    database_url: str = "sqlite+aiosqlite:///./wealth_planning.db"
    secret_key: str = ""
    anthropic_api_key: str = "placeholder"
    tavily_api_key: str = "placeholder"
    chroma_db_path: str = "./chroma_db"
    uploads_path: str = "./uploads"
    max_upload_bytes: int = 20 * 1024 * 1024  # 20MB
    claude_model: str = "claude-sonnet-4-6"
    claude_max_tokens_per_query: int = 8000
    tavily_max_calls_per_session: int = 5
    api_rate_limit_per_minute: int = 10

    # Azure Entra ID SSO
    azure_tenant_id: str = ""
    azure_client_id: str = ""
    azure_client_secret: str = ""

    @property
    def azure_jwks_uri(self) -> str:
        return f"https://login.microsoftonline.com/{self.azure_tenant_id}/discovery/v2.0/keys"

    @property
    def azure_issuer(self) -> str:
        return f"https://login.microsoftonline.com/{self.azure_tenant_id}/v2.0"

    class Config:
        env_file = ".env"


def validate_secrets(s: Settings) -> None:
    if not s.secret_key:
        raise RuntimeError(
            "SECRET_KEY is required and must be set in the environment "
            "(min length 32, not a known default). "
            "Generate one with: python -c 'import secrets; print(secrets.token_urlsafe(48))'"
        )
    if s.secret_key in _KNOWN_DEFAULT_SECRET_KEYS:
        raise RuntimeError(
            "SECRET_KEY is set to a known default sentinel. "
            "Generate one with: python -c 'import secrets; print(secrets.token_urlsafe(48))'"
        )
    if len(s.secret_key) < 32:
        raise RuntimeError(
            f"SECRET_KEY must be at least 32 characters long (got {len(s.secret_key)})."
        )


settings = Settings()
