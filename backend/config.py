from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str = "sqlite+aiosqlite:///./wealth_planning.db"
    # Real envs run `alembic upgrade head`; only set true for throwaway/dev DBs.
    run_create_all_on_startup: bool = False
    secret_key: str = "dev-secret-key-change-in-production-min32"
    anthropic_api_key: str = "placeholder"
    tavily_api_key: str = "placeholder"
    chroma_db_path: str = "./chroma_db"  # used when chroma_mode == "embedded"
    # Vector store mode: "embedded" (PersistentClient) or "http" (Chroma server)
    chroma_mode: str = "embedded"
    chroma_host: str = "localhost"
    chroma_port: int = 8000
    chroma_ssl: bool = False
    uploads_path: str = "./uploads"
    reports_path: str = "./data/reports"
    # File storage backend: "local" (filesystem) or "azure" (Blob storage)
    storage_backend: str = "local"
    azure_storage_connection_string: str = ""
    azure_blob_container: str = "wpapp"
    soffice_bin: str = r"C:\Program Files\LibreOffice\program\soffice.exe"
    max_upload_bytes: int = 20 * 1024 * 1024  # 20MB
    claude_model: str = "claude-sonnet-4-6"
    claude_max_tokens_per_query: int = 8000
    tavily_max_calls_per_session: int = 5
    api_rate_limit_per_minute: int = 10

    # Azure Entra ID SSO
    azure_tenant_id: str = ""
    azure_client_id: str = ""
    azure_client_secret: str = ""

    # Public origin used in invite/reset links sent to advisors.
    # Empty string = fall back to request Origin header / base URL.
    app_base_url: str = ""

    # SMTP for outbound transactional email (invites, password resets).
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    smtp_from_name: str = "Lighthouse Canton Wealth Planning"

    @property
    def azure_jwks_uri(self) -> str:
        return f"https://login.microsoftonline.com/{self.azure_tenant_id}/discovery/v2.0/keys"

    @property
    def azure_issuer(self) -> str:
        return f"https://login.microsoftonline.com/{self.azure_tenant_id}/v2.0"

    class Config:
        env_file = ".env"

settings = Settings()
