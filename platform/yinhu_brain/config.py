from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # ---- DB --------------------------------------------------------------
    # Demo default: a SQLite file next to the running process. Override to
    # point at any SQLAlchemy async URL (postgresql+asyncpg://..., etc.).
    database_url: str = "sqlite+aiosqlite:///./yinhu.db"

    # ---- LLM upstream ----------------------------------------------------
    # Default: Anthropic Claude. Switch to DeepSeek by setting
    # ANTHROPIC_BASE_URL=https://api.deepseek.com/anthropic and the model_*
    # fields below to deepseek-v4-pro / etc.
    anthropic_api_key: str = ""
    anthropic_base_url: str = ""
    model_parse: str = "claude-sonnet-4-6"
    model_qa: str = "claude-opus-4-7"
    model_vision: str = "claude-sonnet-4-6"

    # ---- MinerU OCR ------------------------------------------------------
    # Two routes:
    #   1. Cloud (preferred): set MINERU_API_TOKEN from
    #      https://mineru.net/apiManage/token.
    #   2. Local sidecar: set MINERU_BASE_URL (e.g. http://mineru:8765 when
    #      running `docker compose --profile local-mineru up`).
    # Leave both blank to disable MinerU (pipeline falls back to pypdf +
    # vision-only and warns loudly on scanned PDFs).
    mineru_api_token: str = ""
    mineru_cloud_base_url: str = "https://mineru.net"
    mineru_base_url: str = ""
    mineru_request_timeout_seconds: int = 900

    # ---- CORS ------------------------------------------------------------
    # Comma-separated. localhost:3000 covers the bundled frontend dev server.
    cors_allowed_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_allowed_origins.split(",") if o.strip()]


settings = Settings()
