from typing import Literal

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

    # ---- Document extraction provider ----------------------------------
    document_ai_provider: Literal["mistral", "landingai"] = "mistral"

    # ---- Modular ingest providers --------------------------------------
    # New provider surface. OCR_PROVIDER selects the markdown/text extractor
    # for non-text inputs; EXTRACTOR_PROVIDER selects schema-based extraction.
    # These will eventually supersede `document_ai_provider`.
    ocr_provider: Literal["mistral", "mineru"] = "mistral"
    extractor_provider: Literal["landingai", "deepseek"] = "landingai"

    # ---- MinerU 精准解析 -------------------------------------------------
    # Used by MineruPreciseOcrProvider. Implementation lands in a later task.
    mineru_api_token: str = ""
    mineru_base_url: str = "https://mineru.net"
    mineru_model_version: Literal["pipeline", "vlm"] = "vlm"
    mineru_language: str = "ch"
    mineru_enable_table: bool = True
    mineru_enable_formula: bool = True
    mineru_is_ocr: bool = True
    mineru_poll_interval_seconds: float = 2.0
    mineru_timeout_seconds: int = 180

    # ---- LandingAI ADE --------------------------------------------------
    # LandingAI's Python library reads VISION_AGENT_API_KEY from env. We keep
    # the value in settings too so Railway/.env config can be validated.
    vision_agent_api_key: str = ""
    # LandingAI SDK 1.12 accepts {"production", "eu"} only — "us" is invalid
    # and trips a runtime Unknown-environment error inside the client.
    landingai_environment: Literal["production", "eu"] = "production"
    landingai_parse_model: str = "dpt-2-latest"
    landingai_extract_model: str = "extract-latest"
    landingai_classify_model: str = "classify-latest"
    landingai_split_model: str = "split-latest"
    landingai_large_file_pages_threshold: int = 50

    # ---- CORS ------------------------------------------------------------
    # Comma-separated. localhost:3000 covers the bundled frontend dev server.
    cors_allowed_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_allowed_origins.split(",") if o.strip()]


settings = Settings()
