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

    # ---- Mistral Document AI OCR ----------------------------------------
    # Used for scanned PDFs and image/photo OCR. Leave MISTRAL_API_KEY blank
    # to disable OCR; scanned PDFs will fail with an actionable config error
    # while image flows degrade to the existing vision model.
    mistral_api_key: str = ""
    mistral_base_url: str = "https://api.mistral.ai"
    mistral_ocr_model: str = "mistral-ocr-latest"
    mistral_ocr_timeout_seconds: int = 120

    # ---- CORS ------------------------------------------------------------
    # Comma-separated. localhost:3000 covers the bundled frontend dev server.
    cors_allowed_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_allowed_origins.split(",") if o.strip()]


settings = Settings()
