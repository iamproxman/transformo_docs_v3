from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        extra="ignore",
        case_sensitive=True,
        env_file=[".env", "../.env"]
    )

    PROJECT_NAME: str = "TransformoDocs"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    API_BASE_URL: str = "http://localhost:8000/api/v1"
    
    # Storage & DB
    DATABASE_URL: str = "sqlite:///./transformo_docs.db"
    UPLOAD_DIR: str = "./storage"
    
    # API Keys & Bot Secrets
    GEMINI_API_KEY: str = ""
    TELEGRAM_BOT_TOKEN: str = ""
    INTERNAL_SECRET_KEY: str = "transformo-docs-secret-key-2026"
    
    # CORS
    CORS_ORIGINS: list[str] = ["*"]

settings = Settings()
